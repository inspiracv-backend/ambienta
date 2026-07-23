'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { User } from '@ambienta/shared';
import { mockUsers } from '@/mocks/users';

/**
 * Sesión simulada para esta iteración (sin backend real todavía).
 * Integración real: reemplazar por JWT + Microsoft/Google OAuth vía
 * apps/api cuando exista la spec de OpenSpec aprobada para auth.
 */
interface SessionContextValue {
  user: User | null;
  login: (userId: string) => void;
  logout: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);
const STORAGE_KEY = 'ambienta.mockUserId';

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const storedId = window.localStorage.getItem(STORAGE_KEY);
    if (storedId) {
      setUser(mockUsers.find((u) => u.id === storedId) ?? null);
    }
  }, []);

  function login(userId: string) {
    const found = mockUsers.find((u) => u.id === userId) ?? null;
    setUser(found);
    if (found) window.localStorage.setItem(STORAGE_KEY, found.id);
  }

  function logout() {
    setUser(null);
    window.localStorage.removeItem(STORAGE_KEY);
  }

  return <SessionContext.Provider value={{ user, login, logout }}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession debe usarse dentro de <SessionProvider>');
  return ctx;
}
