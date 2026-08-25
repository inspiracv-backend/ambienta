"""Cuando el Perfil Empresa esta completo (RF-10, #100).

## El problema que resuelve

Hasta hoy la marca la calculaba **el navegador**:

    perfilEmpresaCompleto = Boolean(business_activity && rut_tax_id)

`rut_tax_id` es `NOT NULL` en la base, asi que nunca falta: la condicion
colapsaba a "tiene giro". Y las dos empresas del seed lo tienen. O sea que la
marca daba `true` para todas y **el flujo obligatorio de RF-10 no bloqueaba a
nadie** — nunca se le vio funcionar contra datos reales; el propio analisis dice
que se comprobaba alternando el valor por la consola del navegador.

Ni las plantas, ni los departamentos, ni el sector entraban en la cuenta, aunque
el wizard los exija para avanzar.

## Se calcula, no se guarda

Decision deliberada: no hay columna `perfil_empresa_completo`. Una bandera
guardada aparte deja **dos verdades que se pueden contradecir** — una empresa
marcada como completa a la que despues le borran la ultima planta seguiria
diciendo que si.

El costo es tres `count()` por comprobacion. Se paga: son consultas por indice
sobre tablas chicas, y la alternativa es una bandera que miente.

## Que cuenta como completo

Los cinco pasos del wizard, que es lo que el equipo eligio el 25-ago-2026 y lo
que la persona ve exigido en pantalla:

1. **Giro** declarado (`tenants.business_activity`).
2. Al menos **una instalacion**.
3. Al menos **un departamento** — lo pide RF-11.
4. **Sector CIIU** declarado (`tenants.sector_id`), sin el cual el CORE no puede
   proponer normativa.

El paso 4 del wizard (trabajadores y permisos) es de solo lectura y no cuenta:
no hay nada que la empresa pueda completar ahi todavia.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class EstadoDelPerfil:
    """Si esta completo y, sobre todo, **que falta**.

    Devolver solo un booleano obligaria a la pantalla a recalcular los mismos
    cuatro puntos para poder decir que falta — y ahi empiezan las dos verdades.
    """

    completo: bool
    faltantes: list[str] = field(default_factory=list)

    #: Para que la pantalla pueda mostrar el avance sin volver a preguntar.
    tiene_giro: bool = False
    tiene_instalaciones: bool = False
    tiene_departamentos: bool = False
    tiene_sector: bool = False


#: Lo que se le muestra a la persona por cada punto que falta. En su idioma, no
#: en nombres de columna: quien completa el perfil no sabe que es
#: `business_activity`.
FALTA = {
    "giro": "Declara el giro de la empresa.",
    "instalaciones": "Agrega al menos una planta o instalacion.",
    "departamentos": "Crea al menos un departamento.",
    "sector": "Declara el sector economico (CIIU) de la empresa.",
}


def estado(db: Session, tenant_id: UUID | str) -> EstadoDelPerfil:
    """Mira los cuatro puntos contra la base.

    Una sola consulta y no cuatro: son cuentas independientes sobre tablas
    distintas, y agruparlas evita cuatro viajes por cada request que consulte el
    perfil — que con la guarda de RF-10 puestos son muchos.

    Las cuentas de instalaciones y departamentos **corren bajo RLS**, asi que
    ven solo la empresa de la sesion aunque el `tenant_id` venga por parametro.
    Es correcto que sea asi: preguntar por el perfil de otra empresa deberia dar
    "incompleto", no su estado real.
    """
    fila = db.execute(
        text(
            """
            SELECT
              (t.business_activity IS NOT NULL
                 AND btrim(t.business_activity) <> '')          AS tiene_giro,
              (t.sector_id IS NOT NULL)                          AS tiene_sector,
              EXISTS (SELECT 1 FROM facilities f
                       WHERE f.tenant_id = t.id
                         AND f.deleted_at IS NULL)               AS tiene_instalaciones,
              EXISTS (SELECT 1 FROM departments d
                       WHERE d.tenant_id = t.id
                         AND d.deleted_at IS NULL)               AS tiene_departamentos
            FROM tenants t
            WHERE t.id = :t AND t.deleted_at IS NULL
            """
        ),
        {"t": tenant_id},
    ).first()

    if fila is None:
        # La empresa no existe o no se ve desde esta sesion. Se responde
        # "incompleto" y no un error: quien pregunta no tiene por que enterarse
        # de si esa empresa existe.
        return EstadoDelPerfil(completo=False, faltantes=list(FALTA.values()))

    giro, sector, instalaciones, departamentos = fila

    faltantes = [
        FALTA[clave]
        for clave, cumple in (
            ("giro", giro),
            ("instalaciones", instalaciones),
            ("departamentos", departamentos),
            ("sector", sector),
        )
        if not cumple
    ]

    return EstadoDelPerfil(
        completo=not faltantes,
        faltantes=faltantes,
        tiene_giro=bool(giro),
        tiene_instalaciones=bool(instalaciones),
        tiene_departamentos=bool(departamentos),
        tiene_sector=bool(sector),
    )
