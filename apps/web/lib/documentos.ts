import type {
  Documento,
  EstadoRevision,
  RevisionDocumental,
} from '@ambienta/shared';
import { api } from '@/lib/api-client';

/**
 * Documentos y sus revisiones (RF-102 a RF-106, #31).
 *
 * ## La subida va en tres pasos, y el de en medio no pasa por nosotros
 *
 * ```
 *   1. POST /documents/{id}/upload-url      → la API firma un permiso temporal
 *   2. PUT  <url firmada>                   → el navegador sube DIRECTO a B2
 *   3. POST /documents/{id}/confirm-upload  → la API crea la revisión
 * ```
 *
 * El paso 2 no atraviesa la API a propósito: un PDF de 40 MB pasando por
 * FastAPI ocupa un worker durante toda la subida. Lo que se cede es que el
 * archivo llega sin que lo hayamos visto, y por eso el paso 3 existe — la API
 * le pregunta al bucket el tamaño y el tipo **reales** en vez de creerle al
 * navegador, y de paso es lo único que detecta un `PUT` que falló a la mitad.
 *
 * **El paso 3 no es opcional.** Si la persona cierra la pestaña entre el 2 y el
 * 3, queda un archivo en el bucket sin fila que lo represente: existe y nadie
 * lo ve. Es un caso conocido y anotado en ADR-005; acá se mitiga avisando en
 * pantalla mientras la subida está en curso, no dándolo por resuelto.
 *
 * ## Las cabeceras del paso 1 hay que mandarlas tal cual
 *
 * Van **dentro de la firma**. Con otras, B2 rechaza la subida con un 403 que se
 * lee como un problema de credenciales y no lo es.
 */

interface DocumentoApi {
  id: string;
  tenant_id: string;
  code: string | null;
  title: string;
  document_type: string;
  status: string;
  classification: string;
  tags: string[];
  current_version_id: string | null;
  created_at: string;
  updated_at: string;
}

interface RevisionApi {
  id: string;
  document_id: string;
  version_no: number;
  lifecycle_status: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  storage_provider: string;
  created_at: string;
  approved_by: string | null;
  approved_at: string | null;
  valid_from: string | null;
  valid_to: string | null;
  obsoleted_at: string | null;
  obsoleted_reason: string | null;
}

export function mapDocumento(raw: DocumentoApi): Documento {
  return {
    id: raw.id,
    tenantId: raw.tenant_id,
    codigo: raw.code ?? null,
    titulo: raw.title,
    tipo: raw.document_type,
    estado: raw.status,
    clasificacion: raw.classification,
    etiquetas: Array.isArray(raw.tags) ? raw.tags : [],
    revisionVigenteId: raw.current_version_id ?? null,
    creadoEn: raw.created_at,
    actualizadoEn: raw.updated_at,
  };
}

export function mapRevision(raw: RevisionApi): RevisionDocumental {
  return {
    id: raw.id,
    documentoId: raw.document_id,
    numero: raw.version_no,
    // La API es la que manda sobre el estado. Si algún día apareciera uno que
    // el frontend no conoce, se muestra como borrador —el más restrictivo— en
    // vez de romper la pantalla: un estado desconocido no debe parecer vigente.
    estado: (raw.lifecycle_status as EstadoRevision) ?? 'borrador',
    nombreArchivo: raw.file_name,
    tipoMime: raw.mime_type,
    tamanoBytes: raw.size_bytes,
    proveedor: raw.storage_provider,
    creadaEn: raw.created_at,
    aprobadaPor: raw.approved_by ?? null,
    aprobadaEn: raw.approved_at ?? null,
    rigeDesde: raw.valid_from ?? null,
    rigeHasta: raw.valid_to ?? null,
    obsoletaEn: raw.obsoleted_at ?? null,
    motivoObsolescencia: raw.obsoleted_reason ?? null,
  };
}

export async function listarDocumentos(tenantId: string): Promise<Documento[]> {
  const filas = await api.get<DocumentoApi[]>('/documents/?limit=200', { tenantId });
  return filas.map(mapDocumento);
}

export async function listarRevisiones(
  documentoId: string,
  tenantId: string,
): Promise<RevisionDocumental[]> {
  const filas = await api.get<RevisionApi[]>(`/documents/${documentoId}/versions`, {
    tenantId,
  });
  // De la más nueva a la más vieja: la que interesa casi siempre es la última.
  return filas.map(mapRevision).sort((a, b) => b.numero - a.numero);
}

export async function crearDocumento(
  input: { titulo: string; tipo: string; clasificacion?: string },
  tenantId: string,
): Promise<Documento> {
  const creado = await api.post<DocumentoApi>(
    '/documents/',
    {
      title: input.titulo,
      document_type: input.tipo,
      classification: input.clasificacion ?? 'internal',
    },
    { tenantId },
  );
  return mapDocumento(creado);
}

interface EnlaceDeSubida {
  url: string;
  storage_key: string;
  expires_in: number;
  headers: Record<string, string>;
}

/**
 * SHA-256 del archivo, en hexadecimal.
 *
 * Se calcula **en el navegador y antes de subir** para que el hash pueda
 * viajar dentro de la firma: así el bucket comprueba el contenido y rechaza
 * la subida si no corresponde. Un hash que mandáramos después sería una
 * afirmación nuestra sobre un archivo que ya está guardado — sirve contra la
 * corrupción en el trayecto y no sirve para nada si quien sube miente.
 *
 * `crypto.subtle` **solo existe en contextos seguros**: HTTPS o `localhost`.
 * En un origen `http://` que no sea localhost no está definido, y por eso
 * quien llama decide qué hacer si esto no se puede calcular en vez de que la
 * subida entera falle.
 */
export async function sha256DelArchivo(archivo: File): Promise<string> {
  const bytes = await crypto.subtle.digest('SHA-256', await archivo.arrayBuffer());
  return Array.from(new Uint8Array(bytes))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/** Lo que la pantalla puede contar mientras sube, incluido el hash. */
export type PasoDeSubida = 'calculando-hash' | 'pidiendo-permiso' | 'subiendo' | 'confirmando';

/**
 * Sube un archivo y devuelve la revisión creada.
 *
 * `alAvanzar` existe porque los tres pasos tardan cosas muy distintas: pedir el
 * permiso son milisegundos, subir puede ser un minuto. Una sola rueda girando
 * durante todo eso no distingue "está subiendo" de "se colgó".
 */
export async function subirArchivo(
  documentoId: string,
  archivo: File,
  tenantId: string,
  alAvanzar?: (paso: PasoDeSubida) => void,
): Promise<RevisionDocumental> {
  // Si el navegador no puede calcularlo —origen sin contexto seguro— se sube
  // igual y la revisión queda sin checksum. Es preferible a bloquear la carga
  // de evidencia por una capacidad del entorno.
  alAvanzar?.('calculando-hash');
  let checksum: string | undefined;
  try {
    checksum = await sha256DelArchivo(archivo);
  } catch {
    checksum = undefined;
  }

  alAvanzar?.('pidiendo-permiso');
  const enlace = await api.post<EnlaceDeSubida>(
    `/documents/${documentoId}/upload-url`,
    {
      file_name: archivo.name,
      // Algunos navegadores dejan `type` vacío para extensiones que no conocen.
      // Se manda un genérico en vez de una cadena vacía: la API valida el tipo
      // y `''` no está en la lista blanca, así que rechazaría la subida por un
      // dato que el navegador no supo completar.
      mime_type: archivo.type || 'application/octet-stream',
      size_bytes: archivo.size,
      ...(checksum ? { checksum_sha256: checksum } : {}),
    },
    { tenantId },
  );

  alAvanzar?.('subiendo');
  // `fetch` directo y no `api`: esto va al bucket, no a nuestra API. Mandarle
  // el token de Clerk a un tercero sería filtrar la sesión.
  const respuesta = await fetch(enlace.url, {
    method: 'PUT',
    // Tal cual vienen: van dentro de la firma.
    headers: enlace.headers,
    body: archivo,
  });
  if (!respuesta.ok) {
    throw new Error(
      `El almacenamiento rechazó la subida (HTTP ${respuesta.status}). ` +
        'Si es 403, suele ser que faltan las reglas CORS del bucket para este origen.',
    );
  }

  alAvanzar?.('confirmando');
  const revision = await api.post<RevisionApi>(
    `/documents/${documentoId}/confirm-upload`,
    { storage_key: enlace.storage_key, file_name: archivo.name },
    { tenantId },
  );
  return mapRevision(revision);
}

export async function urlDeDescarga(
  documentoId: string,
  revisionId: string,
  tenantId: string,
): Promise<string> {
  const { url } = await api.get<{ url: string; expires_in: number }>(
    `/documents/${documentoId}/versions/${revisionId}/download-url`,
    { tenantId },
  );
  return url;
}

/** Las cinco transiciones del ciclo de vida (RF-104 a RF-106). */
export type AccionDocumental =
  | 'submit-review'
  | 'return-to-draft'
  | 'approve'
  | 'publish'
  | 'obsolete';

export async function moverRevision(
  documentoId: string,
  revisionId: string,
  accion: AccionDocumental,
  tenantId: string,
  cuerpo?: { motivo?: string; desde?: string },
): Promise<RevisionDocumental> {
  const revision = await api.post<RevisionApi>(
    `/documents/${documentoId}/versions/${revisionId}/${accion}`,
    cuerpo ?? {},
    { tenantId },
  );
  return mapRevision(revision);
}

/** Cómo se llama cada acción en un botón. */
export const ETIQUETA_ACCION: Record<AccionDocumental, string> = {
  'submit-review': 'Enviar a revisión',
  'return-to-draft': 'Devolver a borrador',
  approve: 'Aprobar',
  publish: 'Poner en vigencia',
  obsolete: 'Marcar obsoleta',
};

/**
 * Qué acción lleva de un estado al siguiente.
 *
 * Se deriva del estado **destino** y no de una lista aparte, para que no pueda
 * desincronizarse de `TRANSICIONES_REVISION` del paquete compartido.
 */
export const ACCION_HACIA: Record<EstadoRevision, AccionDocumental> = {
  // Se llega a `borrador` **devolviendo** una revisión que no pasó la revisión.
  // Esta entrada era `null` en la primera versión, y al escribirla apareció que
  // la API tampoco tenía el endpoint: `TRANSICIONES` declaraba
  // `en_revision → borrador` desde el principio y no había forma de hacerlo.
  borrador: 'return-to-draft',
  en_revision: 'submit-review',
  aprobado: 'approve',
  vigente: 'publish',
  obsoleto: 'obsolete',
};
