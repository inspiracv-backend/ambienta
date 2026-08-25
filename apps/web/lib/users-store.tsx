'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { DescriptorCargo, Permiso, Role, User, UserEstado } from '@ambienta/shared';
import { PERMISOS_POR_DEFECTO } from '@ambienta/shared';
import { mockUsers } from '@/mocks/users';
import { useToast } from '@/lib/toast-store';
import { api, mensajeDeError } from '@/lib/api-client';
import { CLERK_HABILITADO } from '@/lib/clerk-config';

interface UsersContextValue {
  users: User[];
  loading: boolean;
  inviteUser: (input: {
    tenantId: string | null;
    nombre: string;
    email: string;
    role: Role;
    plantIds: string[];
    departamentoId: string | null;
  }) => User;
  updateRole: (userId: string, role: Role) => void;
  updatePlants: (userId: string, plantIds: string[]) => void;
  updateDepartamento: (userId: string, departamentoId: string | null) => void;
  updateNombre: (userId: string, nombre: string) => void;
  updateDescriptorCargo: (userId: string, descriptor: DescriptorCargo) => void;
  updatePermisos: (userId: string, permisos: Permiso[]) => void;
  setEstado: (userId: string, estado: UserEstado) => void;
}

const UsersContext = createContext<UsersContextValue | null>(null);

const USER_TYPE_TO_ROLE: Record<string, Role> = {
  platform_admin: 'superadmin',
  tenant_admin: 'admin_empresa',
  internal: 'usuario_interno',
  guest: 'cliente_invitado',
  manager: 'gestor',
};

function mapApiUser(raw: Record<string, unknown>): User | null {
  try {
    const role = USER_TYPE_TO_ROLE[String(raw.user_type)] ?? 'usuario_interno';
    return {
      id: String(raw.id),
      tenantId: raw.tenant_id ? String(raw.tenant_id) : null,
      nombre: String(raw.full_name ?? raw.display_name ?? ''),
      email: String(raw.email ?? ''),
      role,
      permisos: PERMISOS_POR_DEFECTO[role],
      plantIds: [],
      departamentoId: raw.department_id ? String(raw.department_id) : null,
      estado: raw.status === 'active' ? 'activo' : 'invitado',
      ultimaActividad: raw.last_login_at ? String(raw.last_login_at) : null,
    };
  } catch {
    return null;
  }
}

export function UsersProvider({ children }: { children: ReactNode }) {
  const [users, setUsers] = useState<User[]>(mockUsers);
  const { mostrarToast } = useToast();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    /**
     * Con Clerk el tenant lo fija el JWT, asi que `/users/` ya viene acotado
     * por RLS a la empresa de quien pregunta y **no hay que recorrer tenants**:
     * hacerlo pediria N veces la misma lista, porque la API ignora
     * X-Tenant-Id cuando hay token (apps/api/app/deps.py).
     *
     * Sin Clerk no existe sesion que declare un tenant, asi que se enumeran
     * todos para poder cambiar de rol con el DevRoleSwitcher.
     */
    async function fetchUsuariosDelTenant() {
      const data = await api.get<Record<string, unknown>[]>('/users/');
      return data.map(mapApiUser).filter((u): u is User => u !== null);
    }

    async function fetchUsuariosDeTodosLosTenants() {
      const tenants = await api.get<{ id: string }[]>('/tenants/');
      const seen = new Set<string>();
      const allUsers: User[] = [];
      for (const tenant of tenants) {
        try {
          const data = await api.get<Record<string, unknown>[]>('/users/', { tenantId: tenant.id });
          const mapped = data.map(mapApiUser).filter((u): u is User => u !== null);
          for (const u of mapped) {
            if (!seen.has(u.id)) {
              seen.add(u.id);
              allUsers.push(u);
            }
          }
        } catch {
          // skip tenant if users fail
        }
      }
      return allUsers;
    }

    async function fetchAllUsers() {
      try {
        const cargados = CLERK_HABILITADO
          ? await fetchUsuariosDelTenant()
          : await fetchUsuariosDeTodosLosTenants();
        if (!cancelled && cargados.length > 0) setUsers(cargados);
      } catch {
        // Fallback a mocks
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchAllUsers();
    return () => { cancelled = true; };
  }, []);

  function inviteUser(input: {
    tenantId: string | null;
    nombre: string;
    email: string;
    role: Role;
    plantIds: string[];
    departamentoId: string | null;
  }): User {
    const nuevo: User = {
      id: `user-${Date.now()}`,
      tenantId: input.tenantId,
      nombre: input.nombre,
      email: input.email,
      role: input.role,
      permisos: PERMISOS_POR_DEFECTO[input.role],
      plantIds: input.plantIds,
      departamentoId: input.departamentoId,
      estado: 'invitado',
      ultimaActividad: null,
    };
    setUsers((prev) => [...prev, nuevo]);

    if (input.tenantId) {
      // `full_name`, no `display_name`. **La API exige `full_name` y no lo
      // tenia**, asi que esta llamada devolvia 422 y el `.catch` vacio se lo
      // tragaba: la invitacion se veia hecha en pantalla y no creaba a nadie.
      api
        .post(
          '/users/',
          {
            full_name: input.nombre,
            email: input.email,
            user_type: input.role === 'admin_empresa' ? 'tenant_admin' : 'internal',
            department_id: input.departamentoId ?? null,
          },
          { tenantId: input.tenantId },
        )
        .catch((error) => {
          setUsers((prev) => prev.filter((u) => u.id !== nuevo.id));
          mostrarToast({
            tipo: 'error',
            mensaje: 'No se pudo invitar a la persona',
            descripcion: mensajeDeError(error),
          });
        });
    }

    return nuevo;
  }

  /**
   * **No llega a la base, y ya no finge que sí.**
   *
   * Antes mandaba `user_type` a `PATCH /users/{id}`. Ese campo **no está en
   * `UserUpdate`**, así que la API respondía 200 y no cambiaba nada: el rol
   * volvía al recargar y ningún error lo delataba.
   *
   * Pero el arreglo no es renombrar el campo. `users.user_type` es una
   * etiqueta; **los permisos salen de `user_roles`**, que es otra tabla con
   * su propia vigencia. Escribir `user_type` cambiaría lo que dice la ficha
   * sin cambiar lo que la persona puede hacer — que es exactamente el tipo de
   * mentira que este repo ya pagó caro.
   *
   * El endpoint que asigna rol contra `user_roles` es el alcance de #140. Hasta
   * entonces esto queda en local y **se dice en pantalla**, en vez de escribir
   * a un campo que no manda.
   */
  function updateRole(userId: string, role: Role) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role } : u)));
    mostrarToast({
      tipo: 'info',
      mensaje: 'El cambio de rol no se guardó',
      descripcion:
        'Cambiar el rol de forma permanente todavía no está conectado. El permiso efectivo lo define user_roles en la base.',
    });
  }

  /**
   * **No llega a la base, y el motivo es un desacuerdo de modelo.**
   *
   * No es que falte el endpoint. El único lugar donde la base vincula a una
   * persona con una planta es `user_roles.facility_id`, y esa tabla tiene
   * clave primaria `(user_id, role_id)`: **una fila por rol, con UNA planta**.
   *
   * Acá el campo es `plantIds`, en plural. Los dos modelos no se pueden
   * conciliar escribiendo código: o una persona pertenece a varias plantas —y
   * entonces falta una tabla `user_facilities`, o la PK de `user_roles` está
   * mal— o pertenece a una sola, y el plural de esta pantalla sobra.
   *
   * Es una decisión de negocio con consecuencia de esquema, no una tarea de
   * frontend. Mientras no se tome, el mapper de lectura arma `plantIds: []`
   * para todos y cualquier escritura se perdería al recargar.
   */
  function updatePlants(userId: string, plantIds: string[]) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, plantIds } : u)));
  }

  function updateDepartamento(userId: string, departamentoId: string | null) {
    const anterior = users.find((u) => u.id === userId);
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, departamentoId } : u)));

    if (!anterior?.tenantId) return;
    const previo = anterior.departamentoId;

    api
      .patch(`/users/${userId}`, { department_id: departamentoId }, { tenantId: anterior.tenantId })
      .catch((error) => {
        setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, departamentoId: previo } : u)));
        mostrarToast({
          tipo: 'error',
          mensaje: 'No se pudo cambiar el departamento',
          descripcion: mensajeDeError(error),
        });
      });
  }

  function updateNombre(userId: string, nombre: string) {
    const anterior = users.find((u) => u.id === userId);
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, nombre } : u)));
    if (!anterior?.tenantId) return;

    // `full_name`, no `display_name`. Con el nombre equivocado la API
    // respondia **200 sin cambiar nada** —Pydantic descarta los campos que no
    // declara y `exclude_unset` deja el UPDATE vacio—, que es peor que un 422:
    // nadie revierte y nadie se entera hasta recargar.
    api
      .patch(`/users/${userId}`, { full_name: nombre }, { tenantId: anterior.tenantId })
      .catch((error) => {
        setUsers((prev) =>
          prev.map((u) => (u.id === userId ? { ...u, nombre: anterior.nombre } : u)),
        );
        mostrarToast({
          tipo: 'error',
          mensaje: 'No se pudo cambiar el nombre',
          descripcion: mensajeDeError(error),
        });
      });
  }

  /**
   * **No llega a la base:** `UserUpdate` acepta `full_name`, `department_id`,
   * `status` y `preferences`. El descriptor de cargo no esta entre ellos.
   */
  function updateDescriptorCargo(userId: string, descriptorCargo: DescriptorCargo) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, descriptorCargo } : u)));
  }

  /**
   * **No llega a la base.** Los permisos individuales tienen tabla
   * (`user_permissions`) pero **ninguna API**: dependen de que se apruebe el
   * cambio de RBAC, hoy en 0 de 33 tareas.
   */
  function updatePermisos(userId: string, permisos: Permiso[]) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, permisos } : u)));
  }

  function setEstado(userId: string, estado: UserEstado) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, estado } : u)));
    const user = users.find((u) => u.id === userId);
    if (user?.tenantId) {
      api.patch(`/users/${userId}`, {
        status: estado === 'activo' ? 'active' : 'inactive',
      }, { tenantId: user.tenantId }).catch(() => {});
    }
  }

  return (
    <UsersContext.Provider
      value={{
        users,
        loading,
        inviteUser,
        updateRole,
        updatePlants,
        updateDepartamento,
        updateNombre,
        updateDescriptorCargo,
        updatePermisos,
        setEstado,
      }}
    >
      {children}
    </UsersContext.Provider>
  );
}

export function useUsers() {
  const ctx = useContext(UsersContext);
  if (!ctx) throw new Error('useUsers debe usarse dentro de <UsersProvider>');
  return ctx;
}
