import type { Obligation } from '@ambienta/shared';

function addDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

/**
 * Obligaciones (megaproyectos, RF-15) cruzando RETC/Ley REP/SINADER/SIDREP/DAE
 * con los 4 estados requeridos por Paso 3: vigente, por_vencer (≤30 días),
 * vencida, sin_evidencia. Mismo tenant/plantas que mocks/tenants.ts.
 */
export const mockObligations: Obligation[] = [
  {
    id: 'obl-1',
    tenantId: 'tenant-1',
    plantId: 'planta-rancagua',
    sistema: 'SIDREP',
    nombre: 'SIDREP Q3 2026',
    periodo: '2026-Q3',
    estado: 'por_vencer',
    proximoVencimiento: addDays(6),
    responsableId: 'user-interno',
    tasks: [
      { id: 'task-1a', obligationId: 'obl-1', titulo: 'Cargar registro de residuos peligrosos', vencimiento: addDays(6), responsableId: 'user-interno', estado: 'por_vencer' },
      { id: 'task-1b', obligationId: 'obl-1', titulo: 'Adjuntar evidencia de retiro', vencimiento: addDays(4), responsableId: 'user-interno', estado: 'por_vencer' },
    ],
  },
  {
    id: 'obl-2',
    tenantId: 'tenant-1',
    plantId: 'planta-rancagua',
    sistema: 'RETC',
    nombre: 'Declaración RETC anual 2025',
    periodo: '2025-ANUAL',
    estado: 'vigente',
    proximoVencimiento: addDays(210),
    responsableId: 'user-interno',
    tasks: [
      { id: 'task-2a', obligationId: 'obl-2', titulo: 'Consolidar emisiones anuales', vencimiento: addDays(200), responsableId: 'user-interno', estado: 'vigente' },
    ],
  },
  {
    id: 'obl-3',
    tenantId: 'tenant-1',
    plantId: 'planta-talca',
    sistema: 'DAE',
    nombre: 'DAE 2026',
    periodo: '2026-ANUAL',
    estado: 'vencida',
    proximoVencimiento: addDays(-5),
    responsableId: 'user-interno',
    tasks: [
      { id: 'task-3a', obligationId: 'obl-3', titulo: 'Presentar declaración de aguas de emisión', vencimiento: addDays(-5), responsableId: 'user-interno', estado: 'vencida' },
    ],
  },
  {
    id: 'obl-4',
    tenantId: 'tenant-1',
    plantId: 'planta-talca',
    sistema: 'Ley REP',
    nombre: 'Ley REP — Metas de recolección Q3',
    periodo: '2026-Q3',
    estado: 'sin_evidencia',
    proximoVencimiento: addDays(18),
    responsableId: 'user-especialista',
    tasks: [
      { id: 'task-4a', obligationId: 'obl-4', titulo: 'Adjuntar certificado de valorización', vencimiento: addDays(18), responsableId: 'user-especialista', estado: 'sin_evidencia' },
    ],
  },
  {
    id: 'obl-5',
    tenantId: 'tenant-1',
    plantId: 'planta-concepcion',
    sistema: 'SINADER',
    nombre: 'SINADER — Movimiento de residuos julio',
    periodo: '2026-07',
    estado: 'por_vencer',
    proximoVencimiento: addDays(3),
    responsableId: 'user-especialista',
    tasks: [
      { id: 'task-5a', obligationId: 'obl-5', titulo: 'Registrar movimiento de residuos del mes', vencimiento: addDays(3), responsableId: 'user-especialista', estado: 'por_vencer' },
    ],
  },
  {
    id: 'obl-6',
    tenantId: 'tenant-1',
    plantId: 'planta-concepcion',
    sistema: 'RETC',
    nombre: 'RETC — Fuentes fijas Concepción',
    periodo: '2025-ANUAL',
    estado: 'vigente',
    proximoVencimiento: addDays(300),
    responsableId: 'user-especialista',
    tasks: [
      { id: 'task-6a', obligationId: 'obl-6', titulo: 'Monitoreo de fuentes fijas', vencimiento: addDays(280), responsableId: 'user-especialista', estado: 'vigente' },
    ],
  },
  {
    id: 'obl-7',
    tenantId: 'tenant-2',
    plantId: 'sede-santiago',
    sistema: 'SIDREP',
    nombre: 'SIDREP clientes Q3 2026',
    periodo: '2026-Q3',
    estado: 'por_vencer',
    proximoVencimiento: addDays(12),
    responsableId: 'user-gestor',
    tasks: [
      { id: 'task-7a', obligationId: 'obl-7', titulo: 'Consolidar declaraciones de clientes', vencimiento: addDays(12), responsableId: 'user-gestor', estado: 'por_vencer' },
    ],
  },
];
