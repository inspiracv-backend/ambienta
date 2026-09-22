"""Los cuatro roles con que nace toda empresa.

## El defecto que esto cierra

`db/09_roles_por_codigo.sql` crea los roles con un `CROSS JOIN tenants`, que
corre **una sola vez**. En desarrollo no se notaba: el seed ya trae dos empresas
y las dos quedaron con sus cuatro roles. Pero `docker-compose.prod.yml` no carga
el seed, asi que en produccion esa migracion corre **con cero empresas** y no
siembra nada — y `POST /tenants/` sembraba etapas del CRM y catalogos de mejora,
no roles.

Consecuencia: toda empresa dada de alta desde la plataforma nacia **sin ningun
rol**. Con la guarda de permisos conectada eso es 403 en todas las rutas,
incluido su administrador — que ademas no podia asignarse un rol, porque no
habia ninguno que asignar. Es la misma familia que las etapas del CRM, y el
sintoma tampoco apunta a la causa.

## Las reglas son las de la migracion, no otras

Dos listas distintas darian permisos distintos segun cuando nacio la empresa, y
la diferencia solo se veria comparando dos cuentas. Por eso
`test_roles_de_sistema.py` **lee `db/09`** y exige que las listas explicitas
coincidan, igual que la prueba de las etapas del CRM.

- `admin_empresa`: todo menos `platform.*`.
- `encargado_ambiental` y `operador`: las listas de la migracion.
- `servicio_lectura`: todo lo que termina en `.read`.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.organization import Permission, Role, RolePermission

#: `(codigo, nombre, descripcion)`, literales de `db/09`.
ROLES: list[tuple[str, str, str]] = [
    (
        "admin_empresa",
        "Administrador de Empresa",
        "Acceso total a la gestion de la empresa, incluidos usuarios y permisos",
    ),
    (
        "encargado_ambiental",
        "Encargado Ambiental",
        "Gestion de cumplimiento y obligaciones. No administra usuarios",
    ),
    (
        "operador",
        "Operador",
        "Lectura y ejecucion de las tareas que se le asignan",
    ),
    (
        "servicio_lectura",
        "Servicio (solo lectura)",
        "Integraciones y servicio de IA. Solo consulta; no modifica nada.",
    ),
]

PERMISOS_ENCARGADO: frozenset[str] = frozenset({
    "company_profile.read",
    "legal_matrix.read", "legal_matrix.write", "legal_matrix.article.evaluate",
    "catalog.read",
    "obligation.read", "obligation.write", "obligation.submit",
    "task.read", "task.write",
    "audit.read", "audit.write",
    "nonconformity.read", "nonconformity.write",
    "action_plan.read", "action_plan.write",
    "environmental_aspect.read", "environmental_aspect.write",
    "risk_opportunity.read", "risk_opportunity.write",
    "equipment.read", "equipment.write",
    "document.read", "document.write",
    "report.generate", "chatbot.use",
    "user.read",
})

PERMISOS_OPERADOR: frozenset[str] = frozenset({
    "company_profile.read",
    "legal_matrix.read", "catalog.read",
    "obligation.read",
    "task.read", "task.write",
    "audit.read", "nonconformity.read", "action_plan.read",
    "document.read", "chatbot.use",
})


def permisos_de(codigo_rol: str, catalogo: list[str]) -> set[str]:
    """Que permisos del catalogo le tocan a ese rol de sistema."""
    if codigo_rol == "admin_empresa":
        return {p for p in catalogo if not p.startswith("platform.")}
    if codigo_rol == "encargado_ambiental":
        return PERMISOS_ENCARGADO & set(catalogo)
    if codigo_rol == "operador":
        return PERMISOS_OPERADOR & set(catalogo)
    if codigo_rol == "servicio_lectura":
        return {p for p in catalogo if p.endswith(".read")}
    raise ValueError(f"{codigo_rol} no es un rol de sistema")


def sembrar_roles_de_sistema(db: Session, tenant_id: UUID) -> int:
    """Deja a la empresa con sus cuatro roles y sus permisos. Idempotente.

    Idempotente por codigo, como la migracion (`ON CONFLICT DO NOTHING`): un rol
    que ya existe **no se toca**, porque la empresa pudo haberle cambiado los
    permisos y resembrar se los devolveria sin que nadie lo decidiera. Tambien
    sirve para reparar una empresa que quedo sin roles.

    Necesita el tenant declarado: `roles` lleva RLS. Devuelve cuantos creo.
    """
    permisos = {
        codigo: pid for pid, codigo in db.execute(select(Permission.id, Permission.code)).all()
    }
    # Sin filtrar los borrados: `uq_roles_tenant_code` los incluye, y un rol
    # retirado con el mismo codigo haria fallar el alta entera.
    existentes = set(
        db.scalars(select(Role.code).where(Role.tenant_id == tenant_id)).all()
    )

    creados = 0
    for codigo, nombre, descripcion in ROLES:
        if codigo in existentes:
            continue
        rol = Role(
            tenant_id=tenant_id,
            code=codigo,
            name=nombre,
            is_system=True,
            description=descripcion,
        )
        db.add(rol)
        db.flush()
        for permiso in sorted(permisos_de(codigo, list(permisos))):
            db.add(RolePermission(role_id=rol.id, permission_id=permisos[permiso], granted=True))
        creados += 1

    db.flush()
    return creados
