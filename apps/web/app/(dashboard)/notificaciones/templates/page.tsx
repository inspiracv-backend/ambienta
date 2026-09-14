'use client';

import { useEffect, useState } from 'react';
import { FileSpreadsheet } from 'lucide-react';
import { Spinner } from '@/components/atoms';
import { Breadcrumbs, EmptyState } from '@/components/molecules';
import { api, mensajeDeError } from '@/lib/api-client';
import { fechaCalendario } from '@/lib/fechas';

interface PlantillaDeDeclaracion {
  id: string;
  system_code: string;
  name: string;
  version: string;
  valid_from: string | null;
  valid_to: string | null;
  active: boolean;
}

/**
 * S-33 Super-repositorio de plantillas Excel (#116, RF-33, RF-34).
 *
 * **Hasta el 14-sep mostraba cuatro plantillas inventadas** —RETC, Ley REP,
 * SINADER, SIDREP— con versión, pestañas y un enlace `#`, mientras
 * `declaration_templates` tenía cero filas. Es exactamente lo que CLAUDE.md
 * advierte: una estructura de pestañas inventada hace que la empresa prepare su
 * declaración en un formato que el portal rechaza, y se entera cuando ya no
 * hay plazo.
 *
 * Ahora muestra lo que hay en la base. Vacía es el estado real y deliberado: las
 * plantillas son contenido oficial que se descarga de cada portal del Estado.
 */
export default function TemplatesPage() {
  const [plantillas, setPlantillas] = useState<PlantillaDeDeclaracion[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<PlantillaDeDeclaracion[]>('/templates/declarations')
      .then(setPlantillas)
      .catch((e) => setError(mensajeDeError(e)));
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Notificaciones', href: '/notificaciones' }, { label: 'Plantillas Excel' }]} />
      <h1 className="text-2xl font-semibold text-slate-900">Plantillas Excel de declaración</h1>

      {error ? (
        <p role="alert" className="rounded-card border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          No se pudieron cargar las plantillas: {error}. Lo que se ve está vacío porque no se pudo preguntar.
        </p>
      ) : plantillas === null ? (
        <Spinner label="Cargando plantillas" />
      ) : plantillas.length === 0 ? (
        <EmptyState
          icono={FileSpreadsheet}
          titulo="Todavía no hay plantillas cargadas"
          descripcion="Las plantillas son las oficiales de cada portal (RETC, SINADER, SIDREP…) y se cargan desde ahí. No se muestran formatos de ejemplo: prepararse con uno inventado lleva a una declaración que el portal rechaza."
        />
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                <th scope="col" className="px-4 py-3">Sistema</th>
                <th scope="col" className="px-4 py-3">Plantilla</th>
                <th scope="col" className="px-4 py-3">Versión</th>
                <th scope="col" className="px-4 py-3">Vigencia</th>
              </tr>
            </thead>
            <tbody>
              {plantillas.map((p) => (
                <tr key={p.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-3 font-medium text-slate-800">{p.system_code}</td>
                  <td className="px-4 py-3 text-slate-700">
                    {p.name}
                    {!p.active && <span className="ml-2 text-xs text-slate-500">(inactiva)</span>}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{p.version}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {p.valid_from ? fechaCalendario(p.valid_from) : 'Sin inicio'} — {p.valid_to ? fechaCalendario(p.valid_to) : 'vigente'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
