'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api-client';
import { fechaDeInstante } from '@/lib/fechas';

interface Corrida {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  norms_created: number;
  norms_updated: number;
  response_metadata: { sin_su_norma?: string[] };
}

const ESTADO: Record<string, { texto: string; clase: string }> = {
  success: { texto: 'completa', clase: 'text-semaforo-cumple' },
  partial: { texto: 'parcial', clase: 'text-semaforo-parcial' },
  failed: { texto: 'fallida', clase: 'text-semaforo-no-cumple' },
  running: { texto: 'en curso', clase: 'text-slate-600' },
};

/**
 * De dónde salió el catálogo y cuándo (`ingesta-normativa-bcn`).
 *
 * `norm_sync_runs` existía y **nadie la escribía ni la mostraba**: quien miraba
 * el catálogo no podía saber si estaba al día. Una lista vacía se dice como
 * "nunca se sincronizó", no como "al día".
 *
 * Si la consulta falla no se muestra nada: esta línea informa, no bloquea, y un
 * error acá no debe tapar el catálogo.
 */
export function UltimaSincronizacionBcn() {
  const [corrida, setCorrida] = useState<Corrida | null | undefined>(undefined);

  useEffect(() => {
    api
      .get<Corrida[]>('/catalog/sync-runs?limite=1')
      .then((filas) => setCorrida(filas[0] ?? null))
      .catch(() => setCorrida(undefined));
  }, []);

  if (corrida === undefined) return null;

  if (corrida === null) {
    return (
      <p className="text-xs text-slate-500">
        El catálogo todavía no registra ninguna sincronización con la BCN.
      </p>
    );
  }

  const estado = ESTADO[corrida.status] ?? { texto: corrida.status, clase: 'text-slate-600' };
  const faltantes = corrida.response_metadata?.sin_su_norma ?? [];

  return (
    <p className="text-xs text-slate-500">
      Última sincronización con la BCN: {fechaDeInstante(corrida.finished_at ?? corrida.started_at)} ·{' '}
      <span className={`font-medium ${estado.clase}`}>{estado.texto}</span> · {corrida.norms_created} nuevas,{' '}
      {corrida.norms_updated} actualizadas
      {faltantes.length > 0 ? ` · no se encontró: ${faltantes.join(', ')}` : ''}
    </p>
  );
}
