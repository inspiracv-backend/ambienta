from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from ..backend import ClienteBackend, ErrorBackend
from ..backend.modelos import NotificacionNueva, TicketNuevo
from ..conocimiento import BaseConocimiento
from ..observabilidad import aviso, evento
from ..sincronizar.sincronizador import CambioDeNorma

ORIGEN = "agente_monitoreo_normativo"


@dataclass(frozen=True)
class CuentaDeEmpresa:
    """La cuenta con la que el agente actúa en una empresa. Necesita legal_matrix.read,
    company_profile.read y notification.configure; nada más."""

    tenant_id: UUID
    token: str


@dataclass(frozen=True)
class CuentaDePlataforma:
    """La cuenta del equipo de plataforma, para abrir el ticket. No ve datos de las empresas."""

    token: str


@dataclass(frozen=True)
class NovedadSMA:
    unidad_id: int
    expediente: str
    tipo: str | None
    estado: str | None
    estado_anterior: str | None  # None = proceso nuevo
    multa_uta: float | None
    enlace: str | None


@dataclass
class AvisoEmitido:
    tenant_id: str
    clave: str
    asunto: str
    destinatario: str | None
    creado: bool  # False = ya existía (no se duplica)


@dataclass
class InformeMonitoreo:
    avisos: list[AvisoEmitido] = field(default_factory=list)
    ticket: str | None = None
    errores: list[str] = field(default_factory=list)

    @property
    def creados(self) -> int:
        return sum(1 for a in self.avisos if a.creado)


def _texto_cambio(c: CambioDeNorma) -> str:
    partes = [f"La {c.etiqueta} ({c.titulo}) tiene una nueva versión vigente"
              + (f" desde el {c.vigente_desde}." if c.vigente_desde else ".")]
    if c.modificados:
        partes.append(f"Artículos modificados: {', '.join(c.modificados[:25])}"
                      + (f" y {len(c.modificados) - 25} más." if len(c.modificados) > 25 else "."))
    if c.nuevos:
        partes.append(f"Artículos nuevos: {', '.join(c.nuevos[:25])}.")
    if c.derogados:
        partes.append(f"Artículos que ya no están: {', '.join(c.derogados[:25])}.")
    partes.append("Conviene revisar su evaluación en la matriz legal: la versión evaluada ya no es la vigente.")
    return "\n".join(partes)


def _texto_sma(n: NovedadSMA, instalacion: str) -> str:
    if n.estado_anterior is None:
        cab = f"La SMA registra un proceso sancionatorio nuevo ({n.expediente}, {n.tipo}) sobre {instalacion}."
    else:
        cab = (f"El proceso sancionatorio {n.expediente} sobre {instalacion} cambió de estado: "
               f"«{n.estado_anterior}» → «{n.estado}».")
    extra = f" Multa informada: {n.multa_uta:g} UTA." if n.multa_uta else ""
    return f"{cab}{extra}\nFicha en SNIFA: {n.enlace}" if n.enlace else cab + extra


async def _unidades_de_la_empresa(cliente: ClienteBackend, base: BaseConocimiento) -> dict[int, str]:
    """Unidad fiscalizable → nombre de la instalación, por id explícito o por seia_id."""
    from ..agente.herramientas import Herramientas
    from ..snifa import unidades_por_id_sea

    salida: dict[int, str] = {}
    async for inst in cliente.instalaciones():
        ids = inst.environmental_identifiers or {}
        for k in Herramientas.CLAVES_UNIDAD:
            v = ids.get(k)
            if v not in (None, "", []):
                for x in v if isinstance(v, list) else [v]:
                    salida[int(x)] = inst.name
                break
        else:
            if ids.get("seia_id"):
                for u in (await unidades_por_id_sea(base, [str(ids["seia_id"])])).get(str(ids["seia_id"]), []):
                    salida[u] = inst.name
    return salida


async def monitorear(
    *,
    backend_url: str,
    cuentas: list[CuentaDeEmpresa],
    base: BaseConocimiento,
    cambios: list[CambioDeNorma],
    novedades: list[NovedadSMA],
    plataforma: CuentaDePlataforma | None = None,
    opciones_cliente: dict | None = None,
    hoy: Callable[[], date] = date.today,
) -> InformeMonitoreo:
    informe = InformeMonitoreo()
    if not cambios and not novedades:
        return informe
    opciones = opciones_cliente or {}
    afectadas_por_norma: dict[str, int] = {}

    for cuenta in cuentas:
        try:
            async with ClienteBackend.con_token(backend_url, cuenta.token, **opciones) as cliente:
                ya = {n.context.get("clave") async for n in cliente.notificaciones()
                      if (n.context or {}).get("origen") == ORIGEN}
                pendientes: list[tuple[str, NotificacionNueva]] = []

                if cambios:
                    matriz: dict[str, list] = {}
                    async for mn in cliente.normas_de_matriz():
                        matriz.setdefault(str(mn.norm_id), []).append(mn.owner_user_id)
                    for c in cambios:
                        if c.norm_id not in matriz:
                            continue
                        afectadas_por_norma[c.etiqueta] = afectadas_por_norma.get(c.etiqueta, 0) + 1
                        for responsable in dict.fromkeys(matriz[c.norm_id]):
                            clave = f"norma:{c.norm_id}:{c.version_nueva}:{responsable}"
                            pendientes.append((clave, NotificacionNueva(
                                recipient_user_id=responsable,
                                subject=f"Cambió la {c.etiqueta}: revisar la matriz legal",
                                body=_texto_cambio(c),
                                context={"origen": ORIGEN, "clave": clave, "tipo": "cambio_normativo",
                                         "norm_id": c.norm_id, "version_nueva": c.version_nueva,
                                         "articulos_modificados": c.modificados},
                            )))

                if novedades:
                    unidades = await _unidades_de_la_empresa(cliente, base)
                    for nv in novedades:
                        if nv.unidad_id not in unidades:
                            continue
                        clave = f"sma:{nv.expediente}:{nv.estado}"
                        pendientes.append((clave, NotificacionNueva(
                            subject=f"SMA: {'nuevo proceso sancionatorio' if nv.estado_anterior is None else 'cambio de estado'}"
                                    f" en {unidades[nv.unidad_id]}",
                            body=_texto_sma(nv, unidades[nv.unidad_id]),
                            context={"origen": ORIGEN, "clave": clave, "tipo": "novedad_sma",
                                     "expediente": nv.expediente, "unidad_fiscalizable": nv.unidad_id,
                                     "enlace": nv.enlace},
                        )))

                for clave, n in pendientes:
                    if clave in ya:
                        informe.avisos.append(AvisoEmitido(str(cuenta.tenant_id), clave, n.subject,
                                                           str(n.recipient_user_id) if n.recipient_user_id else None, False))
                        continue
                    await cliente.crear_notificacion(n)
                    ya.add(clave)
                    informe.avisos.append(AvisoEmitido(str(cuenta.tenant_id), clave, n.subject,
                                                       str(n.recipient_user_id) if n.recipient_user_id else None, True))
        except ErrorBackend as e:
            informe.errores.append(f"{cuenta.tenant_id}: {type(e).__name__}: {e.detalle}")
            aviso("monitoreo_empresa_fallo", tenant_id=str(cuenta.tenant_id), error=str(e))

    if plataforma and (cambios or novedades):
        # El equipo de plataforma se entera de QUÉ cambió y de cuántas empresas quedaron avisadas,
        # sin datos de adentro de ninguna (RF-60: sin acceso a datos de un tenant).
        lineas = [f"Corrida del {hoy().isoformat()} del agente de monitoreo normativo."]
        if cambios:
            lineas.append("\nNormas con nueva versión vigente:")
            lineas += [f"- {c.etiqueta}: {len(c.modificados)} artículos modificados, {len(c.nuevos)} nuevos, "
                       f"{len(c.derogados)} derogados · empresas con la norma en su matriz: "
                       f"{afectadas_por_norma.get(c.etiqueta, 0)}" for c in cambios]
        if novedades:
            lineas.append(f"\nNovedades en SNIFA: {len(novedades)} procesos sancionatorios nuevos o con cambio de estado.")
        lineas.append(f"\nAvisos creados: {informe.creados}. Errores: {len(informe.errores)}.")
        clave_ticket = f"monitoreo:{hoy().isoformat()}:{','.join(sorted(c.version_nueva for c in cambios))}:{len(novedades)}"
        lineas.append(f"\nClave: {clave_ticket}")
        try:
            async with ClienteBackend.con_token(backend_url, plataforma.token, **opciones) as cliente:
                existentes = [t async for t in cliente.tickets()]
                previo = next((t for t in existentes if t.subject.endswith(clave_ticket[-40:])), None)
                if previo is None:
                    t = await cliente.crear_ticket(TicketNuevo(
                        subject=f"Monitoreo normativo: {len(cambios)} normas, {len(novedades)} novedades SMA · {clave_ticket[-40:]}",
                        description="\n".join(lineas), priority="high" if novedades else "medium"))
                    informe.ticket = t.ticket_number or str(t.id)
                else:
                    informe.ticket = previo.ticket_number or str(previo.id)
        except ErrorBackend as e:
            informe.errores.append(f"plataforma: {type(e).__name__}: {e.detalle}")

    evento("monitoreo", avisos=len(informe.avisos), creados=informe.creados, ticket=informe.ticket,
           errores=len(informe.errores))
    return informe
