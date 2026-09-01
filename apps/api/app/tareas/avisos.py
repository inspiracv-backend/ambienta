"""El cron diario de avisos de vencimiento (#119, #118).

Dos pasos que se corren juntos y son independientes a proposito:

1. **Generar** — mira que obligaciones vencen dentro de las ventanas de cada
   empresa (15/7/3/1 por defecto) y escribe los avisos que falten. Es
   idempotente: correrlo dos veces no duplica, lo garantiza un indice unico
   (`db/17`), no un `if`.
2. **Despachar** — toma lo encolado y lo entrega. Reintenta lo que falla y se
   rinde despues de unos cuantos intentos (`db/19`).

Separados porque fallan distinto y se arreglan distinto: generar de mas es un
error de criterio en las ventanas; despachar de menos es el proveedor caido.
Un solo paso que hiciera las dos cosas informaria "todo bien" mientras la mitad
no salio.

## Por que recorre empresa por empresa con RLS puesto

Se podria hacer una sola pasada como dueño de la base, que es mas corto. **Se
elige no hacerlo.** RLS es la unica barrera entre empresas (CLAUDE.md §4), y
una tarea que la apaga para ir mas rapido convierte cualquier error de filtro
en una fuga en vez de en una pantalla vacia. Aca cada empresa se atiende con su
contexto declarado, igual que un request: si el codigo se equivoca de empresa,
Postgres devuelve cero filas en vez de las de otro.

El unico paso que necesita ver todo es **listar las empresas**, y `tenants` no
lleva `tenant_id`: se lee sin declarar contexto.

## Como se instala en el VPS

```
0 7 * * *  cd /srv/ambienta && docker compose exec -T api python -m app.tareas avisos >> /var/log/ambienta-avisos.log 2>&1
```

**A las 7 de la mañana**, para que el correo llegue antes de la jornada y no a
las tres de la madrugada, cuando nadie lo lee y ademas se confunde con spam.
La salida va a un archivo: una tarea de cron que no deja rastro es una tarea
que nadie sabe si corrio.

**Correrla mas de una vez al dia no hace daño** y de hecho conviene si el
proveedor de correo estuvo caido: la generacion no duplica y el despacho
retoma lo que quedo pendiente. Cada 4 horas es una eleccion razonable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..deps import declarar, olvidar
from ..services import despacho
from ..services.avisos_de_vencimiento import generar

logger = logging.getLogger("ambienta.tareas.avisos")


@dataclass
class Informe:
    empresas: int = 0
    creados: int = 0
    repetidos: int = 0
    escalados: int = 0
    #: Obligaciones que no avisaron a nadie: ni responsable ni administrador
    #: activo. **Es el numero que hay que mirar** — son las que quedan sin
    #: cobertura sin que nada falle.
    sin_destinatario: list[str] = field(default_factory=list)
    entregados: int = 0
    reintentables: int = 0
    rendidos: int = 0
    rechazados: int = 0
    sin_proveedor: int = 0
    atrasados: int = 0

    def resumen(self) -> str:
        lineas = [
            f"empresas atendidas: {self.empresas}",
            "",
            "generacion",
            f"  avisos nuevos: {self.creados}",
            f"  ya existian (el cron ya habia corrido): {self.repetidos}",
            f"  escalados a administradores: {self.escalados}",
            f"  obligaciones SIN destinatario: {len(self.sin_destinatario)}",
            "",
            "despacho",
            f"  entregados: {self.entregados}",
            f"  a reintentar: {self.reintentables}",
            f"  rendidos: {self.rendidos}",
            f"  rechazados sin reintento: {self.rechazados}",
            f"  correos sin proveedor configurado: {self.sin_proveedor}",
        ]
        for codigo in self.sin_destinatario:
            lineas.append(f"    - {codigo}")
        if self.atrasados:
            lineas += [
                "",
                f"  ATENCION: {self.atrasados} avisos llevan mas de 24 h encolados.",
            ]
        return "\n".join(lineas)

    def hay_que_mirarlo(self) -> bool:
        """Si algo quedo mal, el cron tiene que salir con codigo distinto de cero.

        Una tarea programada que siempre sale con 0 es una tarea que nadie
        revisa. Lo que cuenta como "mal" es lo que **nadie va a notar solo**:
        una obligacion sin nadie a quien avisarle, un aviso que se rindio, o una
        cola que se esta acumulando.
        """
        return bool(self.sin_destinatario) or self.rendidos > 0 or self.atrasados > 0


def _empresas(db: Session) -> list[UUID]:
    """Todas las empresas vivas. `tenants` no lleva `tenant_id`, se lee sin contexto."""
    return list(
        db.execute(
            text("SELECT id FROM tenants WHERE deleted_at IS NULL ORDER BY created_at")
        )
        .scalars()
        .all()
    )


def correr(*, transporte: despacho.Transporte | None = None) -> Informe:
    """Genera y despacha, empresa por empresa. Devuelve que paso."""
    informe = Informe()

    with SessionLocal() as db:
        empresas = _empresas(db)

    for tenant_id in empresas:
        # Una sesion por empresa. El contexto de RLS se fija con `SET LOCAL`, o
        # sea que vive lo que dure la transaccion, y el despachador hace commit
        # por cada aviso: reutilizar la sesion dejaria las vueltas siguientes
        # **sin empresa declarada**, viendo cero filas y sin ningun error.
        with SessionLocal() as db:
            declarar(db, tenant_id)
            try:
                r = generar(db, tenant_id)
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("Fallo la generacion de avisos en %s", tenant_id)
                continue

            informe.empresas += 1
            informe.creados += r.creados
            informe.repetidos += r.omitidos_por_repetidos
            informe.escalados += r.escalados
            informe.sin_destinatario.extend(r.sin_destinatario)

        with SessionLocal() as db:
            # **Por toda la sesion, no por transaccion.** El despachador
            # confirma cada aviso por separado, y `SET LOCAL` se pierde en el
            # primer commit: la segunda vuelta veria cero filas y la tarea
            # informaria "nada que hacer" habiendo despachado uno solo.
            declarar(db, tenant_id, toda_la_sesion=True)
            try:
                d = despacho.despachar(db, transporte=transporte)

                informe.entregados += d.entregados
                informe.reintentables += d.reintentables
                informe.rendidos += d.rendidos
                informe.rechazados += d.fallidos
                informe.sin_proveedor += d.sin_proveedor

                informe.atrasados += despacho.atrasados(db)
            except Exception:
                db.rollback()
                logger.exception("Fallo el despacho de avisos en %s", tenant_id)
            finally:
                # Sin esto la conexion vuelve al pool con esta empresa pegada.
                olvidar(db)

    return informe
