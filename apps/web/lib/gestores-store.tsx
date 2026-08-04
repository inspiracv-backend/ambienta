'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Contrato, SubTenant } from '@ambienta/shared';
import { mockSubTenants, mockContratos } from '@/mocks/gestores';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';

interface GestoresContextValue {
  subTenants: SubTenant[];
  contratos: Contrato[];
  loading: boolean;
  addContrato: (input: {
    subTenantId: string;
    nombre: string;
    fechaInicio: string;
    fechaTermino: string;
    camposCustom: Record<string, string>;
  }) => void;
}

const GestoresContext = createContext<GestoresContextValue | null>(null);

export function GestoresProvider({ children }: { children: ReactNode }) {
  const [subTenants] = useState<SubTenant[]>(mockSubTenants);
  const [contratos, setContratos] = useState<Contrato[]>(mockContratos);
  const [loading] = useState(false);
  const registrar = useRegistrarAuditoria();

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

    const subTenant = subTenants.find((s) => s.id === input.subTenantId);

    registrar({
      entidadTipo: 'contrato',
      entidadId: nuevo.id,
      entidadLabel: `${nuevo.nombre} — ${subTenant?.nombre ?? input.subTenantId}`,
      accion: 'creado',
      resumen: `Creó el contrato con ${subTenant?.nombre ?? 'el cliente'}`,
      cambios: [
        { campo: 'Vigencia', antes: null, despues: `${input.fechaInicio} a ${input.fechaTermino}` },
        ...(Object.keys(input.camposCustom).length > 0
          ? [{ campo: 'Campos adicionales', antes: null, despues: Object.keys(input.camposCustom).join(', ') }]
          : []),
      ],
    });
  }

  return (
    <GestoresContext.Provider value={{ subTenants, contratos, loading, addContrato }}>
      {children}
    </GestoresContext.Provider>
  );
}

export function useGestores() {
  const ctx = useContext(GestoresContext);
  if (!ctx) throw new Error('useGestores debe usarse dentro de <GestoresProvider>');
  return ctx;
}
