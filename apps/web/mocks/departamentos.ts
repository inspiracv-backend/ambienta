import type { Departamento } from '@ambienta/shared';

/** Departamentos del Perfil Empresa (RF-11, RF-12, v1.7) — todo Usuario Interno pertenece a uno. */
export const mockDepartamentos: Departamento[] = [
  { id: 'depto-operaciones', tenantId: 'tenant-1', nombre: 'Operaciones' },
  { id: 'depto-medioambiente', tenantId: 'tenant-1', nombre: 'Medio Ambiente' },
  { id: 'depto-administracion', tenantId: 'tenant-1', nombre: 'Administración y Finanzas' },
  { id: 'depto-servicio-cliente', tenantId: 'tenant-2', nombre: 'Servicio al Cliente' },
];
