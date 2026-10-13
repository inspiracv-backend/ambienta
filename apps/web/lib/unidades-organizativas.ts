'use client';

import { useEffect, useState } from 'react';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';

/**
 * Los departamentos **organizativos** de la empresa (`/departments/`).
 *
 * ## Por qué no son los de `departamentos-store`
 *
 * Ese store maneja el **mapa de procesos** (`/processes/`, ISO 9001 §4.4), que
 * la pantalla también llama "departamentos". Pero `users.department_id` apunta a
 * `departments`, y la API valida contra esa tabla. Hasta el 14-sep el alta y la
 * edición de usuarios ofrecían **procesos** como departamento: sus ids no están
 * en `departments` (medido: 0 de 4 en común), así que toda persona interna
 * invitada o editada con departamento se rechazaba.
 */
export interface UnidadOrganizativa {
  id: string;
  nombre: string;
}

export function useUnidadesOrganizativas() {
  const { user } = useSession();
  const tenantId = user?.tenantId ?? null;
  const [unidades, setUnidades] = useState<UnidadOrganizativa[]>([]);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);

  useEffect(() => {
    if (!tenantId) return;
    let vigente = true;
    api
      .get<Record<string, unknown>[]>('/departments/', { tenantId })
      .then((filas) => {
        if (!vigente) return;
        setUnidades(
          filas
            .filter((f) => f.active !== false)
            .map((f) => ({ id: String(f.id), nombre: String(f.name ?? f.code ?? '') })),
        );
        setErrorDeCarga(null);
      })
      .catch((e) => {
        if (vigente) setErrorDeCarga(mensajeDeError(e));
      });
    return () => {
      vigente = false;
    };
  }, [tenantId]);

  return { unidades, errorDeCarga };
}
