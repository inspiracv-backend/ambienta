import type { ReactNode } from 'react';
import type { Role, User } from '@ambienta/shared';
import { mockUsers } from '@/mocks/users';

/**
 * Helpers compartidos por los tests de componentes.
 *
 * Nota sobre el router: `vi.mock` se eleva al inicio del archivo donde se
 * declara, así que el mock de `next/navigation` va en cada archivo de test,
 * no aquí. Este módulo solo trae lo que se puede compartir sin hoisting.
 */

export const STORAGE_KEY = 'ambienta.mockUserId';

export function usuarioConRol(role: Role): User {
  const encontrado = mockUsers.find((u) => u.role === role);
  if (!encontrado) throw new Error(`No hay usuario mock con el rol ${role}`);
  return encontrado;
}

/**
 * Deja la sesión iniciada como el primer usuario mock de ese rol. La sesión
 * vive en localStorage (`lib/session.tsx`) y se deriva de `UsersProvider`,
 * así que sembrar la clave antes de montar el árbol basta.
 */
export function iniciarSesionComo(role: Role): User {
  const user = usuarioConRol(role);
  window.localStorage.setItem(STORAGE_KEY, user.id);
  return user;
}

export function Contenido({ children = 'contenido protegido' }: { children?: ReactNode }) {
  return <div data-testid="contenido">{children}</div>;
}
