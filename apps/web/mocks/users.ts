import type { User } from '@ambienta/shared';

/** Los 6 roles del Análisis Funcional v1.5, repartidos entre los 2 tenants de mocks/tenants.ts. */
export const mockUsers: User[] = [
  {
    id: 'user-superadmin',
    tenantId: null,
    nombre: 'Javiera Soto',
    email: 'javiera.soto@ambienta.cl',
    role: 'superadmin',
    plantIds: [],
  },
  {
    id: 'user-admin-empresa',
    tenantId: 'tenant-1',
    nombre: 'Marcelo Fuentes',
    email: 'marcelo.fuentes@recicladorasur.cl',
    role: 'admin_empresa',
    plantIds: ['planta-rancagua', 'planta-talca', 'planta-concepcion'],
  },
  {
    id: 'user-interno',
    tenantId: 'tenant-1',
    nombre: 'Camila Rojas',
    email: 'camila.rojas@recicladorasur.cl',
    role: 'usuario_interno',
    plantIds: ['planta-rancagua', 'planta-talca'],
  },
  {
    id: 'user-especialista',
    tenantId: 'tenant-1',
    nombre: 'Diego Muñoz',
    email: 'diego.munoz@consultora-ambiental.cl',
    role: 'especialista',
    plantIds: ['planta-concepcion'],
  },
  {
    id: 'user-gestor',
    tenantId: 'tenant-2',
    nombre: 'Antonia Vidal',
    email: 'antonia.vidal@veolia.cl',
    role: 'gestor',
    plantIds: ['sede-santiago'],
  },
  {
    id: 'user-cliente-invitado',
    tenantId: 'tenant-1',
    nombre: 'Roberto Pizarro',
    email: 'roberto.pizarro@gmail.com',
    role: 'cliente_invitado',
    plantIds: [],
  },
];
