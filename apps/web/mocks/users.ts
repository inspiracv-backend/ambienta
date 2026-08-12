import type { User } from '@ambienta/shared';

function addDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

/**
 * Los 5 roles del Análisis Funcional v1.7, repartidos entre los 2 tenants de
 * mocks/tenants.ts. `user-especialista` conserva su id histórico (referenciado
 * como responsableId en varios mocks) pero su rol pasó a `usuario_interno`
 * tras la eliminación del rol Especialista (Decisión cerrada #12, v1.7).
 * `departamentoId` (RF-11) es obligatorio para `usuario_interno` y null para
 * el resto de roles — ver mocks/departamentos.ts. Todos parten `activo` con
 * `ultimaActividad` reciente porque son usuarios que ya vienen operando en
 * las secciones anteriores (Sección N, S-41, solo agrega la gestión real).
 */
export const mockUsers: User[] = [
  {
    id: 'user-superadmin',
    tenantId: null,
    nombre: 'Javiera Soto',
    email: 'javiera.soto@ambienta.cl',
    role: 'superadmin',
    plantIds: [],
    departamentoId: null,
    estado: 'activo',
    ultimaActividad: addDays(0),
  },
  {
    id: 'user-admin-empresa',
    tenantId: 'tenant-1',
    nombre: 'Marcelo Fuentes',
    email: 'marcelo.fuentes@recicladorasur.cl',
    role: 'admin_empresa',
    descriptorCargo: {
      cargo: 'Gerente de Operaciones',
      funciones: ['Dirigir la operación de las tres plantas', 'Aprobar planes de acción ambientales'],
      responsabilidades: ['Cumplimiento normativo del tenant', 'Asignación de recursos para acciones correctivas'],
    },
    plantIds: ['planta-rancagua', 'planta-talca', 'planta-concepcion'],
    departamentoId: null,
    estado: 'activo',
    ultimaActividad: addDays(-1),
  },
  {
    id: 'user-interno',
    tenantId: 'tenant-1',
    nombre: 'Camila Rojas',
    email: 'camila.rojas@recicladorasur.cl',
    role: 'usuario_interno',
    descriptorCargo: {
      cargo: 'Analista Ambiental',
      funciones: ['Preparar declaraciones RETC', 'Mantener el registro de residuos peligrosos'],
      responsabilidades: ['Exactitud de los datos declarados', 'Resguardo de la evidencia documental'],
    },
    plantIds: ['planta-rancagua', 'planta-talca'],
    departamentoId: 'depto-operaciones',
    estado: 'activo',
    ultimaActividad: addDays(-2),
  },
  {
    id: 'user-especialista',
    tenantId: 'tenant-1',
    nombre: 'Diego Muñoz',
    email: 'diego.munoz@consultora-ambiental.cl',
    role: 'usuario_interno',
    descriptorCargo: {
      cargo: 'Jefe de Medio Ambiente',
      funciones: ['Liderar auditorías internas', 'Analizar causa raíz de no conformidades'],
      responsabilidades: ['Programa anual de auditorías', 'Cierre de no conformidades de su planta'],
    },
    plantIds: ['planta-concepcion'],
    departamentoId: 'depto-medioambiente',
    estado: 'activo',
    ultimaActividad: addDays(-5),
  },
  {
    id: 'user-gestor',
    tenantId: 'tenant-2',
    nombre: 'Antonia Vidal',
    email: 'antonia.vidal@veolia.cl',
    role: 'gestor',
    plantIds: ['sede-santiago'],
    departamentoId: null,
    estado: 'activo',
    ultimaActividad: addDays(-3),
  },
  {
    id: 'user-cliente-invitado',
    tenantId: 'tenant-1',
    nombre: 'Roberto Pizarro',
    email: 'roberto.pizarro@gmail.com',
    role: 'cliente_invitado',
    plantIds: [],
    departamentoId: null,
    estado: 'activo',
    ultimaActividad: addDays(-14),
  },
];
