import type {
  EtapaAccionCorrectiva,
  EtapaAnalisisCausa,
  EtapaCorreccion,
  EtapaSeguimiento,
  FormaMetodologia,
  SalidaTratamiento,
} from '@ambienta/shared';
import { api } from '@/lib/api-client';

/**
 * Las etapas del registro de mejora, **contra la tabla tipada** (#27, decisión #57).
 *
 * Hasta el 13-sep el panel leía y escribía `nonconformities.improvement_stages`,
 * el JSONB provisorio. La API ya tenía `improvement_stage_entries` desde el
 * 12-sep —con el responsable como clave foránea y el cierre calculado en el
 * servidor— y la pantalla no la usaba: lo que se guardaba no era lo que el
 * cierre miraba.
 *
 * **Una etapa se da por completada cuando tiene fecha de ejecución**, y eso lo
 * decide el servidor (`completada_en`). Por eso cada etapa de la pantalla tiene
 * un campo de fecha que manda: sin él, la etapa queda pendiente y el registro no
 * se puede cerrar.
 */

export type TipoEtapa = 'registro' | 'correccion' | 'analisis_causa' | 'accion_correctiva' | 'seguimiento';

export interface EtapaApi {
  id: string;
  kind: TipoEtapa;
  responsable_user_id: string | null;
  responsable_nombre?: string | null;
  metodologia_id: string | null;
  fecha_ejecucion: string | null;
  due_date: string | null;
  completada_en: string | null;
  eficaz: boolean | null;
  causa_se_repitio: boolean | null;
  cumplio_proposito: boolean | null;
  requiere_actualizar_riesgos: boolean | null;
  requiere_cambios_sgc: boolean | null;
  observaciones: string | null;
  evidencia_urls: string[];
  datos: Record<string, unknown>;
}

export interface CicloEnPantalla {
  correccion?: EtapaCorreccion;
  analisisCausa?: EtapaAnalisisCausa;
  accionCorrectiva?: EtapaAccionCorrectiva;
  seguimiento?: EtapaSeguimiento;
}

export interface Metodologia {
  id: string;
  nombre: string;
  forma: FormaMetodologia;
}

export interface Severidad {
  code: string;
  label: string;
}

export interface EstadoDeCierre {
  puede: boolean;
  motivo: string | null;
}

const texto = (v: unknown): string | undefined => (typeof v === 'string' && v !== '' ? v : undefined);
const triestado = (v: unknown): boolean | null => (typeof v === 'boolean' ? v : null);
const vacioANull = (v: string | undefined): string | null => (v ? v : null);

export function cicloDesdeApi(filas: EtapaApi[]): CicloEnPantalla {
  const por = new Map(filas.map((f) => [f.kind, f]));
  const ciclo: CicloEnPantalla = {};

  const c = por.get('correccion');
  if (c) {
    ciclo.correccion = {
      correccionInmediata: texto(c.datos.correccionInmediata) ?? '',
      fechaEjecucion: c.fecha_ejecucion ?? undefined,
      evidencia: texto(c.datos.evidencia),
      evidenciaUrls: c.evidencia_urls ?? [],
      responsableEtapaId: c.responsable_user_id ?? undefined,
    };
  }

  const a = por.get('analisis_causa');
  if (a) {
    const porques = Array.isArray(a.datos.cincoPorques) ? (a.datos.cincoPorques as string[]) : [];
    const pescado = a.datos.espinaPescado as EtapaAnalisisCausa['espinaPescado'];
    ciclo.analisisCausa = {
      metodologiaId: a.metodologia_id ?? '',
      // Cinco casilleros siempre: la pantalla los muestra fijos y un arreglo
      // más corto dejaría escalones sin campo donde escribir.
      cincoPorques: [0, 1, 2, 3, 4].map((i) => porques[i] ?? ''),
      ...(pescado ? { espinaPescado: pescado } : {}),
      causaRaiz: texto(a.datos.causaRaiz) ?? '',
      responsableEtapaId: a.responsable_user_id ?? undefined,
      fechaEjecucion: a.fecha_ejecucion ?? undefined,
    };
  }

  const k = por.get('accion_correctiva');
  if (k) {
    ciclo.accionCorrectiva = {
      severidad: texto(k.datos.severidad) ?? '',
      tipoAccion: k.datos.tipoAccion === 'preventiva' ? 'preventiva' : 'correctiva',
      descripcionAccion: texto(k.datos.descripcionAccion) ?? '',
      evidenciaAccion: texto(k.datos.evidenciaAccion),
      fechaInicial: texto(k.datos.fechaInicial),
      // La fecha de finalización **es** la de ejecución: es la que completa la etapa.
      fechaFinalizacion: k.fecha_ejecucion ?? undefined,
      responsableEtapaId: k.responsable_user_id ?? undefined,
      evidenciaUrls: k.evidencia_urls ?? [],
    };
  }

  const s = por.get('seguimiento');
  if (s) {
    ciclo.seguimiento = {
      eficaz: s.eficaz,
      causaSeRepitio: s.causa_se_repitio,
      cumplioProposito: s.cumplio_proposito,
      requiereActualizarRiesgos: s.requiere_actualizar_riesgos,
      requiereCambiosSGC: s.requiere_cambios_sgc,
      // No tiene columna: es la única pregunta que no es de §10.2.1.
      requiereActualizarFoda: triestado(s.datos.requiereActualizarFoda),
      salidas: Array.isArray(s.datos.salidas) ? (s.datos.salidas as SalidaTratamiento[]) : [],
      observaciones: s.observaciones ?? undefined,
      fechaSeguimiento: s.fecha_ejecucion ?? undefined,
      responsableEtapaId: s.responsable_user_id ?? undefined,
      evidenciaUrls: s.evidencia_urls ?? [],
    };
  }
  return ciclo;
}

/**
 * El cuerpo del `PATCH` de una etapa.
 *
 * **Los vacíos van como `null`, no como `''`.** `metodologia_id` y
 * `responsable_user_id` son UUID: una cadena vacía responde 422, y una fecha
 * vacía no es "sin fecha" para Pydantic.
 */
export function cuerpoDe(kind: TipoEtapa, ciclo: CicloEnPantalla): Record<string, unknown> | null {
  switch (kind) {
    case 'correccion': {
      const e = ciclo.correccion;
      if (!e) return null;
      return {
        responsable_user_id: vacioANull(e.responsableEtapaId),
        fecha_ejecucion: vacioANull(e.fechaEjecucion),
        evidencia_urls: e.evidenciaUrls ?? [],
        datos: { correccionInmediata: e.correccionInmediata, evidencia: e.evidencia ?? '' },
      };
    }
    case 'analisis_causa': {
      const e = ciclo.analisisCausa;
      if (!e) return null;
      return {
        responsable_user_id: vacioANull(e.responsableEtapaId),
        metodologia_id: vacioANull(e.metodologiaId),
        fecha_ejecucion: vacioANull(e.fechaEjecucion),
        datos: {
          cincoPorques: e.cincoPorques,
          espinaPescado: e.espinaPescado ?? null,
          causaRaiz: e.causaRaiz,
        },
      };
    }
    case 'accion_correctiva': {
      const e = ciclo.accionCorrectiva;
      if (!e) return null;
      return {
        responsable_user_id: vacioANull(e.responsableEtapaId),
        fecha_ejecucion: vacioANull(e.fechaFinalizacion),
        evidencia_urls: e.evidenciaUrls ?? [],
        datos: {
          severidad: e.severidad,
          tipoAccion: e.tipoAccion,
          descripcionAccion: e.descripcionAccion,
          evidenciaAccion: e.evidenciaAccion ?? '',
          fechaInicial: e.fechaInicial ?? '',
        },
      };
    }
    case 'seguimiento': {
      const e = ciclo.seguimiento;
      if (!e) return null;
      return {
        responsable_user_id: vacioANull(e.responsableEtapaId),
        fecha_ejecucion: vacioANull(e.fechaSeguimiento),
        observaciones: e.observaciones ?? null,
        evidencia_urls: e.evidenciaUrls ?? [],
        // Tri-estado de punta a punta: `null` viaja como `null`, nunca como `false`.
        eficaz: e.eficaz,
        causa_se_repitio: e.causaSeRepitio,
        cumplio_proposito: e.cumplioProposito,
        requiere_actualizar_riesgos: e.requiereActualizarRiesgos,
        requiere_cambios_sgc: e.requiereCambiosSGC,
        datos: { requiereActualizarFoda: e.requiereActualizarFoda, salidas: e.salidas },
      };
    }
    default:
      // `registro` no se edita desde la pantalla: se cumple al registrar.
      return null;
  }
}

/** Qué etapas cambiaron respecto de lo que la base devolvió. Solo esas se mandan. */
export function etapasCambiadas(
  filas: EtapaApi[],
  ciclo: CicloEnPantalla,
): { etapa: EtapaApi; cuerpo: Record<string, unknown> }[] {
  const guardado = cicloDesdeApi(filas);
  const salida: { etapa: EtapaApi; cuerpo: Record<string, unknown> }[] = [];
  for (const etapa of filas) {
    const cuerpo = cuerpoDe(etapa.kind, ciclo);
    if (!cuerpo) continue;
    if (JSON.stringify(cuerpo) !== JSON.stringify(cuerpoDe(etapa.kind, guardado))) {
      salida.push({ etapa, cuerpo });
    }
  }
  return salida;
}

const BASE = '/audits/nonconformities';

export function cargarEtapas(ncId: string, tenantId: string) {
  return api.get<EtapaApi[]>(`${BASE}/${ncId}/etapas`, { tenantId });
}

export function iniciarCiclo(ncId: string, tenantId: string) {
  return api.post<EtapaApi[]>(`${BASE}/${ncId}/etapas`, {}, { tenantId });
}

export function guardarEtapa(ncId: string, etapaId: string, cuerpo: Record<string, unknown>, tenantId: string) {
  return api.patch<EtapaApi>(`${BASE}/${ncId}/etapas/${etapaId}`, cuerpo, { tenantId });
}

export function consultarCierre(ncId: string, tenantId: string) {
  return api.get<EstadoDeCierre>(`${BASE}/${ncId}/puede-cerrarse`, { tenantId });
}

export async function cargarCatalogos(tenantId: string): Promise<{ metodologias: Metodologia[]; severidades: Severidad[] }> {
  const [metodologias, severidades] = await Promise.all([
    api.get<Record<string, unknown>[]>('/audits/catalogos/metodologias', { tenantId }),
    api.get<Record<string, unknown>[]>('/audits/catalogos/severidades', { tenantId }),
  ]);
  return {
    // `/catalogos/metodologias` devuelve también las retiradas (la pantalla de
    // catálogos las necesita); ofrecer una retirada sería volver a usarla.
    metodologias: metodologias.filter((m) => m.active !== false).map((m) => ({
      id: String(m.id),
      nombre: String(m.name ?? m.code),
      forma: m.shape as FormaMetodologia,
    })),
    severidades: severidades.map((s) => ({ code: String(s.code), label: String(s.label ?? s.code) })),
  };
}
