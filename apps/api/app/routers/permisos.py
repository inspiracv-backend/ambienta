"""El catalogo de permisos, que es el vocabulario unico del RBAC (#217, RF-12).

## Por que hacia falta este endpoint

La guarda de la API decide con `permissions.code` — 39 codigos como
`legal_matrix.article.evaluate`. La pantalla de permisos tenia **su propia
lista escrita a mano** de 13 claves como `matriz_legal.evaluar`, y medido el
1-sep-2026 no compartian **ni una**:

    packages/shared -> CATALOGO_PERMISOS   13 claves
    base de datos   -> permissions.code    39 codigos
    en comun                                0

Lo unico que habia evitado el dano es que la pantalla nunca llegaba a guardar:
`updatePermisos` solo tocaba el estado local. El dia que alguien "conectara el
endpoint que falta", un Admin Empresa habria marcado trece casillas que el
servidor no consulta nunca, y se habria quedado creyendo que restringio a
alguien que seguia pudiendo todo.

## La decision: manda la base

De las tres salidas posibles se tomo la tercera (issue #217):

1. Manda la base, la pantalla lista los codigos crudos — fiel pero ilegible.
2. Manda el frontend y se traduce — una tabla de traduccion es un tercer
   artefacto que se desincroniza.
3. **Manda la base, y el texto legible sale de la misma fila.** Un solo
   vocabulario, y `permissions` ya trae `module` y `description` pobladas.

Por eso este endpoint devuelve las tres columnas juntas: sin `descripcion` la
pantalla tendria que inventar el texto, y ahi vuelve a nacer la segunda lista.

## Leer el catalogo no exige permiso

Es una tabla global sin `tenant_id` que solo dice **que permisos existen**, no
quien los tiene. Mismo caso que `/catalog`. Ademas seria incomodo de otra
forma: la pantalla que administra permisos necesita el catalogo para poder
pintarse, y `role.manage` ya protege lo unico que importa, que es escribir.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.organization import Permission
from ..schemas.organization import PermisoDelCatalogo

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("/", response_model=list[PermisoDelCatalogo])
def listar_permisos(db: Session = Depends(get_db)) -> list[PermisoDelCatalogo]:
    """Todos los permisos que la API sabe verificar.

    **Sin paginar, a proposito.** El tope no lo pone quien llama sino la
    siembra: son los permisos que el sistema define, y crecen cuando se agrega
    una capacidad nueva, no cuando una empresa carga datos. Paginarlo obligaria
    a la pantalla a juntar paginas para poder dibujar una sola matriz.

    El orden es por modulo y despues por codigo porque es como se agrupa en la
    pantalla, y asi la interfaz no tiene que reordenar para mostrarlo.

    Se arma campo por campo y no con `from_attributes`: los nombres de la tabla
    estan en ingles (`code`, `module`) y los de la respuesta en castellano, asi
    que un mapeo automatico dejaria los tres campos vacios sin fallar.
    """
    return [
        PermisoDelCatalogo(
            codigo=p.code, modulo=p.module, descripcion=p.description
        )
        for p in db.scalars(
            select(Permission).order_by(Permission.module, Permission.code)
        ).all()
    ]
