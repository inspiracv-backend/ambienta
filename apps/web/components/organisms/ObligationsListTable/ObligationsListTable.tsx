'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Inbox, Plus } from 'lucide-react';
import { Button, StatusBadge } from '@/components/atoms';
import { FilterBar } from '@/components/molecules';
import { CreateObligationModal } from '@/components/organisms/CreateObligationModal';
import { getUserName } from '@/lib/get-user-name';
import type { ObligationsListTableProps } from './ObligationsListTable.types';

const SISTEMAS = ['RETC', 'Ley REP', 'SINADER', 'SIDREP', 'DAE'] as const;

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

/** S-13 Listado de Obligaciones/Declaraciones (megaproyectos). */
export function ObligationsListTable({ obligations, plants }: ObligationsListTableProps) {
  const [plantaFiltro, setPlantaFiltro] = useState('todas');
  const [sistemaFiltro, setSistemaFiltro] = useState('todos');
  const [estadoFiltro, setEstadoFiltro] = useState('todos');
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  const filtered = useMemo(() => {
    return obligations.filter((o) => {
      if (plantaFiltro !== 'todas' && o.plantId !== plantaFiltro) return false;
      if (sistemaFiltro !== 'todos' && o.sistema !== sistemaFiltro) return false;
      if (estadoFiltro !== 'todos' && o.estado !== estadoFiltro) return false;
      return true;
    });
  }, [obligations, plantaFiltro, sistemaFiltro, estadoFiltro]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <FilterBar
          filters={[
            {
              id: 'filtro-planta-obl',
              label: 'Planta',
              value: plantaFiltro,
              onChange: setPlantaFiltro,
              options: [{ value: 'todas', label: 'Todas las plantas' }, ...plants.map((p) => ({ value: p.id, label: p.nombre }))],
            },
            {
              id: 'filtro-sistema',
              label: 'Sistema de declaración',
              value: sistemaFiltro,
              onChange: setSistemaFiltro,
              options: [{ value: 'todos', label: 'Todos los sistemas' }, ...SISTEMAS.map((s) => ({ value: s, label: s }))],
            },
            {
              id: 'filtro-estado-obl',
              label: 'Estado',
              value: estadoFiltro,
              onChange: setEstadoFiltro,
              options: [
                { value: 'todos', label: 'Todos los estados' },
                { value: 'vigente', label: 'Vigente' },
                { value: 'por_vencer', label: 'Por vencer' },
                { value: 'vencida', label: 'Vencida' },
                { value: 'sin_evidencia', label: 'Sin evidencia' },
              ],
            },
          ]}
        />
        <Button icon={<Plus className="h-4 w-4" aria-hidden />} onClick={() => setIsCreateOpen(true)}>
          Crear obligación
        </Button>
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
          <Inbox className="h-6 w-6 text-slate-400" aria-hidden />
          No hay obligaciones que coincidan con estos filtros. Prueba con otra combinación o crea una nueva.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
          <table className="w-full min-w-[760px] text-sm">
            <caption className="sr-only">Obligaciones y declaraciones periódicas</caption>
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                <th scope="col" className="px-4 py-3">Obligación</th>
                <th scope="col" className="px-4 py-3">Período</th>
                <th scope="col" className="px-4 py-3">Estado</th>
                <th scope="col" className="px-4 py-3">Tareas</th>
                <th scope="col" className="px-4 py-3">Próximo vencimiento</th>
                <th scope="col" className="px-4 py-3">Responsable</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((ob) => (
                <tr key={ob.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-800">
                    <Link href={`/obligaciones/${ob.id}`} className="hover:underline">
                      {ob.nombre}
                    </Link>
                    <p className="text-xs font-normal text-slate-500">{ob.sistema}</p>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{ob.periodo}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={ob.estado} />
                  </td>
                  <td className="px-4 py-3 text-slate-500">{ob.tasks.length}</td>
                  <td className="px-4 py-3 text-slate-500">{formatFecha(ob.proximoVencimiento)}</td>
                  <td className="px-4 py-3 text-slate-500">{getUserName(ob.responsableId)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CreateObligationModal open={isCreateOpen} onOpenChange={setIsCreateOpen} plants={plants} />
    </div>
  );
}
