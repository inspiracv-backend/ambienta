import { z } from 'zod';

/**
 * Control de información documentada (RF-102 a RF-106, ISO 9001 §7.5).
 *
 * ## El estado vive en la REVISIÓN, no en el documento
 *
 * Es la decisión de diseño que sostiene todo lo demás, y la toma `db/18`:
 * poner el ciclo de vida en `documents` haría que aprobar la revisión 4
 * borrara el rastro de que la 3 estuvo vigente entre tales fechas — que es
 * exactamente lo que pregunta una auditoría.
 *
 * El documento tiene un código y un título estables; cada revisión tiene su
 * propio estado, su aprobación firmada y sus fechas de vigencia.
 */

/** Los tipos con ciclo de vida: documentación controlada del sistema de gestión. */
export const TIPOS_DOCUMENTO_CONTROLADO = [
  'politica',
  'procedimiento',
  'instructivo',
  'formato',
  'registro',
  'externo',
] as const;
export const TipoDocumentoControladoSchema = z.enum(TIPOS_DOCUMENTO_CONTROLADO);
export type TipoDocumentoControlado = z.infer<typeof TipoDocumentoControladoSchema>;

/**
 * Los tipos SIN ciclo de vida: archivos de la operación.
 *
 * **Van en inglés y los controlados en español.** No es un descuido: `db/18`
 * agregó los controlados a un CHECK que ya tenía estos, y renombrarlos habría
 * roto las filas existentes. Conviene saberlo antes de escribir un tipo a mano.
 */
export const TIPOS_DOCUMENTO_OPERATIVO = [
  'evidence',
  'declaration_template',
  'receipt',
  'contract',
  'audit',
  'email_attachment',
  'other',
] as const;

export const EstadoRevisionSchema = z.enum([
  'borrador',
  'en_revision',
  'aprobado',
  'vigente',
  'obsoleto',
]);
export type EstadoRevision = z.infer<typeof EstadoRevisionSchema>;

/**
 * Qué estado puede seguir a cuál. **Espejo de `TRANSICIONES` en
 * `apps/api/app/services/control_documental.py`.**
 *
 * Existe acá sólo para no ofrecer un botón que la API va a rechazar. La regla
 * la decide el servidor: si estas dos listas se separan, manda la de la API y
 * el usuario ve un 409 — molesto, pero no peligroso. Al revés sería peor.
 */
export const TRANSICIONES_REVISION: Record<EstadoRevision, readonly EstadoRevision[]> = {
  borrador: ['en_revision', 'obsoleto'],
  en_revision: ['aprobado', 'borrador', 'obsoleto'],
  aprobado: ['vigente', 'obsoleto'],
  vigente: ['obsoleto'],
  /** Sin salida: un obsoleto que "revive" deja a quien lo citó sin saber si regía. */
  obsoleto: [],
};

/**
 * Los estados en que una revisión sirve como evidencia.
 *
 * `aprobado` **no** entra: aprobada pero sin entrar en vigencia significa que
 * todavía rige la anterior.
 */
export const SIRVE_COMO_EVIDENCIA: readonly EstadoRevision[] = ['vigente'];

export const RevisionDocumentalSchema = z.object({
  id: z.string(),
  documentoId: z.string(),
  numero: z.number(),
  estado: EstadoRevisionSchema,
  nombreArchivo: z.string(),
  tipoMime: z.string(),
  tamanoBytes: z.number(),
  /** Dónde vive el archivo. `backblaze` hoy; el modelo admite S3, Drive y OneDrive. */
  proveedor: z.string(),
  creadaEn: z.string(),
  /** Quién aprobó. La base exige que vaya junto con `aprobadaEn`. */
  aprobadaPor: z.string().nullable(),
  aprobadaEn: z.string().nullable(),
  rigeDesde: z.string().nullable(),
  rigeHasta: z.string().nullable(),
  obsoletaEn: z.string().nullable(),
  /** Por qué dejó de regir. Obligatorio al marcar obsoleta. */
  motivoObsolescencia: z.string().nullable(),
});
export type RevisionDocumental = z.infer<typeof RevisionDocumentalSchema>;

export const DocumentoSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  /** Lo que se cita en una auditoría. Puede faltar en documentos antiguos. */
  codigo: z.string().nullable(),
  titulo: z.string(),
  tipo: z.string(),
  /** `borrador` | `en_revision` | `vigente` | `obsoleto`. Refleja la revisión que rige. */
  estado: z.string(),
  clasificacion: z.string(),
  etiquetas: z.array(z.string()),
  /** La revisión vigente, si hay alguna. `null` = nada rige todavía. */
  revisionVigenteId: z.string().nullable(),
  creadoEn: z.string(),
  actualizadoEn: z.string(),
});
export type Documento = z.infer<typeof DocumentoSchema>;

/** ¿Este tipo tiene ciclo de vida, o es un archivo que sólo se guarda? */
export function esControlado(tipo: string): boolean {
  return (TIPOS_DOCUMENTO_CONTROLADO as readonly string[]).includes(tipo);
}

/** ¿Esta revisión puede usarse como evidencia ante una fiscalización? */
export function sirveComoEvidencia(estado: EstadoRevision): boolean {
  return SIRVE_COMO_EVIDENCIA.includes(estado);
}

/** Los estados a los que se puede saltar desde este. Vacío = ninguno. */
export function transicionesDesde(estado: EstadoRevision): readonly EstadoRevision[] {
  return TRANSICIONES_REVISION[estado] ?? [];
}

export const ETIQUETA_ESTADO_REVISION: Record<EstadoRevision, string> = {
  borrador: 'Borrador',
  en_revision: 'En revisión',
  aprobado: 'Aprobada',
  vigente: 'Vigente',
  obsoleto: 'Obsoleta',
};

export const ETIQUETA_TIPO_DOCUMENTO: Record<string, string> = {
  politica: 'Política',
  procedimiento: 'Procedimiento',
  instructivo: 'Instructivo',
  formato: 'Formato',
  registro: 'Registro',
  externo: 'Documento externo',
  evidence: 'Evidencia',
  declaration_template: 'Plantilla de declaración',
  receipt: 'Comprobante',
  contract: 'Contrato',
  audit: 'Auditoría',
  email_attachment: 'Adjunto de correo',
  other: 'Otro',
};

/**
 * Un tamaño que una persona pueda leer.
 *
 * Se usa base 1024 y las unidades KB/MB, que es lo que muestra el explorador
 * de archivos en Windows: coincidir con lo que la persona ve al lado importa
 * más que la exactitud del prefijo SI.
 */
export function tamanoLegible(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(kb < 10 ? 1 : 0)} KB`;
  return `${(kb / 1024).toFixed((kb / 1024) < 10 ? 1 : 0)} MB`;
}
