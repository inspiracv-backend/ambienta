'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { ModuloPlataforma, Tenant } from '@ambienta/shared';
import { mockTenants } from '@/mocks/tenants';

interface TenantsContextValue {
  tenants: Tenant[];
  setEstado: (tenantId: string, estado: Tenant['estado']) => void;
  setLimiteUsuarios: (tenantId: string, limite: number) => void;
  setModulosActivos: (tenantId: string, modulos: ModuloPlataforma[]) => void;
}

const TenantsContext = createContext<TenantsContextValue | null>(null);

/**
 * Gestión de Tenants (RF-59, Sección L) — Superadmin solo administra estos
 * campos de plataforma, nunca contenido de negocio del tenant (CLAUDE.md).
 */
export function TenantsProvider({ children }: { children: ReactNode }) {
  const [tenants, setTenants] = useState<Tenant[]>(mockTenants);

  function setEstado(tenantId: string, estado: Tenant['estado']) {
    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, estado } : t)));
  }

  function setLimiteUsuarios(tenantId: string, limite: number) {
    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, limiteUsuarios: limite } : t)));
  }

  function setModulosActivos(tenantId: string, modulos: ModuloPlataforma[]) {
    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, modulosActivos: modulos } : t)));
  }

  return (
    <TenantsContext.Provider value={{ tenants, setEstado, setLimiteUsuarios, setModulosActivos }}>
      {children}
    </TenantsContext.Provider>
  );
}

export function useTenants() {
  const ctx = useContext(TenantsContext);
  if (!ctx) throw new Error('useTenants debe usarse dentro de <TenantsProvider>');
  return ctx;
}
