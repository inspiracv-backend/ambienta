'use client';

import { useEffect, useState } from 'react';
import { FEATURE_FLAGS } from '@ambienta/shared';
import { api, mensajeDeError } from '@/lib/api-client';

/**
 * Lo que vence y **no es una tarea de obligación**: la revisión periódica de
 * cada norma de la matriz (ISO 14001 §9.1.2) y la inscripción de los equipos
 * regulados. El calendario solo mostraba tareas, así que estas fechas —que la
 * base ya tenía o podía calcular— no aparecían en ningún lado.
 *
 * **La fecha va como texto `AAAA-MM-DD` y se compara como texto.** Pasarla por
 * `new Date()` la lee como medianoche UTC, que en Chile es el día anterior: el
 * error que este repositorio ya tuvo con los documentos (`lib/fechas.ts`).
 */
export interface EventoDeCalendario {
  id: string;
  /** Día de calendario, `AAAA-MM-DD`. */
  fecha: string;
  titulo: string;
  tipo: 'revision_norma' | 'inscripcion_equipo';
  href: string;
  vencido: boolean;
}

/** Una norma que no se puede poner en el calendario, y por qué. */
export interface RevisionSinFecha {
  id: string;
  titulo: string;
  motivo: string;
}

export const MOTIVO_SIN_FECHA: Record<string, string> = {
  nunca_evaluada: 'Nunca se evaluó: no hay desde dónde contar.',
  evaluada_sin_fecha: 'Se evaluó, pero sin fecha registrada.',
  por_evento: 'Se revisa por evento, no periódicamente.',
};

export const PREFIJO: Record<EventoDeCalendario['tipo'], string> = {
  revision_norma: 'Revisión',
  inscripcion_equipo: 'Vence inscripción',
};

/** El día de calendario de una celda, en la hora local de quien mira. */
export function claveDeDia(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${dd}`;
}

interface FilaRevision {
  matrix_norm_id: string;
  titulo: string;
  proxima_revision: string | null;
  motivo_sin_fecha: string | null;
  vencida: boolean;
}

interface FilaEquipo {
  id: string;
  name: string;
  registration_expires_at: string | null;
}

export function eventosDeRevisiones(filas: FilaRevision[]): {
  eventos: EventoDeCalendario[];
  sinFecha: RevisionSinFecha[];
} {
  const eventos: EventoDeCalendario[] = [];
  const sinFecha: RevisionSinFecha[] = [];
  for (const f of filas) {
    if (f.proxima_revision) {
      eventos.push({
        id: `revision-${f.matrix_norm_id}`,
        fecha: f.proxima_revision.slice(0, 10),
        titulo: f.titulo,
        tipo: 'revision_norma',
        href: '/matriz-legal',
        vencido: f.vencida,
      });
    } else {
      sinFecha.push({
        id: f.matrix_norm_id,
        titulo: f.titulo,
        motivo: MOTIVO_SIN_FECHA[f.motivo_sin_fecha ?? ''] ?? f.motivo_sin_fecha ?? 'Sin fecha.',
      });
    }
  }
  return { eventos, sinFecha };
}

export function eventosDeEquipos(filas: FilaEquipo[], hoy: string): EventoDeCalendario[] {
  return filas
    .filter((e) => e.registration_expires_at)
    .map((e) => {
      const fecha = String(e.registration_expires_at).slice(0, 10);
      return {
        id: `equipo-${e.id}`,
        fecha,
        titulo: e.name,
        tipo: 'inscripcion_equipo' as const,
        href: '/equipos-regulados',
        vencido: fecha < hoy,
      };
    });
}

/**
 * Los dos orígenes, pedidos por separado: si uno falla el otro se muestra igual,
 * y el fallo **se dice**. Un calendario sin revisiones porque la consulta falló
 * se vería igual que uno sin revisiones pendientes.
 */
export function useEventosDeCalendario(tenantId: string | null) {
  const [eventos, setEventos] = useState<EventoDeCalendario[]>([]);
  const [sinFecha, setSinFecha] = useState<RevisionSinFecha[]>([]);
  const [errores, setErrores] = useState<string[]>([]);

  useEffect(() => {
    if (!tenantId) return;
    let cancelado = false;
    const hoy = claveDeDia(new Date());
    const fallos: string[] = [];

    const revisiones = api
      .get<FilaRevision[]>('/compliance/matrix-norms/revisiones', { tenantId })
      .then(eventosDeRevisiones)
      .catch((e: unknown) => {
        fallos.push(`revisiones de normas: ${mensajeDeError(e)}`);
        return { eventos: [], sinFecha: [] };
      });
    const equipos = FEATURE_FLAGS.matricesIso
      ? api
          .get<FilaEquipo[]>('/iso14001/equipment?limit=500', { tenantId })
          .then((filas) => eventosDeEquipos(filas, hoy))
          .catch((e: unknown) => {
            fallos.push(`equipos regulados: ${mensajeDeError(e)}`);
            return [] as EventoDeCalendario[];
          })
      : Promise.resolve([] as EventoDeCalendario[]);

    void Promise.all([revisiones, equipos]).then(([r, eq]) => {
      if (cancelado) return;
      setEventos([...r.eventos, ...eq]);
      setSinFecha(r.sinFecha);
      setErrores(fallos);
    });
    return () => {
      cancelado = true;
    };
  }, [tenantId]);

  return { eventos, sinFecha, errores };
}
