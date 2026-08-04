'use client';

import { useMemo, useState } from 'react';
import { Inbox } from 'lucide-react';
import { FEATURE_FLAGS, aspectoSinTratar, type AspectoAmbiental, type Plant } from '@ambienta/shared';
import { StatusBadge } from '@/components/atoms';
import { FilterBar } from '@/components/molecules';
import { getUserName } from '@/lib/get-user-name';

const CONDICION_LABEL: Record<string, string> = {
  normal: 'Normal',
  anormal: 'Anormal',
  emergencia: 'Emergencia',
};

const TIPO_LABEL: Record<string, string> = {
  emision_atmosferica: 'Emisión atmosférica',
  vertido_agua: 'Vertido al agua',
  residuo_solido: 'Residuo sólido',
  residuo_peligroso: 'Residuo peligroso',
  consumo_agua: 'Consumo de agua',
  consumo_energia: 'Consumo de energía',
  ruido: 'Ruido',
  contaminacion_suelo: 'Contaminación de suelo',
  biodiversidad: 'Biodiversidad',
  gases_efecto_invernadero: 'GEI',
  otro: 'Otro',
};

interface Props {
  aspectos: AspectoAmbiental[];
  plants: Plant[];
}

export function AspectosAmbientalesTable({ aspectos, plants }: Props) {
  if (!FEATURE_FLAGS.matricesIso) return null;

  const [plantaFiltro, setPlantaFiltro] = useState('todas');
  const [condicionFiltro, setCondicionFiltro] = useState('todas');
  const [significativoFiltro, setSignificativoFiltro] = useState('todos');

  const filtered = useMemo(
    () =>
      aspectos.filter((a) => {
        if (plantaFiltro !== 'todas' && a.plantId !== plantaFiltro) return false;
        if (condicionFiltro !== 'todas' && a.condicionOperacion !== condicionFiltro) return false;
        if (significativoFiltro === 'si' && !a.significativo) return false;
        if (significativoFiltro === 'no' && a.significativo) return false;
        if (significativoFiltro === 'sin_tratar' && !aspectoSinTratar(a)) return false;
        return true;
      }),
    [aspectos, plantaFiltro, condicionFiltro, significativoFiltro],
  );

  return (
    <div className="flex flex-col gap-4">
      <FilterBar
        filters={[
          {
            id: 'filtro-planta-asp',
            label: 'Planta',
            value: plantaFiltro,
            onChange: setPlantaFiltro,
            options: [{ value: 'todas', label: 'Todas las plantas' }, ...plants.map((p) => ({ value: p.id ?? '', label: p.nombre ?? '' }))],
          },
          {
            id: 'filtro-condicion',
            label: 'Condición',
            value: condicionFiltro,
            onChange: setCondicionFiltro,
            options: [
              { value: 'todas', label: 'Todas' },
              { value: 'normal', label: 'Normal' },
              { value: 'anormal', label: 'Anormal' },
              { value: 'emergencia', label: 'Emergencia' },
            ],
          },
          {
            id: 'filtro-significativo',
            label: 'Significancia',
            value: significativoFiltro,
            onChange: setSignificativoFiltro,
            options: [
              { value: 'todos', label: 'Todos' },
              { value: 'si', label: 'Significativo' },
              { value: 'no', label: 'No significativo' },
              { value: 'sin_tratar', label: 'Sin tratar' },
            ],
          },
        ]}
      />

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 py-12 text-slate-400">
          <Inbox className="h-8 w-8" aria-hidden />
          <p className="text-sm">No hay aspectos ambientales que coincidan con los filtros.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Aspectos ambientales identificados</caption>
            <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Actividad</th>
                <th className="px-4 py-3">Aspecto</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Condición</th>
                <th className="px-4 py-3">Puntaje</th>
                <th className="px-4 py-3">Significativo</th>
                <th className="px-4 py-3">Responsable</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((a) => (
                <tr key={a.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{a.actividad}</td>
                  <td className="px-4 py-3 text-slate-700">{a.aspecto}</td>
                  <td className="px-4 py-3 text-slate-600">{TIPO_LABEL[a.tipoAspecto] ?? a.tipoAspecto}</td>
                  <td className="px-4 py-3">
                    <span
                      className={
                        a.condicionOperacion === 'emergencia'
                          ? 'text-red-700'
                          : a.condicionOperacion === 'anormal'
                            ? 'text-amber-700'
                            : 'text-slate-600'
                      }
                    >
                      {CONDICION_LABEL[a.condicionOperacion]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{a.evaluacion?.puntaje ?? '—'}</td>
                  <td className="px-4 py-3">
                    <StatusBadge
                      status={
                        aspectoSinTratar(a)
                          ? 'no_cumple'
                          : a.significativo
                            ? 'parcial'
                            : 'cumple'
                      }
                    />
                  </td>
                  <td className="px-4 py-3 text-slate-600">{a.responsableId ? getUserName(a.responsableId) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
