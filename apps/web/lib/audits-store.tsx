'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Audit, NonConformity } from '@ambienta/shared';
import { mockAudits, mockNonConformities } from '@/mocks/audits';

interface AuditsContextValue {
  audits: Audit[];
  nonConformities: NonConformity[];
  addNonConformity: (input: {
    tenantId: string;
    plantId: string;
    auditId?: string;
    hallazgo: string;
    criticidad: NonConformity['criticidad'];
    responsableId: string;
  }) => NonConformity;
  updatePorques: (ncId: string, cincoPorques: string[]) => void;
  closeNonConformity: (ncId: string, responsableId: string) => void;
}

const AuditsContext = createContext<AuditsContextValue | null>(null);

/** Estado en memoria para esta iteración (mismo patrón que los demás stores). */
export function AuditsProvider({ children }: { children: ReactNode }) {
  const [audits] = useState<Audit[]>(mockAudits);
  const [nonConformities, setNonConformities] = useState<NonConformity[]>(mockNonConformities);

  function addNonConformity(input: {
    tenantId: string;
    plantId: string;
    auditId?: string;
    hallazgo: string;
    criticidad: NonConformity['criticidad'];
    responsableId: string;
  }): NonConformity {
    const nc: NonConformity = {
      id: `nc-${Date.now()}`,
      tenantId: input.tenantId,
      plantId: input.plantId,
      auditId: input.auditId,
      hallazgo: input.hallazgo,
      criticidad: input.criticidad,
      estado: 'abierta',
      fechaDeteccion: new Date().toISOString(),
      responsableId: input.responsableId,
      cincoPorques: [],
    };
    setNonConformities((prev) => [...prev, nc]);
    return nc;
  }

  function updatePorques(ncId: string, cincoPorques: string[]) {
    setNonConformities((prev) =>
      prev.map((nc) =>
        nc.id !== ncId
          ? nc
          : { ...nc, cincoPorques, estado: nc.estado === 'abierta' ? 'en_tratamiento' : nc.estado },
      ),
    );
  }

  function closeNonConformity(ncId: string, responsableId: string) {
    setNonConformities((prev) =>
      prev.map((nc) =>
        nc.id !== ncId
          ? nc
          : { ...nc, estado: 'cerrada', cierre: { fecha: new Date().toISOString(), responsableId, firmada: true } },
      ),
    );
  }

  return (
    <AuditsContext.Provider value={{ audits, nonConformities, addNonConformity, updatePorques, closeNonConformity }}>
      {children}
    </AuditsContext.Provider>
  );
}

export function useAudits() {
  const ctx = useContext(AuditsContext);
  if (!ctx) throw new Error('useAudits debe usarse dentro de <AuditsProvider>');
  return ctx;
}
