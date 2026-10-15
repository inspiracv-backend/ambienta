from __future__ import annotations

import asyncio
import hashlib
import io
import subprocess
from dataclasses import dataclass
from uuid import UUID

import httpx
import pymupdf
from PIL import Image

from ..backend import ClienteBackend
from ..conocimiento import BaseConocimiento
from ..proveedores import Embeddings
from ..proveedores.embeddings import como_vector

MAX_PDF_BYTES = 40 * 1024 * 1024
MAX_PAGES = 400
CHUNK_CHARS = 1400
OVERLAP_CHARS = 180


@dataclass(frozen=True)
class CuentaIngesta:
    tenant_id: UUID
    token: str


@dataclass
class ResultadoIngesta:
    documentos: int = 0
    fragmentos: int = 0
    omitidos: int = 0
    errores: list[str] | None = None


def extraer_texto_pdf(datos: bytes, *, idioma_ocr: str = "spa+eng") -> str:
    """Extrae texto del PDF; aplica OCR página a página cuando el PDF es escaneado."""
    with pymupdf.open(stream=datos, filetype="pdf") as pdf:
        if pdf.page_count > MAX_PAGES:
            raise ValueError(f"El PDF supera el máximo de {MAX_PAGES} páginas")
        paginas: list[str] = []
        for pagina in pdf:
            texto = pagina.get_text("text").strip()
            if len(texto) < 40:
                pixmap = pagina.get_pixmap(dpi=200, alpha=False)
                imagen = Image.open(io.BytesIO(pixmap.tobytes("png")))
                texto = subprocess.run(
                    ["tesseract", "stdin", "stdout", "-l", idioma_ocr],
                    input=_png(imagen), capture_output=True, check=True, timeout=90,
                ).stdout.decode("utf-8", errors="replace").strip()
            if texto:
                paginas.append(texto)
        return "\n\n".join(paginas)


def _png(imagen: Image.Image) -> bytes:
    salida = io.BytesIO()
    imagen.save(salida, format="PNG")
    return salida.getvalue()


def fragmentar(texto: str, *, max_chars: int = CHUNK_CHARS) -> list[str]:
    limpio = " ".join(texto.split())
    partes: list[str] = []
    inicio = 0
    while inicio < len(limpio):
        fin = min(inicio + max_chars, len(limpio))
        if fin < len(limpio):
            corte = limpio.rfind(" ", inicio + max_chars // 2, fin)
            if corte > inicio:
                fin = corte
        parte = limpio[inicio:fin].strip()
        if parte:
            partes.append(parte)
        if fin >= len(limpio):
            break
        solape = min(OVERLAP_CHARS, max_chars // 5)
        siguiente = max(fin - solape, inicio + 1)
        espacio = limpio.find(" ", siguiente, fin)
        inicio = espacio + 1 if espacio >= 0 else siguiente
    return partes


async def _descargar(cliente: ClienteBackend, document_id: UUID, version_id: UUID) -> tuple[bytes, str]:
    enlace = await cliente.enlace_descarga(document_id, version_id)
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as http:
        async with http.stream("GET", enlace.url) as respuesta:
            respuesta.raise_for_status()
            trozos = bytearray()
            async for trozo in respuesta.aiter_bytes():
                trozos.extend(trozo)
                if len(trozos) > MAX_PDF_BYTES:
                    raise ValueError("El PDF supera el máximo de 40 MB")
    contenido = bytes(trozos)
    checksum = hashlib.sha256(contenido).hexdigest()
    if enlace.checksum_sha256 and checksum.lower() != enlace.checksum_sha256.lower():
        raise ValueError("El checksum del PDF no coincide con el enlace firmado")
    if not contenido.startswith(b"%PDF-"):
        raise ValueError("La descarga no contiene un archivo PDF válido")
    return contenido, checksum


async def ingerir_documentos(
    *, backend_url: str, cuentas: list[CuentaIngesta], base: BaseConocimiento,
    embeddings: Embeddings, opciones_cliente: dict | None = None,
) -> ResultadoIngesta:
    resultado = ResultadoIngesta(errores=[])
    opciones = opciones_cliente or {}
    for cuenta in cuentas:
        vistos: set[UUID] = set()
        async with ClienteBackend.con_token(backend_url, cuenta.token, **opciones) as cliente:
            async for documento in cliente.documentos():
                vistos.add(documento.id)
                try:
                    if not documento.current_version_id:
                        async with base.transaccion_de_empresa(cuenta.tenant_id) as conn:
                            await conn.execute("DELETE FROM documento_fragmento WHERE tenant_id=%s AND document_id=%s",
                                               (cuenta.tenant_id, documento.id))
                        continue
                    versiones = await cliente.versiones_documento(documento.id)
                    version = next((v for v in versiones if v.id == documento.current_version_id), None)
                    if not version or version.lifecycle_status != "vigente":
                        async with base.transaccion_de_empresa(cuenta.tenant_id) as conn:
                            await conn.execute("DELETE FROM documento_fragmento WHERE tenant_id=%s AND document_id=%s",
                                               (cuenta.tenant_id, documento.id))
                        continue
                    if (version.mime_type or "").lower() != "application/pdf" and not (version.file_name or "").lower().endswith(".pdf"):
                        resultado.omitidos += 1
                        async with base.transaccion_de_empresa(cuenta.tenant_id) as conn:
                            await conn.execute("DELETE FROM documento_fragmento WHERE tenant_id=%s AND document_id=%s",
                                               (cuenta.tenant_id, documento.id))
                        continue
                    async with base.de_empresa(cuenta.tenant_id) as conn:
                        cur = await conn.execute(
                            "SELECT count(*) FROM documento_fragmento WHERE tenant_id=%s AND document_id=%s "
                            "AND version_id=%s",
                            (cuenta.tenant_id, documento.id, version.id),
                        )
                        (ya_indexado,) = await cur.fetchone()
                    if ya_indexado:
                        resultado.omitidos += 1
                        continue
                    contenido, checksum = await _descargar(cliente, documento.id, version.id)
                    texto = await asyncio.to_thread(extraer_texto_pdf, contenido)
                    bloques = fragmentar(texto)
                    if not bloques:
                        raise ValueError("No se pudo extraer texto del documento")
                    vectores = await embeddings.generar(bloques)
                    async with base.transaccion_de_empresa(cuenta.tenant_id) as conn:
                        await conn.execute("DELETE FROM documento_fragmento WHERE tenant_id=%s AND document_id=%s",
                                           (cuenta.tenant_id, documento.id))
                        for numero, (bloque, vector) in enumerate(zip(bloques, vectores, strict=True)):
                            await conn.execute(
                                "INSERT INTO documento_fragmento "
                                "(tenant_id, document_id, version_id, chunk_no, titulo, contenido, checksum_sha256, embedding) "
                                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                (cuenta.tenant_id, documento.id, version.id, numero, documento.title,
                                 bloque, checksum, como_vector(vector)),
                            )
                    resultado.documentos += 1
                    resultado.fragmentos += len(bloques)
                except Exception as exc:
                    resultado.errores.append(f"{cuenta.tenant_id}/{documento.id}: {type(exc).__name__}: {exc}")
            # Quita el índice de documentos normativos que ya no aparecen para esta empresa.
            async with base.transaccion_de_empresa(cuenta.tenant_id) as conn:
                if vistos:
                    await conn.execute(
                        "DELETE FROM documento_fragmento WHERE tenant_id=%s AND document_id <> ALL(%s)",
                        (cuenta.tenant_id, list(vistos)),
                    )
                else:
                    await conn.execute("DELETE FROM documento_fragmento WHERE tenant_id=%s", (cuenta.tenant_id,))
    return resultado
