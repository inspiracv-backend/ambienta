"""Que puede respaldar un documento, y como se comprueba (RF-108, #73).

## El problema, medido antes de escribir esto

`entity_documents` guarda `entity_type` + `entity_id` **sin clave foranea**.
No es un descuido: `entity_id` apunta a trece tablas distintas segun el tipo, y
una FK exige una sola. La alternativa —trece columnas nulables y un CHECK que
exija que exactamente una este puesta— seria una migracion con `ALTER TABLE`
por cada entidad nueva.

El costo de esa decision es que **la base no puede comprobar nada**, y hasta el
7-sep-2026 tampoco lo comprobaba la aplicacion. Sonda contra la base real,
desde la empresa A:

| lo que se mandaba | respuesta |
|---|---|
| un `entity_id` inventado | **201, y la fila quedaba escrita** |
| una obligacion **real de la empresa B** | **201, y la fila quedaba escrita** |

No es una fuga de lectura: la fila nace con el `tenant_id` de quien la escribe,
asi que leerla de vuelta no revela nada que no se supiera. Es algo distinto y
peor de explicar ante un fiscalizador: la ficha afirma *"este procedimiento
respalda la obligacion X"* senalando algo que en esta empresa no existe. En un
sistema de cumplimiento un respaldo inventado es exactamente el dato que se
discute.

## Por que un mapa explicito y no `globals()` ni el registro de la ORM

Porque las dos listas —el CHECK de `db/27_vinculos_de_documentos.sql` y este
diccionario— **tienen que decir lo mismo**, y hay una prueba que lee el SQL
para exigirlo. Con un mapa escrito a mano la diferencia se ve; derivandolo de
la ORM, un tipo admitido por la base y sin modelo pasaria inadvertido.

Y por eso un `entity_type` que no este aca **no pasa la comprobacion** en vez
de saltarsela. Un `.get()` que devuelve `None` y se lee como "no hay nada que
comprobar" es una puerta abierta con forma de descuido.
"""
from __future__ import annotations

from typing import Any, NamedTuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.audit import ActionPlan, Audit, Nonconformity
from ..models.catalog import LegalNorm
from ..models.compliance import ArticleCompliance
from ..models.iso14001 import EnvironmentalAspect, RegulatedEquipment, RiskOpportunity
from ..models.obligations import DeclarationSubmission, Obligation, Task
from ..models.organization import Contract, Process

#: Cada `entity_type` admitido y el modelo al que apunta su `entity_id`.
#:
#: **Tiene que coincidir con el CHECK de `db/27_vinculos_de_documentos.sql`.**
#: `test_vinculos_de_documentos.py` lee ese archivo y compara: dos listas
#: distintas dejarian un tipo que la base acepta y la aplicacion no sabe
#: comprobar —o al reves, uno que se comprueba y la base rechaza al escribir,
#: con un 500 en vez de un mensaje.
class Anclaje(NamedTuple):
    """A que apunta un `entity_type`, y con que permiso se toca.

    **La familia va aca y no en un mapa aparte** porque un tercer diccionario
    con las mismas trece claves es un tercer sitio del que desincronizarse. La
    prueba que compara con el CHECK del SQL vale para los tres usos.
    """

    modelo: type[Any]
    #: La familia de `app/permisos_de_rutas.py`. El permiso efectivo es
    #: `<familia>.read` o `<familia>.write` segun lo que se haga.
    #:
    #: **No se invento una familia `comment`.** Un permiso nuevo que ningun rol
    #: concede es un 403 para todos, y el sintoma —"no puedo comentar"— no se
    #: parece a la causa. Se reusa la del registro sobre el que se comenta, que
    #: ademas es lo correcto: comentar sobre una auditoria es trabajo de
    #: auditoria, no una capacidad aparte.
    familia: str


ANCLAJES: dict[str, Anclaje] = {
    "article_compliance": Anclaje(ArticleCompliance, "legal_matrix"),
    "obligation": Anclaje(Obligation, "obligation"),
    "task": Anclaje(Task, "task"),
    "action_plan": Anclaje(ActionPlan, "action_plan"),
    "audit": Anclaje(Audit, "audit"),
    "nonconformity": Anclaje(Nonconformity, "nonconformity"),
    "contract": Anclaje(Contract, "manager"),
    "environmental_aspect": Anclaje(EnvironmentalAspect, "environmental_aspect"),
    "risk_opportunity": Anclaje(RiskOpportunity, "risk_opportunity"),
    "regulated_equipment": Anclaje(RegulatedEquipment, "equipment"),
    "declaration_submission": Anclaje(DeclarationSubmission, "obligation"),
    # RF-108 nombra cuatro anclajes y estos dos no estaban.
    #
    # `legal_norm` usa `legal_matrix`: la norma es catalogo global —`catalog`
    # seria su familia natural— pero `catalog.write` es de Admin Global, y
    # colgarle un procedimiento propio a una norma es trabajo de la empresa
    # sobre SU matriz, no una edicion del catalogo de nadie.
    "legal_norm": Anclaje(LegalNorm, "legal_matrix"),
    "process": Anclaje(Process, "company_profile"),
}

# **`legal_norm` es catalogo global y por eso funciona sin nada especial.**
# Medido: `legal_norms.relrowsecurity` es `false` —no lleva `tenant_id` ni
# politica—, asi que la misma lectura con la sesion de la empresa la ve. Se
# deja dicho porque la conclusion contraria era razonable y habria llevado a
# escribir una rama aparte: si la tabla tuviera RLS, comprobarla con el tenant
# declarado devolveria cero filas **siempre** y ninguna norma se podria
# vincular nunca, sin ningun error a la vista (CLAUDE.md §4). Si algun dia se
# le pone RLS a una tabla de catalogo, esto hay que revisarlo.

#: El mismo texto para las dos negativas. Ver `comprobar_anclaje`.
NO_VISIBLE = "entity_id no corresponde a un registro de esta empresa."


def comprobar_anclaje(db: Session, entity_type: str, entity_id: UUID) -> None:
    """Exige que `entity_id` exista y sea de esta empresa. Si no, 422.

    **Las dos negativas se ven identicas** —no existe, y existe pero es de otra
    empresa— con el mismo codigo y el mismo mensaje. Distinguirlas convertiria
    el endpoint en un oraculo: mandando identificadores al azar se averiguaria
    cuales corresponden a registros reales de otras empresas sin verlos nunca.
    Es la misma decision que `validar_visible` y que el 403 del gestor.

    La visibilidad la decide **Postgres**, no un `WHERE tenant_id`: se lee con
    la sesion que ya tiene el tenant declarado, asi que una fila ajena devuelve
    cero por RLS. Ese es el unico filtro por empresa que existe en el sistema
    (CLAUDE.md §4) y este servicio no inventa otro.
    """
    anclaje = ANCLAJES.get(entity_type)
    if anclaje is None:
        # No se deja pasar. Un tipo sin modelo es o un error de escritura —que
        # el CHECK de la base rechazaria despues, con un 500 en vez de un
        # mensaje— o una entidad que alguien agrego al CHECK y olvido aca.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"entity_type '{entity_type}' no es un anclaje conocido.",
        )

    modelo = anclaje.modelo
    condiciones = [modelo.id == entity_id]
    if hasattr(modelo, "deleted_at"):
        # Un registro retirado no puede recibir respaldo nuevo. El vinculo que
        # ya existia no se toca: borrarlo destruiria la prueba de que ese
        # registro estuvo respaldado mientras rigio.
        condiciones.append(modelo.deleted_at.is_(None))

    if db.scalars(select(modelo).where(*condiciones)).first() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=NO_VISIBLE
        )


def familia_de(entity_type: str) -> str:
    """La familia de permisos del registro. Levanta 422 si el tipo no existe.

    La usa el router de comentarios: comentar sobre una auditoria exige
    `audit.write`, no un permiso propio. Sin esto, el rol `servicio_lectura`
    —que solo tiene lecturas— podria escribir comentarios en cualquier ficha.
    """
    anclaje = ANCLAJES.get(entity_type)
    if anclaje is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"entity_type '{entity_type}' no es un anclaje conocido.",
        )
    return anclaje.familia
