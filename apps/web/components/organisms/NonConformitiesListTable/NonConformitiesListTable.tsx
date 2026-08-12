'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Inbox, Plus } from 'lucide-react';
import { Button, StatusBadge } from '@/components/atoms';
import { FilterBar } from '@/components/molecules';
import { getUserName } from '@/lib/get-user-name';
import { ncSemaforo, NC_ESTADO_LABEL, CRITICIDAD_LABEL } from '@/lib/audit-status';
import type { NonConformitiesListTableProps } from './NonConformitiesListTable.types';

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

/** S-22 Listado de No Conformidades (hallazgos). */
export function NonConformitiesListTable({ nonConformities, plants }: NonConformitiesListTableProps) {
  const [plantaFiltro, setPlantaFiltro] = useState('todas');
  const [estadoFiltro, setEstadoFiltro] = useState('todos');
  const [criticidadFiltro, setCriticidadFiltro] = useState('todas');

  const filtered = useMemo(
    () =>
      nonConformities.filter((nc) => {
        if (plantaFiltro !== 'todas' && nc.plantId !== plantaFiltro) return false;
        if (estadoFiltro !== 'todos' && nc.estado !== estadoFiltro) return false;
        if (criticidadFiltro !== 'todas' && nc.criticidad !== criticidadFiltro) return false;
        return true;
      }),
    [nonConformities, plantaFiltro, estadoFiltro, criticidadFiltro],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <FilterBar
          filters={[
            {
              id: 'filtro-planta-nc',
              label: 'Planta',
              value: plantaFiltro,
              onChange: setPlantaFiltro,
              options: [{ value: 'todas', label: 'Todas las plantas' }, ...plants.map((p) => ({ value: p.id, label: p.nombre }))],
            },
            {
              id: 'filtro-estado-nc',
              label: 'Estado',
              value: estadoFiltro,
              onChange: setEstadoFiltro,
              options: [
                { value: 'todos', label: 'Todos los estados' },
                { value: 'abierta', label: 'Abierta' },
                { value: 'en_tratamiento', label: 'En tratamiento' },
                { value: 'cerrada', label: 'Cerrada' },
              ],
            },
            {
              id: 'filtro-criticidad',
              label: 'Criticidad',
              value: criticidadFiltro,
              onChange: setCriticidadFiltro,
              options: [
                { value: 'todas', label: 'Todas' },
                { value: 'alta', label: 'Alta' },
                { value: 'media', label: 'Media' },
                { value: 'baja', label: 'Baja' },
              ],
            },
          ]}
        />
        <Link href="/no-conformidades/nueva">
          <Button icon={<Plus className="h-4 w-4" aria-hidden />}>Registrar hallazgo</Button>
        </Link>
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
          <Inbox className="h-6 w-6 text-slate-400" aria-hidden />
          No hay no conformidades que coincidan con estos filtros.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
          <table className="w-full min-w-[760px] text-sm">
            <caption className="sr-only">No Conformidades registradas</caption>
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                <th scope="col" className="px-4 py-3">Hallazgo</th>
                <th scope="col" className="px-4 py-3">Planta</th>
                <th scope="col" className="px-4 py-3">Criticidad</th>
                <th scope="col" className="px-4 py-3">Estado</th>
                <th scope="col" className="px-4 py-3">Detectado</th>
                <th scope="col" className="px-4 py-3">Responsable</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((nc) => {
                const plant = plants.find((p) => p.id === nc.plantId);
                return (
                  <tr key={nc.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium text-slate-800">
                      <Link href={`/no-conformidades/${nc.id}`} className="hover:underline">
                        {nc.hallazgo}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{plant?.nombre ?? nc.plantId}</td>
                    <td className="px-4 py-3 text-slate-500">{CRITICIDAD_LABEL[nc.criticidad]}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={ncSemaforo(nc.estado)} />
                      <span className="ml-2 text-slate-500">{NC_ESTADO_LABEL[nc.estado]}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatFecha(nc.fechaDeteccion)}</td>
                    <td className="px-4 py-3 text-slate-500">{getUserName(nc.responsableId)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
