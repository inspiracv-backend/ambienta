'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Audit, NonConformity } from '@ambienta/shared';
import { mockAudits, mockNonConformities } from '@/mocks/audits';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useUsers } from '@/lib/users-store';
import { CRITICIDAD_LABEL, NC_ESTADO_LABEL } from '@/lib/audit-status';

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

/**
 * Estado en memoria para esta iteración (mismo patrón que los demás stores).
 *
 * El cierre de una no conformidad es el otro flujo donde el audit log deja de
 * ser conveniencia y pasa a ser requisito: RF-49 exige firma del responsable
 * y fecha, y RF-32 pide además saber "quién aprobó". Por eso el cierre se
 * registra con `aprobadoPor`, que es el campo que responde esa pregunta.
 */
export function AuditsProvider({ children }: { children: ReactNode }) {
  const [audits] = useState<Audit[]>(mockAudits);
  const [nonConformities, setNonConformities] = useState<NonConformity[]>(mockNonConformities);
  const registrar = useRegistrarAuditoria();
  const { users } = useUsers();

  /** Etiqueta corta y estable del hallazgo, para no volcar párrafos al historial. */
  function etiqueta(nc: NonConformity): string {
    return nc.hallazgo.length > 70 ? `${nc.hallazgo.slice(0, 70)}…` : nc.hallazgo;
  }

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

    registrar({
      entidadTipo: 'no_conformidad',
      entidadId: nc.id,
      entidadLabel: etiqueta(nc),
      tenantId: input.tenantId,
      accion: 'creado',
      resumen: 'Registró el hallazgo',
      cambios: [
        { campo: 'Criticidad', antes: null, despues: CRITICIDAD_LABEL[input.criticidad] },
        { campo: 'Estado', antes: null, despues: NC_ESTADO_LABEL.abierta },
        ...(input.auditId ? [{ campo: 'Auditoría de origen', antes: null, despues: input.auditId }] : []),
      ],
      motivo: input.hallazgo,
    });

    return nc;
  }

  function updatePorques(ncId: string, cincoPorques: string[]) {
    const anterior = nonConformities.find((nc) => nc.id === ncId);
    if (!anterior) return;

    const nuevoEstado = anterior.estado === 'abierta' ? 'en_tratamiento' : anterior.estado;

    setNonConformities((prev) =>
      prev.map((nc) => (nc.id !== ncId ? nc : { ...nc, cincoPorques, estado: nuevoEstado })),
    );

    const causaRaiz = cincoPorques.filter(Boolean).at(-1) ?? null;

    registrar({
      entidadTipo: 'no_conformidad',
      entidadId: ncId,
      entidadLabel: etiqueta(anterior),
      tenantId: anterior.tenantId,
      accion: 'actualizado',
      resumen: 'Actualizó el análisis de causa raíz (5 ¿Por qué?)',
      cambios: [
        {
          campo: 'Porqués completados',
          antes: String(anterior.cincoPorques.filter(Boolean).length),
          despues: String(cincoPorques.filter(Boolean).length),
        },
        ...(nuevoEstado !== anterior.estado
          ? [{ campo: 'Estado', antes: NC_ESTADO_LABEL[anterior.estado], despues: NC_ESTADO_LABEL[nuevoEstado] }]
          : []),
      ],
      // La causa raíz es la conclusión del análisis: es el "por qué" de RF-32.
      ...(causaRaiz ? { motivo: `Causa raíz identificada: ${causaRaiz}` } : {}),
    });
  }

  function closeNonConformity(ncId: string, responsableId: string) {
    const anterior = nonConformities.find((nc) => nc.id === ncId);
    if (!anterior || anterior.estado === 'cerrada') return;

    setNonConformities((prev) =>
      prev.map((nc) =>
        nc.id !== ncId
          ? nc
          : { ...nc, estado: 'cerrada', cierre: { fecha: new Date().toISOString(), responsableId, firmada: true } },
      ),
    );

    registrar({
      entidadTipo: 'no_conformidad',
      entidadId: ncId,
      entidadLabel: etiqueta(anterior),
      tenantId: anterior.tenantId,
      accion: 'cerrado',
      resumen: 'Cerró la no conformidad con firma',
      cambios: [
        { campo: 'Estado', antes: NC_ESTADO_LABEL[anterior.estado], despues: NC_ESTADO_LABEL.cerrada },
        { campo: 'Firmada', antes: 'No', despues: 'Sí' },
      ],
      // RF-49 + RF-32: el cierre requiere firma, y el log debe decir quién
      // aprobó. Se resuelve el nombre ahora y se congela: si ese usuario se
      // desactiva o cambia de nombre, la firma debe seguir siendo legible.
      aprobadoPorId: responsableId,
      aprobadoPorNombre: users.find((u) => u.id === responsableId)?.nombre ?? responsableId,
    });
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
