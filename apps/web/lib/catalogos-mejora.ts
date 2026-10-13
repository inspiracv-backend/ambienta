'use client';

import { useCallback, useEffect, useState } from 'react';
import type { FormaMetodologia } from '@ambienta/shared';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';

/**
 * Los catálogos del registro de mejora de la empresa (RF-100, #41).
 *
 * La API los tiene desde el 4-sep (`db/25`) y **no había pantalla**: la escala
 * de severidad era la sembrada para todos, y `days_to_close` —el plazo que hace
 * que las etapas tengan fecha límite y avisen— no lo podía declarar nadie. O
 * sea que el mecanismo de plazos existía entero y no se podía encender.
 */

export interface NivelDeSeveridad {
  id: string;
  code: string;
  label: string;
  rank: number;
  /** `null` = la empresa no declaró plazo. **No es cero.** */
  daysToClose: number | null;
  active: boolean;
}

export interface MetodologiaDeCausa {
  id: string;
  code: string;
  name: string;
  shape: FormaMetodologia;
  active: boolean;
}

export type Resultado = { ok: true } | { ok: false; error: string };

const BASE = '/audits/catalogos';

function nivelDesdeApi(raw: Record<string, unknown>): NivelDeSeveridad {
  return {
    id: String(raw.id),
    code: String(raw.code),
    label: String(raw.label),
    rank: Number(raw.rank ?? 0),
    daysToClose: typeof raw.days_to_close === 'number' ? raw.days_to_close : null,
    active: raw.active !== false,
  };
}

function metodologiaDesdeApi(raw: Record<string, unknown>): MetodologiaDeCausa {
  return {
    id: String(raw.id),
    code: String(raw.code),
    name: String(raw.name),
    shape: raw.shape as FormaMetodologia,
    active: raw.active !== false,
  };
}

/**
 * Lee un plazo escrito en un campo. `''` → `null` (sin plazo). Devuelve
 * `undefined` si no es un entero positivo, para que la pantalla lo rechace en
 * vez de mandar un 0 que la API respondería con 422 —o peor, un plazo que nadie
 * quiso declarar—.
 */
export function plazoDesdeCampo(valor: string): number | null | undefined {
  const t = valor.trim();
  if (t === '') return null;
  if (!/^\d+$/.test(t)) return undefined;
  const n = Number(t);
  return n > 0 ? n : undefined;
}

export function useCatalogosDeMejora() {
  const { user } = useSession();
  const tenantId = user?.tenantId ?? null;
  const [niveles, setNiveles] = useState<NivelDeSeveridad[]>([]);
  const [metodologias, setMetodologias] = useState<MetodologiaDeCausa[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (!tenantId) {
      setCargando(false);
      return;
    }
    setCargando(true);
    try {
      // `solo_activas=false`: la pantalla de configuración tiene que mostrar
      // también lo retirado, o no hay forma de volver a activarlo.
      const [s, m] = await Promise.all([
        api.get<Record<string, unknown>[]>(`${BASE}/severidades?solo_activas=false`, { tenantId }),
        api.get<Record<string, unknown>[]>(`${BASE}/metodologias`, { tenantId }),
      ]);
      setNiveles(s.map(nivelDesdeApi).sort((a, b) => a.rank - b.rank));
      setMetodologias(m.map(metodologiaDesdeApi));
      setErrorDeCarga(null);
    } catch (e) {
      setErrorDeCarga(mensajeDeError(e));
    } finally {
      setCargando(false);
    }
  }, [tenantId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function ejecutar(accion: () => Promise<unknown>): Promise<Resultado> {
    if (!tenantId) return { ok: false, error: 'La sesión no tiene empresa.' };
    try {
      await accion();
      await cargar();
      return { ok: true };
    } catch (e) {
      return { ok: false, error: mensajeDeError(e) };
    }
  }

  return {
    niveles,
    metodologias,
    cargando,
    errorDeCarga,
    editarNivel: (id: string, cambios: { label?: string; daysToClose?: number | null; active?: boolean }) =>
      ejecutar(() =>
        api.patch(
          `${BASE}/severidades/${id}`,
          {
            ...(cambios.label !== undefined ? { label: cambios.label } : {}),
            // `null` explícito: es "quitar el plazo", y omitirlo sería "no tocarlo".
            ...(cambios.daysToClose !== undefined ? { days_to_close: cambios.daysToClose } : {}),
            ...(cambios.active !== undefined ? { active: cambios.active } : {}),
          },
          { tenantId: tenantId! },
        ),
      ),
    // Sin `crearNivel` a propósito: el `code` de un nivel es el valor que se
    // guarda en el hallazgo, y el CHECK de `nonconformities.severity` solo
    // admite `minor`, `major` y `critical`, que ya existen. Ofrecer "agregar
    // nivel" sería un botón que siempre falla.
    editarMetodologia: (id: string, cambios: { name?: string; shape?: FormaMetodologia; active?: boolean }) =>
      ejecutar(() => api.patch(`${BASE}/metodologias/${id}`, cambios, { tenantId: tenantId! })),
    crearMetodologia: (datos: { code: string; name: string; shape: FormaMetodologia }) =>
      ejecutar(() => api.post(`${BASE}/metodologias`, datos, { tenantId: tenantId! })),
  };
}
