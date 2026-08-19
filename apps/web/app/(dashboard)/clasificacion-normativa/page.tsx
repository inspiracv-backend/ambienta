'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, BookMarked } from 'lucide-react';
import { PageHeader, StatCard } from '@/components/molecules';
import { Spinner } from '@/components/atoms';
import {
  cargarCobertura,
  ETIQUETA_DE_URGENCIA,
  porcentajeClasificado,
  urgenciaDe,
  COBERTURA_VACIA,
  type Cobertura,
  type Urgencia,
} from '@/lib/clasificacion-normativa';

/**
 * Clasificación normativa (exclusivo Superadmin, ver `lib/navigation.ts`).
 *
 * ## Qué muestra y por qué importa
 *
 * Todo el mecanismo de normativa aplicable descansa en `norm_sectors`: una
 * norma sin clasificar no le llega a ninguna empresa. La tabla nace vacía, así
 * que hoy el sistema **funciona entero y no propone nada**. Desde adentro no se
 * nota: la matriz responde "sector sin clasificar", que parece una falla
 * técnica y es trabajo pendiente de una persona.
 *
 * Esta pantalla no arregla el vacío. Lo vuelve un número que no se puede
 * ignorar, y señala en qué sectores duele.
 *
 * ## Por qué es del ámbito plataforma
 *
 * `norm_sectors` no lleva `tenant_id`. Una clasificación errada se propaga a
 * **todas** las empresas de ese sector, no solo a la de quien la escribió. Si
 * esto viviera en el menú de empresa, un Admin Empresa estaría cambiando la
 * normativa de sus competidores.
 */

const TONO_DE_URGENCIA: Record<Urgencia, string> = {
  'sin-normativa': 'bg-rose-50 text-rose-700 ring-rose-200',
  'solo-recomendadas': 'bg-amber-50 text-amber-700 ring-amber-200',
  'con-obligatorias': 'bg-emerald-50 text-emerald-700 ring-emerald-200',
};

export default function ClasificacionNormativaPage() {
  const [cobertura, setCobertura] = useState<Cobertura>(COBERTURA_VACIA);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let vigente = true;
    cargarCobertura()
      // Si falla, se queda en ceros y lo dice el vacío de la tabla. Mostrar un
      // número inventado aquí sería peor que no mostrar ninguno: esta pantalla
      // existe justamente para que nadie crea que el trabajo está hecho.
      .catch(() => COBERTURA_VACIA)
      .then((c) => {
        if (!vigente) return;
        setCobertura(c);
        setCargando(false);
      });
    return () => {
      vigente = false;
    };
  }, []);

  const pct = porcentajeClasificado(cobertura);
  const pendientes = cobertura.normasSinClasificar;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        titulo="Clasificación normativa"
        descripcion="Qué normas aplican a qué sectores. Sin esto, ninguna empresa recibe normativa."
      />

      {cargando ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard
              etiqueta="Normas sin clasificar"
              valor={pendientes}
              detalle={`de ${cobertura.normasTotales} en el catálogo`}
              icono={BookMarked}
              tono={pendientes > 0 ? 'critico' : 'positivo'}
            />
            <StatCard
              etiqueta="Sectores sin normativa"
              valor={cobertura.sectoresSinNormativa}
              detalle={`de ${cobertura.porSector.length} sectores CIIU`}
              icono={AlertTriangle}
              tono={cobertura.sectoresSinNormativa > 0 ? 'atencion' : 'positivo'}
            />
            <StatCard
              etiqueta="Catálogo clasificado"
              // `null` cuando no hay normas: sin catálogo cargado no es que
              // nadie haya clasificado, es que no hay nada que clasificar.
              valor={pct === null ? '—' : `${pct} %`}
              detalle={pct === null ? 'Sin normas en el catálogo' : 'Al menos un sector asignado'}
              tono={pct === null || pct < 100 ? 'neutro' : 'positivo'}
            />
          </div>

          {pendientes > 0 && (
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              <strong>{pendientes}</strong>{' '}
              {pendientes === 1 ? 'norma no está clasificada' : 'normas no están clasificadas'} en
              ningún sector. Mientras siga así, las empresas de esos rubros completan su perfil y su
              matriz legal queda vacía.
            </p>
          )}

          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <caption className="sr-only">
                Normas clasificadas por sector económico, separando obligatorias de recomendadas
              </caption>
              <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Sector CIIU
                  </th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">
                    Obligatorias
                  </th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">
                    Recomendadas
                  </th>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Estado
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {cobertura.porSector.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                      No se pudo leer el catálogo de sectores.
                    </td>
                  </tr>
                ) : (
                  cobertura.porSector.map((s) => {
                    const urgencia = urgenciaDe(s);
                    return (
                      <tr key={s.sectorId} className="hover:bg-slate-50">
                        <th scope="row" className="px-4 py-3 text-left font-normal text-slate-900">
                          <span className="font-mono text-xs text-slate-400">{s.codigo}</span>{' '}
                          {s.nombre}
                        </th>
                        <td className="px-4 py-3 text-right tabular-nums text-slate-900">
                          {s.directas}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-slate-500">
                          {s.recomendadas}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONO_DE_URGENCIA[urgencia]}`}
                          >
                            {ETIQUETA_DE_URGENCIA[urgencia]}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
