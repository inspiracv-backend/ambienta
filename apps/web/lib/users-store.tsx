'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { DescriptorCargo, Permiso, Role, User, UserEstado } from '@ambienta/shared';
import { PERMISOS_POR_DEFECTO } from '@ambienta/shared';
import { mockUsers } from '@/mocks/users';
import { api } from '@/lib/api-client';
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
      api.post('/users/', {
        display_name: input.nombre,
        email: input.email,
        user_type: input.role === 'admin_empresa' ? 'tenant_admin' : 'internal',
      }, { tenantId: input.tenantId }).catch(() => {});
    }

    return nuevo;
  }

  function updateRole(userId: string, role: Role) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role } : u)));
    const user = users.find((u) => u.id === userId);
    if (user?.tenantId) {
      api.patch(`/users/${userId}`, {
        user_type: role === 'admin_empresa' ? 'tenant_admin' : 'internal',
      }, { tenantId: user.tenantId }).catch(() => {});
    }
  }

  function updatePlants(userId: string, plantIds: string[]) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, plantIds } : u)));
  }

  function updateDepartamento(userId: string, departamentoId: string | null) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, departamentoId } : u)));
  }

  function updateNombre(userId: string, nombre: string) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, nombre } : u)));
    const user = users.find((u) => u.id === userId);
    if (user?.tenantId) {
      api.patch(`/users/${userId}`, { display_name: nombre }, { tenantId: user.tenantId }).catch(() => {});
    }
  }

  function updateDescriptorCargo(userId: string, descriptorCargo: DescriptorCargo) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, descriptorCargo } : u)));
  }

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
