import type { Contrato, SubTenant } from '@ambienta/shared';

function addDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

/** Clientes finales (sub-tenants) del tenant Gestor "Veolia Ambiental Chile" (tenant-2) — RF-56/RF-57. */
export const mockSubTenants: SubTenant[] = [
  {
    id: 'sub-1',
    gestorTenantId: 'a0000000-0000-0000-0000-000000000002',
    nombre: 'Agroindustrial Los Ríos SpA',
    rut: '77.111.222-3',
    estado: 'activo',
    contactos: [
      { id: 'ct-1a', nombre: 'Paula Herrera', cargo: 'Jefa de Planta', telefono: '+56 9 8123 4567', email: 'paula.herrera@agrolosrios.cl', autorizado: true },
      { id: 'ct-1b', nombre: 'Ignacio Silva', cargo: 'Encargado de Bodega', telefono: '+56 9 8765 4321', email: 'ignacio.silva@agrolosrios.cl', autorizado: false },
    ],
  },
  {
    id: 'sub-2',
    gestorTenantId: 'a0000000-0000-0000-0000-000000000002',
    nombre: 'Frigorífico del Maule Ltda.',
    rut: '78.222.333-4',
    estado: 'inactivo',
    contactos: [
      { id: 'ct-2a', nombre: 'Rodrigo Álamos', cargo: 'Gerente de Operaciones', telefono: '+56 9 7654 3210', email: 'rodrigo.alamos@frigomaule.cl', autorizado: true },
    ],
  },
];

/** Contratos de los clientes finales, con campos dinámicos por tenant (RF-58b). */
export const mockContratos: Contrato[] = [
  {
    id: 'contrato-1',
    subTenantId: 'sub-1',
    nombre: 'Contrato retiro de residuos orgánicos 2026',
    fechaInicio: '2026-01-01T00:00:00.000Z',
    fechaTermino: '2026-12-31T00:00:00.000Z',
    camposCustom: {
      'Frecuencia de retiro': 'Semanal',
      'Volumen estimado (ton/mes)': '18',
    },
  },
];
