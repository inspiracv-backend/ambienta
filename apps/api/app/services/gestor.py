"""Un Gestor y la cartera de clientes que administra (#59, #60, #65; RF-65 a RF-67).

## El problema, medido antes de escribir esto

El 4-sep: `EcoGestion Consultoria Ambiental Ltda` es `tenant_type = 'manager'`,
tiene el contrato `ECOG-2026-001` con Minera Andes, y **al entrar ve un sistema
vacio**:

| lo que pide | filas |
|---|---|
| `/contracts/` | 1 — el contrato existe |
| `/obligations/` | **0** — las de su cliente son invisibles |
| rutas que nombren cliente o sub-tenant | **0** |

O sea que el modelo sabe **quien administra a quien** y no hay ni un camino para
actuar sobre ello. La promesa del modulo —un consultor que lleva el cumplimiento
de varias empresas— no existia. Y `parent_tenant_id` esta en la tabla desde el
principio con **cero filas** usandolo.

## Por que esto NO toca RLS, y no es timidez

La politica de las 38 tablas es `tenant_id = current_tenant_id()`. La tentacion
es ampliarla —"o el tenant es un cliente de mi gestor"— y seria **la peor
decision posible del proyecto**: RLS no es la segunda barrera, es la unica
(CLAUDE.md §4), y una politica mas compleja hay que mantenerla correcta en 38
tablas a la vez. Un error ahi no da una pantalla vacia: da una fuga.

Lo que se agrega es otra cosa: **una forma verificada de declarar OTRO tenant**.
El gestor sigue viendo exactamente lo que RLS le deja ver; lo que cambia es que
puede pedir, explicitamente y para una peticion, correr como uno de sus
clientes. La barrera se queda donde estaba y por encima se pone una puerta con
llave.

Consecuencia que conviene tener clara: **actuando por un cliente, el gestor deja
de ver lo suyo**. No es una vista combinada. Es correcto y es lo que se quiere —
una consulta que mezclara las dos empresas es justo lo que RLS existe para
impedir.

## La llave es el contrato, y se comprueba en cada peticion

No basta con que el gestor lo haya declarado al entrar. Un contrato se suspende
o se termina, y si la comprobacion viviera en el token, revocar el acceso no
haria nada hasta que el token expire. Es la misma leccion del acceso de
invitado: la firma no basta, hay que volver a mirar la fila.

**`active` y nada mas.** `draft` y `pending_signature` son contratos que todavia
no rigen; `suspended`, `expired` y `terminated` son los que dejaron de regir, y
son exactamente los casos en que el acceso tiene que cortarse. Aceptar
`suspended` convertiria "suspender el contrato" en un gesto decorativo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.organization import Contract, Tenant
from .husos import hoy_de

#: El unico estado de contrato que habilita a un gestor a actuar por su cliente.
#:
#: Ver el encabezado: los otros cinco o todavia no rigen o dejaron de regir, y
#: en los tres ultimos cortar el acceso **es el punto**.
ESTADO_QUE_HABILITA = "active"


class ErrorDeGestor(ValueError):
    """Algo que la relacion gestor-cliente no admite."""


class NoEsGestor(ErrorDeGestor):
    """La empresa de la sesion no es un gestor."""


class SinContratoVigente(ErrorDeGestor):
    """No hay contrato activo entre este gestor y ese cliente.

    Se distingue de `NoEsGestor` porque el arreglo es otro: aca la relacion
    puede existir y estar suspendida, vencida o sin firmar.
    """


@dataclass
class ClienteDelGestor:
    tenant_id: str
    legal_name: str
    contract_id: str
    contract_number: str
    contract_status: str
    start_date: date | None
    end_date: date | None
    #: Si el gestor puede actuar por el **hoy**. Va explicito y no se filtra la
    #: lista: un cliente cuyo contrato vencio tiene que verse en la cartera —con
    #: su motivo— y no desaparecer, que se leeria como que se perdio al cliente.
    puede_actuar: bool


def es_gestor(db: Session, tenant_id: UUID) -> bool:
    return (
        db.scalar(
            select(Tenant.tenant_type).where(
                Tenant.id == tenant_id, Tenant.deleted_at.is_(None)
            )
        )
        == "manager"
    )


def cartera(db: Session, manager_id: UUID) -> list[ClienteDelGestor]:
    """Los clientes de este gestor, vigentes y no vigentes.

    **Lee `contracts` con la sesion del gestor**, o sea con RLS puesto: el
    contrato lleva `tenant_id` del gestor, asi que ve los suyos y ninguno mas.
    El nombre del cliente se resuelve aparte porque `tenants` no lleva
    `tenant_id` y no pasa por la politica.
    """
    contratos = list(
        db.scalars(
            select(Contract)
            .where(
                Contract.manager_tenant_id == manager_id,
                Contract.deleted_at.is_(None),
            )
            .order_by(Contract.start_date.desc())
        ).all()
    )
    if not contratos:
        return []

    nombres = {
        t.id: t.legal_name
        for t in db.scalars(
            select(Tenant).where(
                Tenant.id.in_([c.client_tenant_id for c in contratos])
            )
        ).all()
    }

    hoy = hoy_de(db, manager_id)
    return [
        ClienteDelGestor(
            tenant_id=str(c.client_tenant_id),
            legal_name=nombres.get(c.client_tenant_id, "(empresa retirada)"),
            contract_id=str(c.id),
            contract_number=c.contract_number,
            contract_status=c.status,
            start_date=c.start_date,
            end_date=c.end_date,
            puede_actuar=_vigente(c, hoy),
        )
        for c in contratos
    ]


def _vigente(contrato: Contract, hoy: date) -> bool:
    """Activo **y** dentro de sus fechas.

    El estado y las fechas se comprueban los dos: un contrato que nadie marco
    `expired` cuando le paso la fecha sigue diciendo `active`, y confiar solo en
    la columna dejaria el acceso abierto hasta que alguien se acuerde. El estado
    es una decision; la fecha es un hecho.

    **`hoy` viene del huso de la empresa, no de `date.today()`.** La primera
    version usaba el reloj del proceso, y la base corre en UTC mientras el host
    esta en hora de Chile: a partir de las 20:00 los dos estan en dias
    distintos, y un contrato vencido ayer seguia habilitando el acceso durante
    esas horas. Es el mismo error que el cron de avisos, el mismo dia.
    """
    if contrato.status != ESTADO_QUE_HABILITA:
        return False
    if contrato.start_date and contrato.start_date > hoy:
        return False
    if contrato.end_date and contrato.end_date < hoy:
        return False
    return True


def comprobar_puede_actuar(
    db: Session, manager_id: UUID, client_id: UUID
) -> Contract:
    """La llave. Devuelve el contrato que lo habilita, o explica por que no.

    **Se llama en cada peticion**, no una vez al entrar. Un contrato se
    suspende, vence o se termina, y si esto viviera en el token, revocarlo no
    haria nada durante lo que dure la sesion. Misma leccion que el acceso de
    invitado: la firma no basta, hay que volver a mirar la fila.
    """
    if not es_gestor(db, manager_id):
        raise NoEsGestor(
            "Esta empresa no es un gestor, asi que no puede actuar por cuenta "
            "de otra."
        )

    contrato = db.scalars(
        select(Contract)
        .where(
            Contract.manager_tenant_id == manager_id,
            Contract.client_tenant_id == client_id,
            Contract.deleted_at.is_(None),
        )
        .order_by(Contract.start_date.desc())
    ).first()

    if contrato is None:
        # **El mismo mensaje que un contrato vencido, a proposito.** Distinguir
        # "no existe" de "existe y no rige" convertiria esto en un oraculo para
        # averiguar con quien trabaja otro gestor. Es la misma razon por la que
        # `validar_visible` responde igual a un id inventado que a uno ajeno.
        raise SinContratoVigente(
            "No hay un contrato vigente con esa empresa."
        )

    if not _vigente(contrato, hoy_de(db, manager_id)):
        raise SinContratoVigente(
            "No hay un contrato vigente con esa empresa."
        )

    return contrato
