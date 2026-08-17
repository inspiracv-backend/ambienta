/**
 * Los identificadores y los nombres de las dos primeras empresas **espejan la
 * semilla de `db/02_seed.sql`**, no son inventados.
 *
 * No es cosmetico: en modo desarrollo el frontend manda el tenant de la sesion
 * en la cabecera `X-Tenant-Id`, y la API lo exige como UUID. Con los ids
 * antiguos (`tenant-1`) **toda llamada con empresa devolvia 400** y la pantalla
 * caia a estos mismos datos de ejemplo con un aviso de "no pudimos conectar":
 * se entraba, y no se podia probar nada.
 *
 * Si cambia la semilla, esto cambia con ella.
 */
import type { Tenant } from '@ambienta/shared';

function enDias(dias: number): string {
  const d = new Date();
  d.setDate(d.getDate() + dias);
  return d.toISOString();
}

/**
 * 3 tenants para cubrir los casos que el sistema debe distinguir:
 * uno industrial multi-planta con contrato vigente, uno tipo Gestor
 * (sub-tenancy, RF-64 a RF-70), y uno en **demo por vencer** — este último
 * existe para poder evaluar el aviso de vencimiento, que sin un caso real no
 * se ve nunca.
 *
 * `estado`, `suscripcion` y `modulosActivos` son campos de administración de
 * plataforma (RF-81, Sección L) — nunca contenido de negocio del tenant.
 * `perfilEmpresaCompleto: true` en los dos primeros porque se modelan como
 * tenants ya operando; el de demo lo tiene en `false` porque acaba de darse
 * de alta y todavía no completó el flujo obligatorio (RF-10).
 */
export const mockTenants: Tenant[] = [
  {
    id: 'a0000000-0000-0000-0000-000000000001',
    nombre: 'Minera Andes SpA',
    identificacion: { tipo: 'RUT', numero: '76.123.456-7' },
    pais: 'CL',
    sector: 'Industrial',
    giro: 'Reciclaje y valorización de residuos industriales',
    direccion: 'Camino Industrial 4820, Rancagua',
    sitioWeb: 'https://recicladorasur.cl',
    numeroTrabajadores: 145,
    certificaciones: ['iso-9001', 'iso-14001'],
    contactoComercial: {
      nombre: 'Marcelo Fuentes',
      cargo: 'Gerente de Operaciones',
      email: 'marcelo.fuentes@recicladorasur.cl',
      telefono: '+56 9 8123 4567',
    },
    esGestor: false,
    perfilEmpresaCompleto: true,
    estado: 'activo',
    suscripcion: {
      plan: 'contrato',
      fechaInicio: enDias(-200),
      fechaTermino: enDias(165),
      limiteUsuarios: 20,
    },
    modulosActivos: [
      'matriz-legal',
      'obligaciones',
      'calendario',
      'auditorias',
      'no-conformidades',
      'catalogo-normativo',
      'reportes',
      'notificaciones',
      'chatbot',
    ],
    plants: [
      { id: 'planta-rancagua', tenantId: 'a0000000-0000-0000-0000-000000000001', nombre: 'Planta Rancagua', comuna: 'Rancagua', region: "O'Higgins", identificadorRETC: '5495718', ciiu: 'C107100' },
      { id: 'planta-talca', tenantId: 'a0000000-0000-0000-0000-000000000001', nombre: 'Planta Talca', comuna: 'Talca', region: 'Maule', identificadorRETC: '5495722', ciiu: 'C107100' },
      { id: 'planta-concepcion', tenantId: 'a0000000-0000-0000-0000-000000000001', nombre: 'Planta Concepción', comuna: 'Concepción', region: 'Biobío' },
    ],
  },
  {
    id: 'a0000000-0000-0000-0000-000000000002',
    nombre: 'EcoGestión Consultoría Ambiental Ltda',
    identificacion: { tipo: 'RUT', numero: '96.789.123-4' },
    pais: 'CL',
    sector: 'Gestión de residuos',
    giro: 'Gestión y disposición de residuos para terceros',
    direccion: 'Av. Providencia 1650, Santiago',
    numeroTrabajadores: 60,
    certificaciones: ['iso-14001', 'iso-45001'],
    contactoComercial: {
      nombre: 'Antonia Vidal',
      cargo: 'Subgerenta de Cumplimiento',
      email: 'antonia.vidal@veolia.cl',
      telefono: '+56 2 2345 6789',
    },
    esGestor: true,
    perfilEmpresaCompleto: true,
    estado: 'activo',
    suscripcion: {
      plan: 'contrato',
      fechaInicio: enDias(-90),
      fechaTermino: enDias(275),
      limiteUsuarios: 10,
    },
    modulosActivos: ['obligaciones', 'calendario', 'gestores', 'notificaciones'],
    plants: [
      { id: 'sede-santiago', tenantId: 'a0000000-0000-0000-0000-000000000002', nombre: 'Sede Santiago', comuna: 'Santiago', region: 'Metropolitana' },
    ],
  },
  {
    // Demo recién dada de alta: sin Perfil Empresa y a 3 días de vencer.
    // Es el caso que el Superadmin necesita ver destacado en su dashboard.
    id: 'tenant-3',
    nombre: 'Agrícola Los Maitenes Ltda.',
    identificacion: { tipo: 'RUT', numero: '77.456.789-K' },
    pais: 'CL',
    sector: 'Agroindustria',
    giro: 'Producción y exportación de fruta fresca',
    direccion: 'Ruta 5 Sur km 182, Curicó',
    numeroTrabajadores: 320,
    certificaciones: ['iso-9001'],
    contactoComercial: {
      nombre: 'Patricia Herrera',
      cargo: 'Jefa de Medio Ambiente',
      email: 'pherrera@losmaitenes.cl',
      telefono: '+56 9 7654 3210',
    },
    notasComerciales: 'Solicitó demo tras webinar de Ley REP. Interesada en el módulo de Obligaciones.',
    esGestor: false,
    perfilEmpresaCompleto: false,
    estado: 'activo',
    suscripcion: {
      plan: 'demo',
      fechaInicio: enDias(-7),
      fechaTermino: enDias(3),
      limiteUsuarios: 3,
    },
    modulosActivos: ['matriz-legal', 'obligaciones', 'calendario'],
    plants: [
      { id: 'planta-curico', tenantId: 'tenant-3', nombre: 'Packing Curicó', comuna: 'Curicó', region: 'Maule' },
    ],
  },
];
