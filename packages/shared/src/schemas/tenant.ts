import { z } from 'zod';

export const PlantSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  nombre: z.string(),
  comuna: z.string(),
  region: z.string(),
});
export type Plant = z.infer<typeof PlantSchema>;

/** Módulos administrables por el Superadmin (RF-81) — coinciden con la navegación global de la plataforma. */
export const MODULOS_PLATAFORMA = [
  'matriz-legal',
  'obligaciones',
  'calendario',
  'auditorias',
  'no-conformidades',
  'catalogo-normativo',
  'gestores',
  'reportes',
  'notificaciones',
  'usuarios-roles',
  'chatbot',
] as const;
export const ModuloPlataformaSchema = z.enum(MODULOS_PLATAFORMA);
export type ModuloPlataforma = z.infer<typeof ModuloPlataformaSchema>;

/**
 * Países soportados. El producto se define multi-país desde el inicio (§1 y
 * §3.2.2 del Análisis Funcional), pero el modelo asumía Chile: `rut` era un
 * campo obligatorio con nombre de un identificador chileno.
 */
export const PAISES = [
  { codigo: 'CL', nombre: 'Chile', documento: 'RUT' },
  { codigo: 'PE', nombre: 'Perú', documento: 'RUC' },
  { codigo: 'CO', nombre: 'Colombia', documento: 'NIT' },
  { codigo: 'MX', nombre: 'México', documento: 'RFC' },
  { codigo: 'AR', nombre: 'Argentina', documento: 'CUIT' },
] as const;
export const PaisSchema = z.enum(['CL', 'PE', 'CO', 'MX', 'AR']);
export type Pais = z.infer<typeof PaisSchema>;

/**
 * Identificación tributaria genérica (RF-87: "RUT chileno **o** documento de
 * identificación genérico"). El tipo se deriva del país, pero se guarda
 * explícito porque el documento vive en documentos impresos y reportes donde
 * hay que rotularlo correctamente.
 */
export const IdentificacionSchema = z.object({
  tipo: z.string(),
  numero: z.string(),
});
export type Identificacion = z.infer<typeof IdentificacionSchema>;

/**
 * Certificaciones de sistemas de gestión que mantiene la empresa.
 *
 * No es un dato decorativo: determina **qué se le audita**. Una empresa
 * certificada en ISO 14001 tiene un programa de auditoría distinto al de una
 * que solo cumple normativa legal. Es también el "contexto de la
 * organización" que pide ISO 9001 §4.1.
 */
export const CERTIFICACIONES = [
  { codigo: 'iso-9001', nombre: 'ISO 9001', descripcion: 'Gestión de la calidad' },
  { codigo: 'iso-14001', nombre: 'ISO 14001', descripcion: 'Gestión ambiental' },
  { codigo: 'iso-45001', nombre: 'ISO 45001', descripcion: 'Seguridad y salud en el trabajo' },
  { codigo: 'iso-50001', nombre: 'ISO 50001', descripcion: 'Gestión de la energía' },
] as const;
export const CertificacionSchema = z.enum(['iso-9001', 'iso-14001', 'iso-45001', 'iso-50001']);
export type Certificacion = z.infer<typeof CertificacionSchema>;

/**
 * Contacto comercial del cliente (módulo CRM).
 *
 * Separado del `User` administrador a propósito: quien firma el contrato no
 * siempre es quien usa el sistema. Confundirlos obliga a crear cuentas para
 * personas que nunca van a entrar.
 */
export const ContactoComercialSchema = z.object({
  nombre: z.string(),
  cargo: z.string(),
  email: z.string().email(),
  /** Con prefijo de país incluido (RF-88: no asumir +569). */
  telefono: z.string(),
});
export type ContactoComercial = z.infer<typeof ContactoComercialSchema>;

/**
 * Suscripción del tenant.
 *
 * El equipo lo describió así: *"no son usuarios transaccionales, suelen ser
 * contratos de un año, como un SAP"*. Por eso la vigencia es explícita y con
 * fecha de término — no un booleano de activo/inactivo — y la demo es un
 * plan con duración, no un estado suelto.
 */
export const PlanSchema = z.enum(['demo', 'contrato']);
export type Plan = z.infer<typeof PlanSchema>;

export const SuscripcionSchema = z.object({
  plan: PlanSchema,
  fechaInicio: z.string(),
  /** Fin de la demo o del contrato. Es lo que se renueva, no la cuenta entera. */
  fechaTermino: z.string(),
  limiteUsuarios: z.number().int().positive(),
});
export type Suscripcion = z.infer<typeof SuscripcionSchema>;

/** Días por defecto de una demo (RF-82: planes de prueba). */
export const DIAS_DEMO_POR_DEFECTO = 10;

export const TenantSchema = z.object({
  id: z.string(),

  // ── Identificación legal ────────────────────────────────────────────────
  nombre: z.string(),
  identificacion: IdentificacionSchema,
  pais: PaisSchema,
  sector: z.string(),
  giro: z.string().optional(),
  direccion: z.string().optional(),
  sitioWeb: z.string().optional(),
  /**
   * Logo de la empresa. Se usa en los reportes impresos: un informe de
   * auditoría sin el logo del auditado no parece un documento de la empresa.
   */
  logoUrl: z.string().optional(),

  // ── Contexto de la organización (ISO 9001 §4.1) ─────────────────────────
  /** Determina obligaciones aplicables: hay umbrales normativos por tamaño. */
  numeroTrabajadores: z.number().int().nonnegative().optional(),
  /** Determina qué se le audita. */
  certificaciones: z.array(CertificacionSchema).default([]),

  // ── Comercial (CRM) ─────────────────────────────────────────────────────
  contactoComercial: ContactoComercialSchema.optional(),
  notasComerciales: z.string().optional(),

  // ── Administración de plataforma (RF-81) ────────────────────────────────
  // Nunca contenido de negocio del tenant (CLAUDE.md).
  esGestor: z.boolean().default(false),
  estado: z.enum(['activo', 'suspendido']),
  suscripcion: SuscripcionSchema,
  modulosActivos: z.array(ModuloPlataformaSchema),

  // ── Perfil Empresa (RF-10 a RF-12) — lo completa el Admin Empresa ───────
  perfilEmpresaCompleto: z.boolean(),
  plants: z.array(PlantSchema),
});
export type Tenant = z.infer<typeof TenantSchema>;

/** Etiqueta del documento tributario según el país. */
export function documentoDePais(pais: Pais): string {
  return PAISES.find((p) => p.codigo === pais)?.documento ?? 'Identificación';
}

/** Nombre del país para mostrar. */
export function nombreDePais(pais: Pais): string {
  return PAISES.find((p) => p.codigo === pais)?.nombre ?? pais;
}

/**
 * Días que faltan para que termine la suscripción. Negativo si ya venció.
 *
 * Es lo que permite avisar antes de que una demo expire o un contrato haya
 * que renovarlo, en vez de descubrirlo cuando el cliente ya no puede entrar.
 */
export function diasParaVencimiento(suscripcion: Suscripcion, ahora: Date = new Date()): number {
  const ms = new Date(suscripcion.fechaTermino).getTime() - ahora.getTime();
  return Math.ceil(ms / 86_400_000);
}
