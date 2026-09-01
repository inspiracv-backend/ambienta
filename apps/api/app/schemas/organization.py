from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from .base import OrmBase


# ── Country ───────────────────────────────────────────────────────────────

class CountryRead(OrmBase):
    id: int
    iso2: str
    iso3: str
    name: str
    default_timezone: str


# ── Tenant ────────────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    country_id: int
    parent_tenant_id: UUID | None = None
    tenant_type: str = "company"
    rut_tax_id: str
    legal_name: str
    trade_name: str | None = None
    business_activity: str | None = None
    sector_id: int | None = None
    size_bracket: str | None = None
    settings: dict = Field(default_factory=dict)


class TenantRead(OrmBase):
    id: UUID
    country_id: int
    parent_tenant_id: UUID | None
    tenant_type: str
    rut_tax_id: str
    legal_name: str
    trade_name: str | None
    business_activity: str | None
    sector_id: int | None
    size_bracket: str | None
    status: str
    settings: dict
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tiene_perfil_normativo(self) -> bool:
        """Si a esta empresa se le puede calcular normativa aplicable.

        Se devuelve explicito y no se deja que el cliente lo deduzca de
        `sector_id is None`: la pantalla tiene que poder decir "falta declarar
        el sector" en vez de mostrar una lista vacia de normas, que se lee como
        "esta empresa no tiene obligaciones" — lo contrario de lo que pasa.

        El giro en texto libre NO cuenta. Es lo que impide cruzar, y es
        justamente el motivo de que exista `sector_id`.
        """
        return self.sector_id is not None


class TenantUpdate(BaseModel):
    legal_name: str | None = None
    trade_name: str | None = None
    business_activity: str | None = None
    sector_id: int | None = None
    size_bracket: str | None = None
    status: str | None = None
    settings: dict | None = None

    rut_tax_id: str | None = None
    """Identificacion legal de la empresa. **Solo la cambia el Admin Global.**

    Esta en el esquema porque sin ella el Perfil Empresa no se puede completar:
    la aplicacion lo considera completo cuando hay giro Y RUT, y el RUT no habia
    forma de fijarlo. La pantalla ofrecia marcar como completo algo que la API
    no dejaba completar.

    El router rechaza este campo si quien llama no es Admin Global. No basta
    dejarlo aca: el RUT identifica legalmente a la empresa ante la autoridad, y
    que su propio administrador lo cambie permitiria emitir declaraciones a
    nombre de otra. Decision del equipo, 13-ago-2026.
    """


# ── Facility ──────────────────────────────────────────────────────────────

class FacilityCreate(BaseModel):
    code: str
    name: str
    facility_type: str
    address: str | None = None
    region_code: str | None = None
    commune_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    environmental_identifiers: dict = Field(default_factory=dict)


class FacilityRead(OrmBase):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    facility_type: str
    address: str | None
    region_code: str | None
    commune_code: str | None
    latitude: float | None
    longitude: float | None
    environmental_identifiers: dict
    active: bool
    created_at: datetime
    updated_at: datetime


class FacilityUpdate(BaseModel):
    name: str | None = None
    facility_type: str | None = None
    address: str | None = None
    region_code: str | None = None
    commune_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    environmental_identifiers: dict | None = None
    active: bool | None = None


# ── Department ────────────────────────────────────────────────────────────

class DepartmentCreate(BaseModel):
    facility_id: UUID | None = None
    parent_department_id: UUID | None = None
    code: str
    name: str


class DepartmentRead(OrmBase):
    id: UUID
    tenant_id: UUID
    facility_id: UUID | None
    parent_department_id: UUID | None
    code: str
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime


class DepartmentUpdate(BaseModel):
    name: str | None = None
    facility_id: UUID | None = None
    parent_department_id: UUID | None = None
    active: bool | None = None


# ── User ──────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    department_id: UUID | None = None
    rut_tax_id: str | None = None
    email: str
    full_name: str
    user_type: str
    preferences: dict = Field(default_factory=dict)


class UserRead(OrmBase):
    id: UUID
    tenant_id: UUID
    department_id: UUID | None
    rut_tax_id: str | None
    email: str
    full_name: str
    user_type: str
    status: str
    preferences: dict
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = None
    department_id: UUID | None = None
    status: str | None = None
    preferences: dict | None = None


class RegistrarInvitadoPermanente(BaseModel):
    """Convertir a un Cliente Invitado en usuario de la empresa (RF-03).

    `guest_credential_id` identifica a la persona: es lo unico que el acceso de
    invitado guarda de ella, junto con el RUT.

    `full_name` y `email` son opcionales — salen de sus solicitudes si no
    llegan. Se aceptan porque quien administra puede tener que corregir el dato:
    la persona pudo escribir mal su correo al abrir la solicitud, y obligarla a
    arrastrar ese error seria absurdo.

    `department_id` **no** es opcional: la base exige departamento a los tipos
    `internal` y `tenant_admin` (RF-11), asi que sin el la fila la rechaza
    Postgres con un error que no se lee como lo que es.
    """

    guest_credential_id: UUID
    department_id: UUID
    full_name: str | None = None
    email: str | None = None
    #: `internal` por defecto. Registrar a alguien que venia de afuera como
    #: administrador de la empresa deberia ser un acto deliberado, no el camino
    #: mas corto.
    user_type: str = "internal"


class InvitacionEnviada(BaseModel):
    """Lo que quedo hecho al invitar (#139, RF-03).

    No incluye el enlace: Clerk lo manda al correo y **no lo devuelve**, a
    proposito. Un enlace de un solo uso que pasa por nuestra respuesta queda en
    los registros de la API y en el historial del navegador de quien invito.
    """

    user_id: UUID
    email: str
    #: El identificador de Clerk, para rastrear la invitacion en su consola sin
    #: tener que buscarla por correo. `None` si Clerk no lo devolvio.
    clerk_invitation_id: str | None = None


class InvitadoRegistrado(BaseModel):
    user: UserRead
    #: Que paso ademas de crear la cuenta: sus solicitudes cambiaron de dueno y
    #: su acceso de invitado quedo revocado. Se devuelve para que la pantalla lo
    #: diga, en vez de que la persona lo descubra cuando el enlace deja de
    #: funcionarle.
    efectos: list[str] = Field(default_factory=list)


# ── Role ──────────────────────────────────────────────────────────────────

class RoleCreate(BaseModel):
    code: str
    name: str
    is_system: bool = False
    description: str | None = None


class RoleRead(OrmBase):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    is_system: bool
    description: str | None
    created_at: datetime
    updated_at: datetime


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


# ── Permission ────────────────────────────────────────────────────────────

class PermissionRead(OrmBase):
    id: int
    code: str
    module: str
    description: str


# ── RolePermission ────────────────────────────────────────────────────────

class RolePermissionCreate(BaseModel):
    role_id: UUID
    permission_id: int
    granted: bool = True


class RolePermissionRead(OrmBase):
    role_id: UUID
    permission_id: int
    granted: bool


# ── UserRole ──────────────────────────────────────────────────────────────

class UserRoleCreate(BaseModel):
    user_id: UUID
    role_id: UUID
    facility_id: UUID | None = None
    department_id: UUID | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class UserRoleRead(OrmBase):
    user_id: UUID
    role_id: UUID
    tenant_id: UUID
    facility_id: UUID | None
    department_id: UUID | None
    valid_from: datetime
    valid_to: datetime | None


# ── Process ───────────────────────────────────────────────────────────────

class ProcessCreate(BaseModel):
    department_id: UUID | None = None
    parent_process_id: UUID | None = None
    code: str
    name: str
    process_type: str
    description: str | None = None
    responsible_user_id: UUID | None = None
    inputs: list = Field(default_factory=list)
    outputs: list = Field(default_factory=list)
    display_order: int = 0


class ProcessRead(OrmBase):
    id: UUID
    tenant_id: UUID
    department_id: UUID | None
    parent_process_id: UUID | None
    code: str
    name: str
    process_type: str
    description: str | None
    responsible_user_id: UUID | None
    inputs: list
    outputs: list
    display_order: int
    active: bool
    created_at: datetime
    updated_at: datetime


class ProcessUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    responsible_user_id: UUID | None = None
    inputs: list | None = None
    outputs: list | None = None
    display_order: int | None = None
    active: bool | None = None


# ── FacilityProcess ───────────────────────────────────────────────────────

class FacilityProcessCreate(BaseModel):
    facility_id: UUID
    process_id: UUID
    is_primary: bool = False
    scope_notes: str | None = None
    active_from: date | None = None
    active_to: date | None = None


class FacilityProcessRead(OrmBase):
    facility_id: UUID
    process_id: UUID
    tenant_id: UUID
    is_primary: bool
    scope_notes: str | None
    active_from: date | None
    active_to: date | None
    created_at: datetime
    updated_at: datetime


# ── Contract ──────────────────────────────────────────────────────────────

class ContractCreate(BaseModel):
    manager_tenant_id: UUID
    client_tenant_id: UUID
    contract_number: str
    title: str
    start_date: date
    end_date: date | None = None
    scope: dict = Field(default_factory=dict)
    terms_snapshot: dict = Field(default_factory=dict)


class ContractRead(OrmBase):
    id: UUID
    tenant_id: UUID
    manager_tenant_id: UUID
    client_tenant_id: UUID
    contract_number: str
    title: str
    status: str
    start_date: date
    end_date: date | None
    scope: dict
    terms_snapshot: dict
    created_at: datetime
    updated_at: datetime


class ContractUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    end_date: date | None = None
    scope: dict | None = None


class FacilityProcessUpdate(BaseModel):
    """Vigencia y alcance de un proceso dentro de una planta.

    `facility_id` y `process_id` son la clave compuesta y salen del path.
    """

    is_primary: bool | None = None
    scope_notes: str | None = None
    active_from: date | None = None
    active_to: date | None = None


class FacilityProcessCreateAnidado(BaseModel):
    """Cuerpo de `POST /facilities/{facility_id}/processes/{process_id}`.

    Sin `facility_id` ni `process_id`: vienen del path. No se hacen opcionales
    sino que se omiten, porque aceptarlos permitiria enviar un valor que
    contradice la URL — y entonces habria que decidir cual gana, que es una
    ambiguedad que no hace falta tener.
    """

    is_primary: bool = False
    scope_notes: str | None = None
    active_from: date | None = None
    active_to: date | None = None


# ── Permisos (RF-08, RF-12) ───────────────────────────────────────────────

class PermisoEfectivo(BaseModel):
    """Un permiso que la persona tiene, y de donde le viene.

    `origen` importa para la pantalla: quitar un permiso que viene del rol se
    hace de otra forma que quitar uno concedido a esta persona en particular, y
    sin distinguirlos la interfaz ofreceria la accion equivocada.
    """

    codigo: str
    modulo: str
    descripcion: str
    origen: str = Field(description="'rol' o 'individual'")


class PermisosDelUsuario(BaseModel):
    user_id: UUID
    permisos: list[PermisoEfectivo]
    # Se devuelven aparte porque una denegacion no aparece en la lista de lo
    # que puede hacer, y sin verla nadie entiende por que el rol no alcanza.
    denegados: list[str] = Field(
        default_factory=list,
        description="Permisos que el rol concede pero se le denegaron a esta persona",
    )


class PermisoIndividual(BaseModel):
    """Concesion o denegacion sobre una persona concreta."""

    codigo: str
    granted: bool
    # Obligatorio: la spec pide que toda excepcion fuera del rol quede
    # justificada. Un permiso suelto sin motivo es indistinguible de un error
    # de configuracion cuando alguien lo audita seis meses despues.
    reason: str = Field(min_length=3, max_length=500)
