'use client';

import { useEffect, useId, useState } from 'react';
import { Compass } from 'lucide-react';
import type { Tenant } from '@ambienta/shared';
import { Button } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useTenants } from '@/lib/tenants-store';
import { cargarSectores, TRAMOS, type Sector, type Tramo } from '@/lib/perfil-normativo';

/**
 * Declara el sector CIIU y el tramo de la empresa (7.1, 7.5).
 *
 * ## Por qué esta tarjeta existe aparte del alta
 *
 * El alta pide el sector **desde ahora**. Las empresas que ya estaban nacieron
 * sin él —la columna es nueva— y no había ninguna pantalla donde declararlo.
 * El sistema informaba correctamente que faltaba el dato y no ofrecía camino
 * para completarlo, que es una forma elegante de no funcionar: toda empresa
 * existente quedaba en `sin_perfil` para siempre.
 *
 * ## Por qué el sector no es el giro
 *
 * El giro es texto libre y describe a qué se dedica la empresa. El sector CIIU
 * tiene código estable y **es contra el que están clasificadas las normas**, así
 * que es el único campo que decide qué le aplica. Los dos se piden: uno para la
 * ficha, el otro para la matriz.
 */
export function PerfilNormativoCard({ tenant }: { tenant: Tenant }) {
  const formId = useId();
  const { updatePerfilNormativo } = useTenants();
  const [sectores, setSectores] = useState<Sector[]>([]);
  const [sectorId, setSectorId] = useState<number | null>(tenant.sectorId ?? null);
  const [tramo, setTramo] = useState<Tramo | ''>(tenant.tramo ?? '');

  useEffect(() => {
    void cargarSectores().then(setSectores);
  }, []);

  // Si la empresa se recarga desde la API después del primer render, el
  // formulario tiene que reflejar lo guardado y no lo que había al montar.
  useEffect(() => {
    setSectorId(tenant.sectorId ?? null);
    setTramo(tenant.tramo ?? '');
  }, [tenant.sectorId, tenant.tramo]);

  const declarado = tenant.sectorId != null && tenant.tramo != null;
  const cambio = sectorId !== (tenant.sectorId ?? null) || tramo !== (tenant.tramo ?? '');

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <header className="flex items-start gap-3">
        <Compass className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" aria-hidden />
        <div>
          <h2 className="font-semibold text-slate-900">Perfil normativo</h2>
          <p className="text-sm text-slate-500">
            El sector y el tamaño determinan qué normativa se le propone a la empresa.
          </p>
        </div>
      </header>

      {!declarado && (
        // Se dice qué pasa mientras falte, no solo que falta. "Campo requerido"
        // no le explica a nadie por qué su matriz legal está vacía.
        <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Mientras no estén declarados, la matriz legal no puede proponer ninguna norma.
        </p>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <FormField label="Sector económico (CIIU)" htmlFor={`${formId}-sector`}>
          <select
            id={`${formId}-sector`}
            className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            value={sectorId ?? ''}
            onChange={(e) => setSectorId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">
              {sectores.length === 0 ? 'Cargando sectores…' : 'Selecciona un sector'}
            </option>
            {sectores.map((s) => (
              <option key={s.id} value={s.id}>
                {s.codigo} — {s.nombre}
              </option>
            ))}
          </select>
        </FormField>

        <FormField label="Tamaño de la empresa" htmlFor={`${formId}-tramo`}>
          <select
            id={`${formId}-tramo`}
            className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            value={tramo}
            onChange={(e) => setTramo(e.target.value as Tramo | '')}
          >
            <option value="">Selecciona un tramo</option>
            {TRAMOS.map((t) => (
              <option key={t.valor} value={t.valor}>
                {t.label} ({t.detalle})
              </option>
            ))}
          </select>
        </FormField>
      </div>

      <div className="mt-4 flex justify-end">
        <Button
          // Se exigen los dos. Guardar solo el sector dejaría el perfil a medias
          // y la recomendación sin afinar, sin que nada lo señale después.
          disabled={!sectorId || !tramo || !cambio}
          onClick={() => {
            if (!sectorId || !tramo) return;
            updatePerfilNormativo(tenant.id, { sectorId, tramo });
          }}
        >
          Guardar perfil normativo
        </Button>
      </div>
    </section>
  );
}
