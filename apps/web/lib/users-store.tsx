'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { DescriptorCargo, Role, User, UserEstado } from '@ambienta/shared';
import { mockUsers } from '@/mocks/users';

interface UsersContextValue {
  users: User[];
  inviteUser: (input: {
    /** `null` para usuarios de plataforma (equipo interno), que no pertenecen a ninguna empresa. */
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
  setEstado: (userId: string, estado: UserEstado) => void;
}

const UsersContext = createContext<UsersContextValue | null>(null);

/**
 * Gestión de Usuarios y Roles (RF-08, S-41, Sección N) — estado en memoria,
 * mismo patrón que los demás stores. No hay envío real de email de
 * invitación (depende de Resend, ver gap en Sección J): "invitar" crea el
 * registro directo con `estado: 'invitado'`.
 *
 * ⚠️ **Única excepción al registro de auditoría en el store.** Los demás
 * stores llaman a `useRegistrarAuditoria()` internamente, para que ninguna
 * ruta de mutación pueda olvidarse. Aquí no se puede: este provider está por
 * encima de `SessionProvider` (la sesión deriva su usuario de aquí), así que
 * no tiene acceso al actor sin crear un ciclo de dependencias. El registro lo
 * hacen sus pantallas — `UsersManagementTable` y `UserProfileView` — usando
 * el helper `registrarCambioDeUsuario` de `lib/user-audit.ts`, que centraliza
 * el formato para que no se desincronicen entre sí.
 */
export function UsersProvider({ children }: { children: ReactNode }) {
  const [users, setUsers] = useState<User[]>(mockUsers);

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
      plantIds: input.plantIds,
      departamentoId: input.departamentoId,
      estado: 'invitado',
      ultimaActividad: null,
    };
    setUsers((prev) => [...prev, nuevo]);
    return nuevo;
  }

  function updateRole(userId: string, role: Role) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role } : u)));
  }

  function updatePlants(userId: string, plantIds: string[]) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, plantIds } : u)));
  }

  function updateDepartamento(userId: string, departamentoId: string | null) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, departamentoId } : u)));
  }

  function updateNombre(userId: string, nombre: string) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, nombre } : u)));
  }

  function updateDescriptorCargo(userId: string, descriptorCargo: DescriptorCargo) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, descriptorCargo } : u)));
  }

  function setEstado(userId: string, estado: UserEstado) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, estado } : u)));
  }

  return (
    <UsersContext.Provider
      value={{ users, inviteUser, updateRole, updatePlants, updateDepartamento, updateNombre, updateDescriptorCargo, setEstado }}
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
