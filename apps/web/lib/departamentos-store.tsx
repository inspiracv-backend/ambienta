'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Departamento } from '@ambienta/shared';
import { mockDepartamentos } from '@/mocks/departamentos';

interface DepartamentosContextValue {
  departamentos: Departamento[];
  addDepartamento: (tenantId: string, nombre: string) => void;
}

const DepartamentosContext = createContext<DepartamentosContextValue | null>(null);

/** Departamentos del Perfil Empresa (RF-11, RF-12, v1.7) — estado en memoria, mismo patrón que los demás stores. */
export function DepartamentosProvider({ children }: { children: ReactNode }) {
  const [departamentos, setDepartamentos] = useState<Departamento[]>(mockDepartamentos);

  function addDepartamento(tenantId: string, nombre: string) {
    setDepartamentos((prev) => [...prev, { id: `depto-${Date.now()}`, tenantId, nombre }]);
  }

  return (
    <DepartamentosContext.Provider value={{ departamentos, addDepartamento }}>{children}</DepartamentosContext.Provider>
  );
}

export function useDepartamentos() {
  const ctx = useContext(DepartamentosContext);
  if (!ctx) throw new Error('useDepartamentos debe usarse dentro de <DepartamentosProvider>');
  return ctx;
}
