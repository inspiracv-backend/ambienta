'use client';

import { useEffect, useState } from 'react';
import { api, mensajeDeError } from '@/lib/api-client';
import type { NotificationPreferencesFormProps } from './NotificationPreferencesForm.types';

/**
 * Las ventanas que usa el generador cuando la empresa no declaró las suyas.
 *
 * **Copia de `VENTANAS_POR_DEFECTO` en `apps/api/app/services/avisos_de_vencimiento.py`.**
 * Si cambia allá, cambia acá. La pantalla anterior decía 30, 15 y 7 — que no
 * era lo que se mandaba.
 */
const VENTANAS_POR_DEFECTO = [15, 7, 3, 1];
const EVENTO = 'obligation_due';

interface Regla {
  event_type: string;
  lead_minutes: number;
  active: boolean;
}

/** Los días que usa esta empresa: mismo cálculo que `ventanas_de` en la API. */
export function ventanasDe(reglas: Regla[]): { dias: number[]; porDefecto: boolean } {
  const dias = new Set<number>();
  reglas
    .filter((r) => r.event_type === EVENTO && r.active && r.lead_minutes > 0)
    .forEach((r) => dias.add(Math.floor(r.lead_minutes / 1440)));
  // `lead_minutes` menor a un día da 0 y la API lo descarta igual.
  dias.delete(0);
  if (dias.size === 0) return { dias: VENTANAS_POR_DEFECTO, porDefecto: true };
  return { dias: Array.from(dias).sort((a, b) => b - a), porDefecto: false };
}

function listar(dias: number[]): string {
  const textos = dias.map(String);
  if (textos.length === 1) return textos[0];
  return `${textos.slice(0, -1).join(', ')} y ${textos[textos.length - 1]}`;
}

/**
 * S-32 Configuración de Notificaciones — **de solo lectura desde el 13-sep.**
 *
 * Antes era un formulario de preferencias por persona (canal y anticipación)
 * con "Guardar" y "Guardado.", pero **no había dónde guardarlo**: ni tabla ni
 * endpoint, se perdía al recargar. Y el generador de avisos no lo habría leído
 * aunque existiera: manda siempre por los dos canales, con las ventanas de la
 * empresa.
 *
 * Ahora dice lo que de verdad pasa. Las preferencias por persona quedan para
 * después de la 1.0, con modelo propio.
 */
export function NotificationPreferencesForm({ tenantId }: NotificationPreferencesFormProps) {
  const [ventanas, setVentanas] = useState<{ dias: number[]; porDefecto: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    api
      .get<Regla[]>('/notifications/rules', { tenantId })
      .then((reglas) => { if (!cancelado) setVentanas(ventanasDe(reglas)); })
      .catch((e) => { if (!cancelado) setError(mensajeDeError(e)); });
    return () => { cancelado = true; };
  }, [tenantId]);

  return (
    <div className="flex max-w-md flex-col gap-6">
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-1 text-sm font-semibold text-slate-700">Canales</h2>
        <p className="text-sm text-slate-600">
          Los avisos de vencimiento llegan <strong>por correo y dentro de la plataforma</strong>, siempre por los dos.
        </p>
      </div>

      <div className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-1 text-sm font-semibold text-slate-700">Anticipación</h2>
        {error ? (
          <p className="text-sm text-semaforo-no-cumple">No se pudieron cargar las reglas de la empresa: {error}</p>
        ) : !ventanas ? (
          <p className="text-sm text-slate-500">Cargando…</p>
        ) : (
          <p className="text-sm text-slate-600">
            Se avisa <strong>{listar(ventanas.dias)} {ventanas.dias.length === 1 && ventanas.dias[0] === 1 ? 'día' : 'días'}</strong> antes de cada vencimiento
            {ventanas.porDefecto ? ' (valores por defecto: la empresa no declaró los suyos).' : ', según las reglas de la empresa.'}
          </p>
        )}
      </div>

      <p className="text-xs text-slate-500">
        La anticipación es de la empresa, no de cada persona. Elegir canales y días por persona todavía no está disponible.
      </p>
    </div>
  );
}
