'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Contrato, SubTenant } from '@ambienta/shared';
import { mockSubTenants, mockContratos } from '@/mocks/gestores';

interface GestoresContextValue {
  subTenants: SubTenant[];
  contratos: Contrato[];
  addContrato: (input: {
    subTenantId: string;
    nombre: string;
    fechaInicio: string;
    fechaTermino: string;
    camposCustom: Record<string, string>;
  }) => void;
}

const GestoresContext = createContext<GestoresContextValue | null>(null);

/** Estado en memoria para esta iteración (mismo patrón que los demás stores). */
export function GestoresProvider({ children }: { children: ReactNode }) {
  const [subTenants] = useState<SubTenant[]>(mockSubTenants);
  const [contratos, setContratos] = useState<Contrato[]>(mockContratos);

  function addContrato(input: {
    subTenantId: string;
    nombre: string;
    fechaInicio: string;
    fechaTermino: string;
    camposCustom: Record<string, string>;
  }) {
    const nuevo: Contrato = {
      id: `contrato-${Date.now()}`,
      subTenantId: input.subTenantId,
      nombre: input.nombre,
      fechaInicio: input.fechaInicio,
      fechaTermino: input.fechaTermino,
      camposCustom: input.camposCustom,
    };
    setContratos((prev) => [...prev, nuevo]);
  }

  return (
    <GestoresContext.Provider value={{ subTenants, contratos, addContrato }}>
      {children}
    </GestoresContext.Provider>
  );
}

export function useGestores() {
  const ctx = useContext(GestoresContext);
  if (!ctx) throw new Error('useGestores debe usarse dentro de <GestoresProvider>');
  return ctx;
}
