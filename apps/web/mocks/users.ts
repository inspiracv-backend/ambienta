import type { User } from '@ambienta/shared';

/**
 * Los 5 roles del Análisis Funcional v1.7, repartidos entre los 2 tenants de
 * mocks/tenants.ts. `user-especialista` conserva su id histórico (referenciado
 * como responsableId en varios mocks) pero su rol pasó a `usuario_interno`
 * tras la eliminación del rol Especialista (Decisión cerrada #12, v1.7).
 * `departamentoId` (RF-11) es obligatorio para `usuario_interno` y null para
 * el resto de roles — ver mocks/departamentos.ts.
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
  },
  {
    id: 'user-admin-empresa',
    tenantId: 'tenant-1',
    nombre: 'Marcelo Fuentes',
    email: 'marcelo.fuentes@recicladorasur.cl',
    role: 'admin_empresa',
    plantIds: ['planta-rancagua', 'planta-talca', 'planta-concepcion'],
    departamentoId: null,
  },
  {
    id: 'user-interno',
    tenantId: 'tenant-1',
    nombre: 'Camila Rojas',
    email: 'camila.rojas@recicladorasur.cl',
    role: 'usuario_interno',
    plantIds: ['planta-rancagua', 'planta-talca'],
    departamentoId: 'depto-operaciones',
  },
  {
    id: 'user-especialista',
    tenantId: 'tenant-1',
    nombre: 'Diego Muñoz',
    email: 'diego.munoz@consultora-ambiental.cl',
    role: 'usuario_interno',
    plantIds: ['planta-concepcion'],
    departamentoId: 'depto-medioambiente',
  },
  {
    id: 'user-gestor',
    tenantId: 'tenant-2',
    nombre: 'Antonia Vidal',
    email: 'antonia.vidal@veolia.cl',
    role: 'gestor',
    plantIds: ['sede-santiago'],
    departamentoId: null,
  },
  {
    id: 'user-cliente-invitado',
    tenantId: 'tenant-1',
    nombre: 'Roberto Pizarro',
    email: 'roberto.pizarro@gmail.com',
    role: 'cliente_invitado',
    plantIds: [],
    departamentoId: null,
  },
];
