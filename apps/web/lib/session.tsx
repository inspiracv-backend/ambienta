'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { User } from '@ambienta/shared';
import { useUsers } from '@/lib/users-store';

/**
 * Sesión simulada para esta iteración (sin backend real todavía).
 * `user` se deriva en vivo de `UsersProvider` (no de una copia propia) para
 * que editar el nombre/rol/estado de un usuario (S-41/S-42, Sección N) se
 * refleje de inmediato en `AppHeader` y en el resto de la app sin duplicar
 * el dato. Integración real: reemplazar por JWT + Microsoft/Google OAuth
 * vía apps/api cuando exista la spec de OpenSpec aprobada para auth.
 */
interface SessionContextValue {
  user: User | null;
  login: (userId: string) => void;
  logout: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);
const STORAGE_KEY = 'ambienta.mockUserId';

export function SessionProvider({ children }: { children: ReactNode }) {
  const { users } = useUsers();
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    const storedId = window.localStorage.getItem(STORAGE_KEY);
    if (storedId) setUserId(storedId);
  }, []);

  const user = users.find((u) => u.id === userId) ?? null;

  function login(userIdToLogin: string) {
    const found = users.find((u) => u.id === userIdToLogin) ?? null;
    if (found) {
      setUserId(found.id);
      window.localStorage.setItem(STORAGE_KEY, found.id);
    } else {
      setUserId(null);
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }

  function logout() {
    setUserId(null);
    window.localStorage.removeItem(STORAGE_KEY);
  }

  return <SessionContext.Provider value={{ user, login, logout }}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession debe usarse dentro de <SessionProvider>');
  return ctx;
}
