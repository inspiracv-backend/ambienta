from pydantic import BaseModel

from ..models.organization import (
    Contract,
    Department,
    Facility,
    Permission,
    Process,
    Role,
    Tenant,
    User,
)
from ..schemas.organization import (
    ContractCreate,
    ContractUpdate,
    DepartmentCreate,
    DepartmentUpdate,
    FacilityCreate,
    FacilityUpdate,
    ProcessCreate,
    ProcessUpdate,
    RoleCreate,
    RoleUpdate,
    TenantCreate,
    TenantUpdate,
    UserCreate,
    UserUpdate,
)
from .base import CRUDBase

crud_tenant = CRUDBase[Tenant, TenantCreate, TenantUpdate](Tenant)
crud_facility = CRUDBase[Facility, FacilityCreate, FacilityUpdate](Facility)
crud_department = CRUDBase[Department, DepartmentCreate, DepartmentUpdate](Department)
crud_user = CRUDBase[User, UserCreate, UserUpdate](User)
crud_role = CRUDBase[Role, RoleCreate, RoleUpdate](Role)
crud_permission = CRUDBase[Permission, BaseModel, BaseModel](Permission)
crud_process = CRUDBase[Process, ProcessCreate, ProcessUpdate](Process)
crud_contract = CRUDBase[Contract, ContractCreate, ContractUpdate](Contract)
