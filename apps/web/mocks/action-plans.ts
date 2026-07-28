import type { PlanAccion } from '@ambienta/shared';

function addDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

/**
 * Planes de acción de ejemplo. Están repartidos entre los dos usuarios
 * internos del tenant y con distintos plazos (uno atrasado, uno próximo, uno
 * holgado) para que la vista "Mis tareas" del Usuario Interno (RF-40) muestre
 * sus tres estados sin tener que crear datos a mano.
 */
export const mockActionPlans: PlanAccion[] = [
  {
    // Generado desde el Art. 10 "No cumple" de norm-1 (Ley REP) en mocks/catalog.ts.
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
  {
    // Atrasado: es el caso que genera incumplimiento y debe destacarse.
    id: 'plan-2',
    tenantId: 'tenant-1',
    origenTipo: 'no_conformidad',
    origenId: 'nc-1',
    origenLabel: 'NC-001 — Contenedores sin rotulación de residuo peligroso',
    titulo: 'Rotular contenedores del patio de residuos peligrosos',
    responsableId: 'user-interno',
    fechaLimite: addDays(-4),
    estado: 'en_progreso',
    tareas: [
      { id: 'pt-2a', titulo: 'Levantar inventario de contenedores sin rótulo', hecha: true },
      { id: 'pt-2b', titulo: 'Solicitar rótulos según DS 148', hecha: true },
      { id: 'pt-2c', titulo: 'Instalar rótulos y registrar evidencia fotográfica', hecha: false },
    ],
  },
  {
    // Vence esta semana.
    id: 'plan-3',
    tenantId: 'tenant-1',
    origenTipo: 'articulo',
    origenId: 'art-2a',
    origenLabel: 'Art. 5 — Declaración anual (DS 148 — Residuos peligrosos)',
    titulo: 'Preparar declaración anual de residuos peligrosos',
    responsableId: 'user-interno',
    fechaLimite: addDays(5),
    estado: 'abierto',
    tareas: [
      { id: 'pt-3a', titulo: 'Consolidar guías de despacho del período', hecha: false },
      { id: 'pt-3b', titulo: 'Validar cantidades contra el registro SIDREP', hecha: false },
    ],
  },
];
