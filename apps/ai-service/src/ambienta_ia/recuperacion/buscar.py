"""
El recuperador (SPEC-05).

Tres caminos (D-03):

- **Exacta**: la pregunta nombra un artículo ("artículo 11 de la Ley 19.300"). Se busca por
  número, porque la búsqueda vectorial entiende de qué habla cada artículo pero no memoriza
  números: devuelve el 10 o el 12 con la misma confianza.
- **Palabras**: `tsvector` en español, para términos técnicos exactos.
- **Semántica**: pgvector, para preguntas conceptuales.

Y un cuarto para auditoría (D-06): **histórica**, que pide al backend el articulado vigente a
una fecha en vivo, porque en la base solo se indexa lo vigente hoy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from ..backend import ClienteBackend
from ..backend.modelos import Norma
from ..citas import CitaDetectada, detectar_cita, etiqueta_norma
from ..conocimiento import BaseConocimiento
from ..proveedores import Embeddings
from ..proveedores.embeddings import como_vector, coseno
from ..sincronizar.arbol import fragmentar_norma, texto_para_embedding
from .fusion import fusionar
from .reordenar import Reordenador, aplicar
from .tipos import Cita, Recuperacion, Resultado

PESO_SEMANTICA = 1.0
PESO_PALABRAS = 0.6

_COLUMNAS = """
    f.article_id, f.parte, f.article_number, f.ruta, f.texto, f.norm_id, f.version_id,
    v.norm_type, v.norm_number, v.titulo, v.official_url,
    1 - (f.embedding <=> %(vector)s::vector) AS similitud
"""

SQL_EXACTA = f"""
SELECT {_COLUMNAS}
  FROM fragmento f JOIN version_norma v ON v.id = f.version_id
 WHERE f.numero_normal = %(articulo)s
   AND (%(norma)s::text IS NULL OR v.clave_norma = %(norma)s::text)
 ORDER BY v.clave_norma, f.parte
 LIMIT 20
"""

SQL_SEMANTICA = f"""
SELECT {_COLUMNAS}
  FROM fragmento f JOIN version_norma v ON v.id = f.version_id
 WHERE (%(norma)s::text IS NULL OR v.clave_norma = %(norma)s::text)
 ORDER BY f.embedding <=> %(vector)s::vector
 LIMIT %(k)s
"""

# Cualquiera de los términos, no todos: "requieren" y "requerirán" no comparten raíz, y exigir
# todos los términos de una pregunta completa casi nunca encuentra nada. El orden lo da ts_rank.
SQL_PALABRAS = f"""
WITH consulta AS (
    SELECT nullif(replace(plainto_tsquery('spanish', %(pregunta)s)::text, '&', '|'), '')::tsquery AS q
)
SELECT {_COLUMNAS}
  FROM fragmento f JOIN version_norma v ON v.id = f.version_id
 WHERE f.busqueda @@ (SELECT q FROM consulta)
   AND (%(norma)s::text IS NULL OR v.clave_norma = %(norma)s::text)
 ORDER BY ts_rank(f.busqueda, (SELECT q FROM consulta)) DESC
 LIMIT %(k)s
"""

SQL_NORMAS_POR_CLAVE = """
SELECT norm_id, norm_type, norm_number, titulo, official_url FROM version_norma WHERE clave_norma = %s
"""

SQL_NORMA = """
SELECT norm_id, norm_type, norm_number, titulo, official_url FROM version_norma WHERE norm_id = ANY(%s)
"""


def _resultado(fila: tuple, origen: str) -> Resultado:
    (article_id, parte, article_number, ruta, texto, norm_id, version_id,
     norm_type, norm_number, titulo, official_url, similitud) = fila
    cita = Cita(
        norma=etiqueta_norma(norm_type, norm_number, titulo),
        articulo=article_number,
        ruta=ruta,
        texto=texto,
        norm_id=norm_id,
        article_id=article_id,
        norm_version_id=version_id,
        official_url=official_url,
    )
    return Resultado(
        clave=f"{article_id}:{parte}",
        cita=cita,
        similitud=float(similitud) if similitud is not None else None,
        origen={origen},  # type: ignore[arg-type]
    )


# Con reordenador: cuántos candidatos se le pasan, y un piso de similitud muy bajo que solo evita
# gastar la llamada en preguntas que no tienen nada que ver con nada del corpus.
CANDIDATOS_SEMANTICA = 20
CANDIDATOS_PALABRAS = 8
MAX_CANDIDATOS = 24
PISO_CON_REORDENADOR = 0.25


@dataclass
class _Candidatos:
    exactos: list[Resultado]
    resto: list[Resultado]
    mejor: float | None


class Recuperador:
    def __init__(self, base: BaseConocimiento, embeddings: Embeddings, *, umbral: float = 0.35, k: int = 5,
                 reordenador: Reordenador | None = None):
        """
        Sin `reordenador`, la evidencia la decide `umbral` sobre la similitud coseno (sirve con el
        catálogo de demo y sin red). Con reordenador, la decide el modelo: con el catálogo real el
        coseno no separa lo pertinente de lo ajeno (ver reordenar.py).
        """
        self.base = base
        self.embeddings = embeddings
        self.umbral = umbral
        self.k = k
        self.reordenador = reordenador

    async def recuperar(
        self,
        pregunta: str,
        tenant_id: UUID,
        *,
        fecha: date | None = None,
        cliente: ClienteBackend | None = None,
        k: int | None = None,
        alternativa: str | None = None,
    ) -> Recuperacion:
        """
        `alternativa`: otra formulación de lo mismo (la del modelo, cuando `pregunta` es la de la
        persona). Se buscan las dos y el reordenador ve las dos. Medido: la reformulación del
        modelo ("diferencia entre EIA y DIA") perdía el art. 11 que la pregunta original trae.
        """
        if not tenant_id:
            raise ValueError("Sin empresa no se busca: una búsqueda sin empresa es una fuga de datos.")
        k = k or self.k
        if alternativa and alternativa.strip() != pregunta.strip():
            return await self._con_alternativa(pregunta, alternativa, tenant_id, fecha=fecha, cliente=cliente, k=k)
        cita = detectar_cita(pregunta)
        [vector] = await self.embeddings.generar([pregunta])

        if fecha is not None:
            if cliente is None:
                raise ValueError("Una consulta a una fecha necesita el cliente del backend.")
            return await self._historica(pregunta, vector, cita, tenant_id, fecha, cliente, k)

        params = {
            "vector": como_vector(vector),
            "articulo": cita.articulo,
            "norma": cita.norma,
            "pregunta": pregunta,
            "k": k * 2,
        }
        async with self.base.de_empresa(tenant_id) as conn:
            exactos: list[Resultado] = []
            if cita:
                cur = await conn.execute(SQL_EXACTA, params)
                exactos = [_resultado(f, "exacta") for f in await cur.fetchall()]
            cur = await conn.execute(SQL_SEMANTICA, params)
            semanticos = [_resultado(f, "semantica") for f in await cur.fetchall()]
            cur = await conn.execute(SQL_PALABRAS, params)
            palabras = [_resultado(f, "palabras") for f in await cur.fetchall()]

        similitudes = [r.similitud for r in semanticos + palabras + exactos if r.similitud is not None]
        mejor = max(similitudes) if similitudes else None

        if self.reordenador is not None:
            return await self._reordenar(pregunta, exactos, semanticos, palabras, mejor, k)

        # La evidencia se decide acá, con la similitud coseno, antes de fusionar.
        semanticos = [r for r in semanticos if (r.similitud or 0) >= self.umbral]
        palabras = [r for r in palabras if (r.similitud or 0) >= self.umbral]
        combinados = fusionar([semanticos, palabras], pesos=[PESO_SEMANTICA, PESO_PALABRAS])

        if exactos:
            for r in exactos:
                r.puntaje = 1.0
            vistos = {r.clave for r in exactos}
            resto = [r for r in combinados if r.clave not in vistos]
            return Recuperacion(
                resultados=(exactos + resto)[: max(k, len(exactos))],
                modo="exacta",
                hay_evidencia=True,
                mejor_similitud=mejor,
            )

        return Recuperacion(
            resultados=combinados[:k],
            modo="combinada" if combinados else "ninguna",
            hay_evidencia=bool(combinados),
            mejor_similitud=mejor,
        )

    async def _con_alternativa(self, pregunta: str, alternativa: str, tenant_id: UUID, *, fecha: date | None,
                               cliente: ClienteBackend | None, k: int) -> Recuperacion:
        if self.reordenador is None:
            # Sin reordenador: la de la persona primero, y la alternativa solo si no alcanzó.
            r = await self.recuperar(pregunta, tenant_id, fecha=fecha, cliente=cliente, k=k)
            return r if r.hay_evidencia else await self.recuperar(alternativa, tenant_id, fecha=fecha,
                                                                   cliente=cliente, k=k)
        reordenador, self.reordenador = self.reordenador, None
        try:
            # Candidatos amplios de cada formulación, sin filtrar, y una sola calificación.
            a = await self._candidatos(pregunta, tenant_id, fecha=fecha, cliente=cliente)
            b = await self._candidatos(alternativa, tenant_id, fecha=fecha, cliente=cliente)
        finally:
            self.reordenador = reordenador
        exactos = [r for r in a.exactos + b.exactos]
        vistos: set[str] = set()
        candidatos: list[Resultado] = []
        for r in exactos + fusionar([a.resto, b.resto]):
            if r.clave not in vistos:
                vistos.add(r.clave)
                candidatos.append(r)
        candidatos = candidatos[:MAX_CANDIDATOS + 8]
        mejor = max((x for x in (a.mejor, b.mejor) if x is not None), default=None)
        if not exactos and (mejor or 0) < PISO_CON_REORDENADOR:
            return Recuperacion([], "ninguna", False, mejor)
        texto = f"{pregunta}\n(Interpretación de la consulta: {alternativa})"
        puntajes = await reordenador.calificar(texto, candidatos)
        minimos = {r.clave for r in exactos} if exactos and (detectar_cita(pregunta).norma or detectar_cita(alternativa).norma) else set()
        elegidos = aplicar(candidatos, puntajes, minimos=minimos, k=k)
        modo = "historica" if fecha else ("exacta" if exactos else "combinada")
        return Recuperacion(elegidos, modo if elegidos else "ninguna", bool(elegidos), mejor)

    async def _candidatos(self, pregunta: str, tenant_id: UUID, *, fecha: date | None,
                          cliente: ClienteBackend | None) -> _Candidatos:
        """Lo que se le pasaría al reordenador para una formulación, sin calificar."""
        if fecha is not None:
            r = await self.recuperar(pregunta, tenant_id, fecha=fecha, cliente=cliente, k=MAX_CANDIDATOS)
            # En el modo histórico, lo pedido por número vuelve ya filtrado por ese número: es un
            # pedido explícito y no lo decide el reordenador (medido: el art. 11 de 1994 caía).
            if detectar_cita(pregunta):
                return _Candidatos(r.resultados, [], r.mejor_similitud)
            return _Candidatos([], r.resultados, r.mejor_similitud)
        cita = detectar_cita(pregunta)
        [vector] = await self.embeddings.generar([pregunta])
        params = {"vector": como_vector(vector), "articulo": cita.articulo, "norma": cita.norma,
                  "pregunta": pregunta, "k": CANDIDATOS_SEMANTICA}
        async with self.base.de_empresa(tenant_id) as conn:
            exactos: list[Resultado] = []
            if cita:
                cur = await conn.execute(SQL_EXACTA, params)
                exactos = [_resultado(f, "exacta") for f in await cur.fetchall()]
            cur = await conn.execute(SQL_SEMANTICA, params)
            semanticos = [_resultado(f, "semantica") for f in await cur.fetchall()]
            params["k"] = CANDIDATOS_PALABRAS
            cur = await conn.execute(SQL_PALABRAS, params)
            palabras = [_resultado(f, "palabras") for f in await cur.fetchall()]
        sims = [r.similitud for r in semanticos + palabras + exactos if r.similitud is not None]
        return _Candidatos(exactos, fusionar([semanticos, palabras], pesos=[PESO_SEMANTICA, PESO_PALABRAS]),
                           max(sims) if sims else None)

    async def _reordenar(self, pregunta: str, exactos: list[Resultado], semanticos: list[Resultado],
                         palabras: list[Resultado], mejor: float | None, k: int) -> Recuperacion:
        modo = "exacta" if exactos else "combinada"
        if not exactos and (mejor or 0) < PISO_CON_REORDENADOR:
            return Recuperacion([], "ninguna", False, mejor)
        fusion = fusionar([semanticos[:CANDIDATOS_SEMANTICA], palabras[:CANDIDATOS_PALABRAS]],
                          pesos=[PESO_SEMANTICA, PESO_PALABRAS])
        candidatos: list[Resultado] = []
        vistos: set[str] = set()
        for r in exactos + fusion:
            if r.clave not in vistos:
                vistos.add(r.clave)
                candidatos.append(r)
        candidatos = candidatos[:MAX_CANDIDATOS]
        puntajes = await self.reordenador.calificar(pregunta, candidatos)
        # Lo pedido por número es intocable solo si también se nombró la norma: "el artículo 10"
        # suelto trae el 10 de todas las normas, y en "¿se puede ejecutar un proyecto del
        # artículo 10 sin evaluación?" lo que responde es el 8.
        minimos = {r.clave for r in exactos} if exactos and detectar_cita(pregunta).norma else set()
        elegidos = aplicar(candidatos, puntajes, minimos=minimos, k=k)
        return Recuperacion(elegidos, modo if elegidos else "ninguna", bool(elegidos), mejor)

    async def _historica(
        self,
        pregunta: str,
        vector: list[float],
        cita: CitaDetectada,
        tenant_id: UUID,
        fecha: date,
        cliente: ClienteBackend,
        k: int,
    ) -> Recuperacion:
        """
        Texto vigente a una fecha, en vivo. Candidatas: la norma nombrada, o las normas de los
        fragmentos más parecidos hoy.
        """
        async with self.base.de_empresa(tenant_id) as conn:
            if cita.norma:
                cur = await conn.execute(SQL_NORMAS_POR_CLAVE, (cita.norma,))
            else:
                cur = await conn.execute(
                    SQL_SEMANTICA, {"vector": como_vector(vector), "norma": None, "k": 12}
                )
                ids = list(dict.fromkeys(f[5] for f in await cur.fetchall()))[:3]
                cur = await conn.execute(SQL_NORMA, (ids,))
            normas = await cur.fetchall()

        candidatos: list[Resultado] = []
        titulos = {n[0]: n[3] for n in normas}
        for norm_id, norm_type, norm_number, titulo, official_url in normas:
            articulos = await cliente.articulos(norm_id, vigente_el=fecha)
            if not articulos:
                continue  # [] = no había texto vigente entonces (handoff §4)
            norma = Norma(id=norm_id, norm_type=norm_type, norm_number=norm_number, title=titulo,
                          official_url=official_url, updated_at="1970-01-01T00:00:00Z")
            etiqueta = etiqueta_norma(norm_type, norm_number, titulo)
            version_por_articulo = {a.id: a.norm_version_id for a in articulos}
            for f in fragmentar_norma(norma, articulos):
                if cita.articulo and f.numero_normal != cita.articulo:
                    continue
                candidatos.append(
                    Resultado(
                        clave=f"{f.article_id}:{f.parte}",
                        cita=Cita(
                            norma=etiqueta,
                            articulo=f.article_number,
                            ruta=f.ruta,
                            texto=f.texto,
                            norm_id=norm_id,
                            article_id=f.article_id,
                            norm_version_id=version_por_articulo.get(f.article_id),
                            official_url=official_url,
                        ),
                        similitud=None,
                        origen={"en_vivo"},
                    )
                )

        if not candidatos:
            return Recuperacion([], "historica", False, None)

        vectores = await self.embeddings.generar(
            [texto_para_embedding(titulos[r.cita.norm_id], r.cita.ruta, r.cita.texto) for r in candidatos]
        )
        for r, v in zip(candidatos, vectores, strict=True):
            r.similitud = coseno(vector, v)
            r.puntaje = r.similitud
        candidatos.sort(key=lambda r: r.similitud or 0, reverse=True)
        mejor = candidatos[0].similitud

        if cita.articulo:
            elegidos = candidatos[:k]  # pidió el artículo por número: es evidencia por sí mismo
        elif self.reordenador is not None:
            primeros = candidatos[:MAX_CANDIDATOS]
            elegidos = aplicar(primeros, await self.reordenador.calificar(pregunta, primeros), k=k)
        else:
            elegidos = [r for r in candidatos if (r.similitud or 0) >= self.umbral][:k]
        return Recuperacion(elegidos, "historica", bool(elegidos), mejor)
