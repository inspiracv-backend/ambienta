'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api-client';

/**
 * El estado del Perfil Empresa, **leído del servidor** (RF-10).
 *
 * ## Por qué no se calcula acá
 *
 * Antes se calculaba en el navegador:
 *
 * ```ts
 * perfilEmpresaCompleto = Boolean(business_activity && rut_tax_id)
 * ```
 *
 * `rut_tax_id` es `NOT NULL` en la base, así que nunca falta: la condición
 * colapsaba a «tiene giro», y las dos empresas del seed lo tienen. **La marca
 * daba `true` para todas y el gate no bloqueaba a nadie** — nunca se le vio
 * funcionar contra datos reales.
 *
 * Ahora el criterio vive en un solo lado. Si la pantalla lo recalculara,
 * volveríamos a tener dos verdades que se pueden contradecir: la API bloquearía
 * una escritura que el navegador cree permitida, y la persona vería un 409 sin
 * entender por qué.
 *
 * ## Mientras carga no se decide nada
 *
 * `cargando` empieza en `true` y quien lo use **no debe redirigir hasta que
 * termine**. Tratar «todavía no sé» como «incompleto» mandaría a todo el mundo
 * al wizard en cada carga de página.
 */
export interface PerfilEmpresa {
  completo: boolean;
  faltantes: string[];
  tieneGiro: boolean;
  tieneInstalaciones: boolean;
  tieneDepartamentos: boolean;
  tieneSector: boolean;
}

interface RespuestaMe {
  perfil_empresa?: {
    completo: boolean;
    faltantes: string[];
    tiene_giro: boolean;
    tiene_instalaciones: boolean;
    tiene_departamentos: boolean;
    tiene_sector: boolean;
  };
}

export function usePerfilEmpresa(tenantId: string | null | undefined) {
  const [perfil, setPerfil] = useState<PerfilEmpresa | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!tenantId) {
      setCargando(false);
      return;
    }

    let vigente = true;
    setCargando(true);

    api
      .get<RespuestaMe>('/me', { tenantId })
      .then((r) => {
        if (!vigente) return;
        const p = r.perfil_empresa;
        setPerfil(
          p
            ? {
                completo: p.completo,
                faltantes: p.faltantes,
                tieneGiro: p.tiene_giro,
                tieneInstalaciones: p.tiene_instalaciones,
                tieneDepartamentos: p.tiene_departamentos,
                tieneSector: p.tiene_sector,
              }
            : null,
        );
      })
      .catch(() => {
        // **Sin respuesta no se bloquea a nadie.** Si la API está caída, el
        // gate no tiene forma de saber si el perfil está completo, y mandar a
        // todo el mundo al wizard convertiría una caída en un bloqueo total.
        if (vigente) setPerfil(null);
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });

    return () => {
      vigente = false;
    };
  }, [tenantId]);

  return { perfil, cargando };
}
