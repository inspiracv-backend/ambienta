'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { ModuloPlataforma, Plant, Tenant } from '@ambienta/shared';
import { mockTenants } from '@/mocks/tenants';

interface TenantsContextValue {
  tenants: Tenant[];
  setEstado: (tenantId: string, estado: Tenant['estado']) => void;
  setLimiteUsuarios: (tenantId: string, limite: number) => void;
  setModulosActivos: (tenantId: string, modulos: ModuloPlataforma[]) => void;
  updateDatosBasicos: (tenantId: string, datos: { giro: string; direccion: string }) => void;
  addPlant: (tenantId: string, input: { nombre: string; comuna: string; region: string }) => void;
  completarPerfilEmpresa: (tenantId: string) => void;
}

const TenantsContext = createContext<TenantsContextValue | null>(null);

/**
 * Gestión de Tenants (RF-81, Sección L) — Superadmin solo administra los
 * campos de plataforma (estado/límites/módulos), nunca contenido de negocio
 * del tenant (CLAUDE.md). Los mutadores de Perfil Empresa (RF-10 a RF-12,
 * v1.7: datos básicos, plantas, completar) son del Admin Empresa —
 * conviven en el mismo store porque ambos mutan la misma entidad Tenant.
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

  function updateDatosBasicos(tenantId: string, datos: { giro: string; direccion: string }) {
    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, ...datos } : t)));
  }

  function addPlant(tenantId: string, input: { nombre: string; comuna: string; region: string }) {
    setTenants((prev) =>
      prev.map((t) => {
        if (t.id !== tenantId) return t;
        const plant: Plant = { id: `planta-${Date.now()}`, tenantId, ...input };
        return { ...t, plants: [...t.plants, plant] };
      }),
    );
  }

  function completarPerfilEmpresa(tenantId: string) {
    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, perfilEmpresaCompleto: true } : t)));
  }

  return (
    <TenantsContext.Provider
      value={{ tenants, setEstado, setLimiteUsuarios, setModulosActivos, updateDatosBasicos, addPlant, completarPerfilEmpresa }}
    >
      {children}
    </TenantsContext.Provider>
  );
}

export function useTenants() {
  const ctx = useContext(TenantsContext);
  if (!ctx) throw new Error('useTenants debe usarse dentro de <TenantsProvider>');
  return ctx;
}
