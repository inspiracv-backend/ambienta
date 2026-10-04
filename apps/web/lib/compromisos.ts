import { api } from '@/lib/api-client';

/**
 * Las salidas que la verificación de eficacia deja comprometidas: actualizar la
 * matriz de riesgos y oportunidades, la matriz FODA o un documento del sistema
 * de gestión (ISO 9001 §10.2.1 e y f).
 *
 * **Viven en el servidor desde el 4-oct.** Antes eran parte del JSON de la
 * etapa de seguimiento: el responsable era un texto sin clave foránea y no
 * había forma de preguntar qué le debe el sistema de gestión a la empresa —que
 * es justo lo que revisa un auditor—. Ahora son filas propias y sobreviven al
 * cierre del registro.
 */
export interface CompromisoApi {
  id: string;
  nonconformity_id: string;
  /** `matriz_riesgos` | `matriz_foda` | `documento_sgc`. */
  kind: string;
  descripcion: string | null;
  status: 'pendiente' | 'ejecutada' | 'descartada';
  responsable_user_id: string | null;
  responsable_nombre: string | null;
  due_date: string | null;
  justificacion: string | null;
  completada_en: string | null;
  nonconformity_code: string | null;
  nonconformity_title: string | null;
}

const BASE = '/audits';

export function cargarCompromisos(ncId: string, tenantId: string) {
  return api.get<CompromisoApi[]>(`${BASE}/nonconformities/${ncId}/compromisos`, { tenantId });
}

export function comprometerSalida(
  ncId: string,
  cuerpo: { kind: string; descripcion?: string | null },
  tenantId: string,
) {
  return api.post<CompromisoApi>(`${BASE}/nonconformities/${ncId}/compromisos`, cuerpo, { tenantId });
}

export function actualizarCompromiso(
  id: string,
  cuerpo: Partial<Pick<CompromisoApi, 'responsable_user_id' | 'due_date' | 'status' | 'justificacion' | 'descripcion'>>,
  tenantId: string,
) {
  return api.patch<CompromisoApi>(`${BASE}/compromisos/${id}`, cuerpo, { tenantId });
}

/**
 * Lo que el sistema de gestión todavía debe, de toda la empresa.
 *
 * Sin `limit`: el cliente completa la lista cuando la API la corta, y una lista
 * de pendientes a medias se lee como "ya no queda nada".
 */
export function cargarPendientesDeLaEmpresa(tenantId: string) {
  return api.get<CompromisoApi[]>(`${BASE}/compromisos?estado=pendiente`, { tenantId });
}
