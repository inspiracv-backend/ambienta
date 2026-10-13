import { api } from '@/lib/api-client';

/**
 * El informe de una auditoría (RF-101, #42), contra `GET /audits/{id}/informe`.
 *
 * La API lo arma desde el 4-sep —resumen, una fila por proceso, tasa de cierre
 * del ciclo anterior— y **ninguna pantalla lo pedía**. Y los veredictos por
 * proceso, que son lo único que escribe el auditor, no tenían dónde escribirse:
 * toda fila habría salido `no_auditado` para siempre.
 */

export type Clasificacion = 'conforme' | 'conforme_con_observaciones' | 'no_conforme' | 'no_auditado';

export const CLASIFICACION_LABEL: Record<Clasificacion, string> = {
  conforme: 'Conforme',
  conforme_con_observaciones: 'Conforme con observaciones',
  no_conforme: 'No conforme',
  no_auditado: 'No auditado',
};

export interface FilaDeLaMatriz {
  proceso_id: string;
  proceso_nombre: string;
  clausulas_auditadas: string[];
  items: number;
  items_conformes: number;
  items_no_conformes: number;
  hallazgos: string[];
  clasificacion: Clasificacion;
  conclusion: string | null;
  evidencia_revisada: string | null;
}

export interface InformeDeAuditoria {
  audit_id: string;
  codigo: string;
  titulo: string;
  estado: string;
  resumen: {
    procesos_auditados: number;
    items_sin_proceso: number;
    no_conformidades: number;
    observaciones: number;
    oportunidades_de_mejora: number;
    /** `null` = no se evaluó ninguna pregunta. **No es 0 %.** */
    conformidad: number | null;
  };
  matriz: FilaDeLaMatriz[];
  tasa_de_cierre_del_ciclo_anterior: number | null;
  motivo_sin_tasa: string | null;
  auditoria_anterior_id: string | null;
}

interface VeredictoApi {
  id: string;
  process_id: string;
}

export interface DatosDeVeredicto {
  classification: Clasificacion;
  conclusion: string | null;
  evidence_reviewed: string | null;
}

/**
 * Un porcentaje para mostrar, o «Sin evaluar».
 *
 * La API ya manda porcentajes (0–100, un decimal) o `null`. **No se adivina la
 * escala**: una primera versión multiplicaba por 100 lo que valiera 1 o menos,
 * y un 1 % real se habría mostrado como 100 %. El `null` no se redondea a cero:
 * es la acusación que este repositorio ya hizo cuatro veces.
 */
export function porcentaje(valor: number | null): string {
  if (valor === null) return 'Sin evaluar';
  return `${valor.toLocaleString('es-CL', { maximumFractionDigits: 1 })} %`;
}

export function cargarInforme(auditId: string, tenantId: string) {
  return api.get<InformeDeAuditoria>(`/audits/${auditId}/informe`, { tenantId });
}

/**
 * Guarda el veredicto de un proceso: crea si no hay, edita si ya hay.
 *
 * Se pregunta la lista antes en vez de intentar crear y caer al 409: el 409
 * existe para que no haya dos veredictos, no como forma de averiguar si ya hay
 * uno.
 */
export async function guardarVeredicto(
  auditId: string,
  procesoId: string,
  datos: DatosDeVeredicto,
  tenantId: string,
): Promise<void> {
  const existentes = await api.get<VeredictoApi[]>(`/audits/${auditId}/procesos`, { tenantId });
  const actual = existentes.find((v) => String(v.process_id) === procesoId);
  if (actual) {
    await api.patch(`/audits/${auditId}/procesos/${actual.id}`, datos, { tenantId });
  } else {
    await api.post(`/audits/${auditId}/procesos`, { process_id: procesoId, ...datos }, { tenantId });
  }
}
