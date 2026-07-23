import type { PlanAccion } from '@ambienta/shared';

function addDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

/** Ejemplo generado desde el Art. 10 "No cumple" de norm-1 (Ley REP) en mocks/catalog.ts. */
export const mockActionPlans: PlanAccion[] = [
  {
    id: 'plan-1',
    tenantId: 'tenant-1',
    origenTipo: 'articulo',
    origenId: 'art-1b',
    origenLabel: 'Art. 10 — Registro de productores (Ley 20.920 — Ley REP)',
    titulo: 'Regularizar registro de productores REP',
    responsableId: 'user-especialista',
    fechaLimite: addDays(25),
    estado: 'en_progreso',
    tareas: [
      { id: 'pt-1a', titulo: 'Recopilar antecedentes de producción anual', hecha: true },
      { id: 'pt-1b', titulo: 'Completar formulario de registro en el sistema REP', hecha: false },
      { id: 'pt-1c', titulo: 'Enviar registro y confirmar recepción', hecha: false },
    ],
  },
];
