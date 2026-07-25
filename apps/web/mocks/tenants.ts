import type { Tenant } from '@ambienta/shared';

/**
 * 2 tenants para poder probar aislamiento visual multi-tenant (Paso 3):
 * uno industrial multi-planta, uno tipo Gestor (sub-tenancy, RF-56 a RF-58c).
 * `estado`/`limiteUsuarios`/`modulosActivos` son campos de administración de
 * plataforma (RF-59, Sección L) — nunca contenido de negocio del tenant.
 */
export const mockTenants: Tenant[] = [
  {
    id: 'tenant-1',
    nombre: 'Recicladora del Sur SpA',
    rut: '76.123.456-7',
    sector: 'Industrial',
    esGestor: false,
    estado: 'activo',
    limiteUsuarios: 20,
    modulosActivos: [
      'matriz-legal',
      'obligaciones',
      'calendario',
      'auditorias',
      'no-conformidades',
      'catalogo-normativo',
      'notificaciones',
      'chatbot',
    ],
    plants: [
      { id: 'planta-rancagua', tenantId: 'tenant-1', nombre: 'Planta Rancagua', comuna: 'Rancagua', region: "O'Higgins" },
      { id: 'planta-talca', tenantId: 'tenant-1', nombre: 'Planta Talca', comuna: 'Talca', region: 'Maule' },
      { id: 'planta-concepcion', tenantId: 'tenant-1', nombre: 'Planta Concepción', comuna: 'Concepción', region: 'Biobío' },
    ],
  },
  {
    id: 'tenant-2',
    nombre: 'Veolia Ambiental Chile',
    rut: '96.789.123-4',
    sector: 'Gestión de residuos',
    esGestor: true,
    estado: 'activo',
    limiteUsuarios: 10,
    modulosActivos: ['obligaciones', 'calendario', 'gestores', 'notificaciones'],
    plants: [
      { id: 'sede-santiago', tenantId: 'tenant-2', nombre: 'Sede Santiago', comuna: 'Santiago', region: 'Metropolitana' },
    ],
  },
];
