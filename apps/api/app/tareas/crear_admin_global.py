"""Crear al primer Admin Global. Se corre **una vez**, al desplegar.

    docker compose exec api python -m app.tareas crear-admin-global \\
        --correo persona@ambienta.cl --nombre "Nombre Apellido" \\
        --razon-social "Ambienta SpA" --rut 76.123.456-7

## Por que hace falta

En produccion la base arranca **sin ninguna empresa ni usuario**:
`docker-compose.prod.yml` no carga el seed de demo. Dar de alta una empresa
exige ser Admin Global (`exigir_admin_global`), y un Admin Global solo lo podia
crear... nadie. Medido el 14-sep: tampoco la base de desarrollo tiene uno — ahi
no se nota porque sin Clerk la API confia en quien llama.

## Que deja hecho

1. La empresa de la plataforma (`tenant_type = 'platform'`), o la que ya exista.
   `users.tenant_id` es NOT NULL: el Admin Global pertenece a una empresa, y su
   sesion la declara.
2. Sus roles de sistema, como cualquier empresa nueva.
3. La persona como `platform_admin`, con `admin_empresa` en esa empresa — la
   guarda de rutas pide `company_profile.write` para `POST /tenants/` y
   `role.manage` para invitar, y sin rol recibiria 403.
4. La invitacion de Clerk con el `tenant_id` de la plataforma.

Todo en una transaccion: si Clerk no responde, no queda nada.

## Lo que NO hace, a proposito

**Se niega si ya hay un Admin Global.** Sumar gente al equipo de plataforma es
RF-84, y el rol de Soporte sigue sin definirse; este comando no es la puerta
trasera para eso. Tampoco inventa un RUT: sin empresa de plataforma, lo pide.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import declarar
from ..models.organization import Tenant, User
from ..services import catalogos_de_mejora as svc_catalogos
from ..services import crm as svc_crm
from ..services import roles_de_sistema as svc_roles
from ..services.invitacion_de_usuario import crear_cuenta_e_invitar


class ErrorDeArranque(Exception):
    """No corresponde crear al Admin Global con lo que se pidio."""


class YaHayAdminGlobal(ErrorDeArranque):
    """Ya existe uno: este comando no suma gente al equipo de plataforma."""


@dataclass
class AdminCreado:
    tenant_id: UUID
    usuario_id: UUID
    empresa_nueva: bool
    clerk_invitation_id: str | None


def _admin_existente(db: Session, plataformas: list[Tenant]) -> User | None:
    """Busca empresa por empresa: `users` lleva RLS y sin declarar ve cero filas."""
    for empresa in plataformas:
        declarar(db, empresa.id)
        fila = db.scalar(
            select(User).where(
                User.tenant_id == empresa.id,
                User.user_type == "platform_admin",
                User.deleted_at.is_(None),
            )
        )
        if fila is not None:
            return fila
    return None


def crear(
    db: Session,
    *,
    correo: str,
    nombre: str,
    razon_social: str | None = None,
    rut: str | None = None,
) -> AdminCreado:
    """Deja creado e invitado al primer Admin Global. No confirma: eso es de quien llama."""
    plataformas = list(
        db.scalars(
            select(Tenant)
            .where(Tenant.tenant_type == "platform", Tenant.deleted_at.is_(None))
            .order_by(Tenant.created_at)
        ).all()
    )

    existente = _admin_existente(db, plataformas)
    if existente is not None:
        raise YaHayAdminGlobal(
            f"Ya hay un Admin Global ({existente.email}). Sumar a alguien al equipo "
            "de plataforma no se hace con este comando (RF-84)."
        )

    empresa_nueva = not plataformas
    if plataformas:
        empresa = plataformas[0]
    else:
        if not razon_social or not rut:
            raise ErrorDeArranque(
                "No existe la empresa de la plataforma: indica --razon-social y --rut. "
                "No se inventa un RUT."
            )
        empresa = Tenant(
            country_id=1,
            tenant_type="platform",
            rut_tax_id=rut.strip(),
            legal_name=razon_social.strip(),
        )
        db.add(empresa)
        db.flush()

    declarar(db, empresa.id)
    svc_roles.sembrar_roles_de_sistema(db, empresa.id)
    svc_crm.sembrar_etapas_por_defecto(db, empresa.id)
    svc_catalogos.sembrar_por_defecto(db, empresa.id)

    usuario, respuesta = crear_cuenta_e_invitar(
        db,
        empresa.id,
        full_name=nombre.strip(),
        email=correo.strip(),
        user_type="platform_admin",
        department_id=None,
        role_code="admin_empresa",
    )
    return AdminCreado(
        tenant_id=empresa.id,
        usuario_id=usuario.id,
        empresa_nueva=empresa_nueva,
        clerk_invitation_id=str(respuesta.get("id") or "") or None,
    )
