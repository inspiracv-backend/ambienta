'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Audit, NonConformity, EtapasMejora, TipoRegistroMejora } from '@ambienta/shared';
import { mockAudits, mockNonConformities } from '@/mocks/audits';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useUsers } from '@/lib/users-store';
import { useSession } from '@/lib/session';
import { CRITICIDAD_LABEL, NC_ESTADO_LABEL } from '@/lib/audit-status';
import { api } from '@/lib/api-client';

interface AuditsContextValue {
  audits: Audit[];
  nonConformities: NonConformity[];
  loading: boolean;
  addNonConformity: (input: {
    tenantId: string;
    plantId: string;
    auditId?: string;
    hallazgo: string;
    criticidad: NonConformity['criticidad'];
    responsableId: string;
    tipoRegistro?: TipoRegistroMejora;
  }) => NonConformity;
  updatePorques: (ncId: string, cincoPorques: string[]) => void;
  updateEtapas: (ncId: string, etapas: EtapasMejora) => void;
  closeNonConformity: (ncId: string, responsableId: string) => void;
}

const AuditsContext = createContext<AuditsContextValue | null>(null);

/** `audits.audit_type` de la API → los dos tipos del modelo compartido. */
const TIPO_POR_AUDIT_TYPE: Record<string, Audit['tipo']> = {
  internal: 'interna',
  external: 'externa',
  // La API admite tambien 'regulatory' y 'supplier'. El modelo compartido solo
  // distingue interna/externa, asi que ambas caen en externa: las hace un
  // tercero. Si el negocio necesita separarlas, se amplia AuditSchema.
  regulatory: 'externa',
  supplier: 'externa',
};

/** `audits.status` de la API → los tres estados del modelo compartido. */
const ESTADO_POR_STATUS: Record<string, Audit['estado']> = {
  planned: 'planificada',
  active: 'en_curso',
  reporting: 'en_curso',
  closed: 'cerrada',
  cancelled: 'cerrada',
};

function mapApiAudit(raw: Record<string, unknown>): Audit | null {
  try {
    return {
      id: String(raw.id),
      tenantId: String(raw.tenant_id ?? ''),
      plantId: String(raw.facility_id ?? ''),
      tipo: TIPO_POR_AUDIT_TYPE[String(raw.audit_type ?? '')] ?? 'interna',
      fecha: raw.planned_start ? String(raw.planned_start) : new Date().toISOString(),
      estado: ESTADO_POR_STATUS[String(raw.status ?? '')] ?? 'planificada',
      // La API los tiene como `scope` (texto libre) y en tablas aparte; el
      // listado no los trae. Se pueblan al abrir el detalle.
      procesos: [],
      normativaIds: [],
    };
  } catch {
    return null;
  }
}

export function AuditsProvider({ children }: { children: ReactNode }) {
  const [audits, setAudits] = useState<Audit[]>(mockAudits);
  const [nonConformities, setNonConformities] = useState<NonConformity[]>(mockNonConformities);
  const [loading, setLoading] = useState(true);
  const registrar = useRegistrarAuditoria();
  const { users } = useUsers();
  const { user } = useSession();

  useEffect(() => {
    if (!user?.tenantId) { setLoading(false); return; }
    let cancelled = false;
    Promise.all([
      api.get<Record<string, unknown>[]>('/audits/', { tenantId: user.tenantId }),
      api.get<Record<string, unknown>[]>('/audits/nonconformities/', { tenantId: user.tenantId }),
    ])
      .then(([auditsData, ncData]) => {
        if (cancelled) return;
        const mappedAudits = auditsData.map(mapApiAudit).filter((a): a is Audit => a !== null);
        if (mappedAudits.length > 0) setAudits(mappedAudits);
        // NC mapping is complex due to frontend-specific fields, keep mocks as base
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [user?.tenantId]);

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
    tipoRegistro?: TipoRegistroMejora;
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
      tipoRegistro: input.tipoRegistro,
    };
    setNonConformities((prev) => [...prev, nc]);

    api.post('/audits/nonconformities/', {
      description: input.hallazgo,
      severity: input.criticidad,
      status: 'open',
      owner_user_id: input.responsableId,
    }, { tenantId: input.tenantId }).catch(() => {});

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
      ...(causaRaiz ? { motivo: `Causa raíz identificada: ${causaRaiz}` } : {}),
    });
  }

  function updateEtapas(ncId: string, etapas: EtapasMejora) {
    const anterior = nonConformities.find((nc) => nc.id === ncId);
    if (!anterior) return;

    const nuevoEstado = anterior.estado === 'abierta' ? 'en_tratamiento' : anterior.estado;

    setNonConformities((prev) =>
      prev.map((nc) =>
        nc.id !== ncId ? nc : { ...nc, etapasMejora: etapas, estado: nuevoEstado },
      ),
    );

    registrar({
      entidadTipo: 'no_conformidad',
      entidadId: ncId,
      entidadLabel: etiqueta(anterior),
      tenantId: anterior.tenantId,
      accion: 'actualizado',
      resumen: 'Actualizó las etapas del tratamiento',
      cambios: [
        ...(nuevoEstado !== anterior.estado
          ? [{ campo: 'Estado', antes: NC_ESTADO_LABEL[anterior.estado], despues: NC_ESTADO_LABEL[nuevoEstado] }]
          : []),
      ],
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

    if (user?.tenantId) {
      api.patch(`/audits/nonconformities/${ncId}`, { status: 'closed' }, { tenantId: user.tenantId }).catch(() => {});
    }

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
      aprobadoPorId: responsableId,
      aprobadoPorNombre: users.find((u) => u.id === responsableId)?.nombre ?? responsableId,
    });
  }

  return (
    <AuditsContext.Provider value={{ audits, nonConformities, loading, addNonConformity, updatePorques, updateEtapas, closeNonConformity }}>
      {children}
    </AuditsContext.Provider>
  );
}

export function useAudits() {
  const ctx = useContext(AuditsContext);
  if (!ctx) throw new Error('useAudits debe usarse dentro de <AuditsProvider>');
  return ctx;
}
