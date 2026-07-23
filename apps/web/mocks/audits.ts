import type { Audit, NonConformity } from '@ambienta/shared';

function addDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

/** Auditorías (planificación) — Sección G, no implementada aún en UI pero disponible para dashboard-metrics. */
export const mockAudits: Audit[] = [
  {
    id: 'audit-1',
    tenantId: 'tenant-1',
    plantId: 'planta-rancagua',
    tipo: 'interna',
    fecha: addDays(20),
    estado: 'planificada',
    procesos: ['Gestión de residuos peligrosos'],
    normativaIds: [],
  },
  {
    id: 'audit-2',
    tenantId: 'tenant-1',
    plantId: 'planta-talca',
    tipo: 'externa',
    fecha: addDays(-15),
    estado: 'cerrada',
    procesos: ['Emisiones atmosféricas'],
    normativaIds: [],
  },
];

/** No Conformidades (hallazgos) — usadas por lib/dashboard-metrics.ts para contar NC activas por tenant. */
export const mockNonConformities: NonConformity[] = [
  {
    id: 'nc-1',
    tenantId: 'tenant-1',
    auditId: 'audit-2',
    hallazgo: 'Discrepancia entre kilogramos declarados y retirados de residuo peligroso',
    criticidad: 'alta',
    estado: 'en_tratamiento',
    fechaDeteccion: addDays(-14),
    responsableId: 'user-interno',
  },
  {
    id: 'nc-2',
    tenantId: 'tenant-1',
    hallazgo: 'Falta certificado de calibración de balanza de pesaje',
    criticidad: 'media',
    estado: 'abierta',
    fechaDeteccion: addDays(-3),
    responsableId: 'user-especialista',
  },
];
