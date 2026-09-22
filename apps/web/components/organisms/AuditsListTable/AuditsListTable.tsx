'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Inbox } from 'lucide-react';
import { FilterBar } from '@/components/molecules';
import { AUDIT_ESTADO_LABEL } from '@/lib/audit-status';
import { fechaDeInstante } from '@/lib/fechas';
import type { AuditsListTableProps } from './AuditsListTable.types';

/** Sin fecha planificada se dice, no se inventa la de hoy. */
function formatFecha(iso: string) {
  return iso ? fechaDeInstante(iso) : 'Sin fecha';
}

/** S-20 Listado de Auditorías (planificación de revisiones internas/externas). */
export function AuditsListTable({ audits, plants }: AuditsListTableProps) {
  const [plantaFiltro, setPlantaFiltro] = useState('todas');
  const [estadoFiltro, setEstadoFiltro] = useState('todos');

  const filtered = useMemo(
    () =>
      audits.filter((a) => {
        if (plantaFiltro !== 'todas' && a.plantId !== plantaFiltro) return false;
        if (estadoFiltro !== 'todos' && a.estado !== estadoFiltro) return false;
        return true;
      }),
    [audits, plantaFiltro, estadoFiltro],
  );

  return (
    <div className="flex flex-col gap-4">
      <FilterBar
        filters={[
          {
            id: 'filtro-planta-audit',
            label: 'Planta',
            value: plantaFiltro,
            onChange: setPlantaFiltro,
            options: [{ value: 'todas', label: 'Todas las plantas' }, ...plants.map((p) => ({ value: p.id, label: p.nombre }))],
          },
          {
            id: 'filtro-estado-audit',
            label: 'Estado',
            value: estadoFiltro,
            onChange: setEstadoFiltro,
            options: [
              { value: 'todos', label: 'Todos los estados' },
              { value: 'planificada', label: 'Planificada' },
              { value: 'en_curso', label: 'En curso' },
              { value: 'cerrada', label: 'Cerrada' },
              { value: 'cancelada', label: 'Cancelada' },
            ],
          },
        ]}
      />

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
          <Inbox className="h-6 w-6 text-slate-400" aria-hidden />
          No hay auditorías que coincidan con estos filtros.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
          <table className="w-full min-w-[640px] text-sm">
            <caption className="sr-only">Auditorías planificadas</caption>
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                <th scope="col" className="px-4 py-3">Auditoría</th>
                <th scope="col" className="px-4 py-3">Planta</th>
                <th scope="col" className="px-4 py-3">Tipo</th>
                <th scope="col" className="px-4 py-3">Fecha</th>
                <th scope="col" className="px-4 py-3">Estado</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((audit) => {
                const plant = plants.find((p) => p.id === audit.plantId);
                return (
                  <tr key={audit.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium text-slate-800">
                      {/* El enlace llevaba el nombre de la planta: una auditoría de
                          toda la empresa quedaba con un enlace sin texto. */}
                      <Link href={`/auditorias/${audit.id}`} className="hover:underline">
                        {audit.titulo || audit.codigo || 'Auditoría sin título'}
                      </Link>
                      {audit.codigo && audit.titulo && (
                        <span className="block text-xs font-normal text-slate-500">{audit.codigo}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{audit.plantId ? (plant?.nombre ?? audit.plantId) : 'Toda la empresa'}</td>
                    <td className="px-4 py-3 text-slate-500 capitalize">{audit.tipo}</td>
                    <td className="px-4 py-3 text-slate-500">{formatFecha(audit.fecha)}</td>
                    <td className="px-4 py-3">
                      {/* Sin semaforo: el estado del ciclo no dice si se cumplio. Una
                          auditoria cerrada —o cancelada— salia "Cumple" aunque
                          hubiera encontrado no conformidades. */}
                      <span className="text-slate-600">{AUDIT_ESTADO_LABEL[audit.estado]}</span>
                    </td>
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
