'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Inbox } from 'lucide-react';
import { StatusBadge } from '@/components/atoms';
import { FilterBar } from '@/components/molecules';
import {
  computeNormCompliance,
  computeNormCoverage,
  countArticulosEnIncumplimiento,
  countArticulosSinEvaluar,
  normSemaforo,
} from '@/lib/legal-matrix';
import { getUserName } from '@/lib/get-user-name';
import type { LegalMatrixTableProps } from './LegalMatrixTable.types';

const FUENTE_LABEL = { BCN: 'Pública (BCN)', ISO: 'ISO interna', RCA: 'RCA del tenant' } as const;

/** S-08 Listado de Matriz Legal: filtros por planta/estado/tipo (H6), semáforo por norma (H1+H2). */
export function LegalMatrixTable({ norms, plants }: LegalMatrixTableProps) {
  const [plantaFiltro, setPlantaFiltro] = useState('todas');
  const [estadoFiltro, setEstadoFiltro] = useState('todos');
  const [tipoFiltro, setTipoFiltro] = useState('todos');

  const filtered = useMemo(() => {
    return norms.filter((norm) => {
      if (plantaFiltro !== 'todas' && !norm.plantIds.includes(plantaFiltro)) return false;
      if (tipoFiltro !== 'todos' && norm.fuente !== tipoFiltro) return false;
      if (estadoFiltro !== 'todos') {
        const semaforo = normSemaforo(computeNormCompliance(norm));
        if (semaforo !== estadoFiltro) return false;
      }
      return true;
    });
  }, [norms, plantaFiltro, estadoFiltro, tipoFiltro]);

  return (
    <div className="flex flex-col gap-4">
      <FilterBar
        filters={[
          {
            id: 'filtro-planta',
            label: 'Planta',
            value: plantaFiltro,
            onChange: setPlantaFiltro,
            options: [{ value: 'todas', label: 'Todas las plantas' }, ...plants.map((p) => ({ value: p.id, label: p.nombre }))],
          },
          {
            id: 'filtro-estado',
            label: 'Estado de cumplimiento',
            value: estadoFiltro,
            onChange: setEstadoFiltro,
            options: [
              { value: 'todos', label: 'Todos los estados' },
              { value: 'cumple', label: 'Cumple' },
              { value: 'parcial', label: 'Parcial' },
              { value: 'no_cumple', label: 'No cumple' },
            ],
          },
          {
            id: 'filtro-tipo',
            label: 'Tipo de norma',
            value: tipoFiltro,
            onChange: setTipoFiltro,
            options: [
              { value: 'todos', label: 'Todos los tipos' },
              { value: 'BCN', label: 'Pública (BCN)' },
              { value: 'ISO', label: 'ISO interna' },
              { value: 'RCA', label: 'RCA del tenant' },
            ],
          },
        ]}
      />

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
          <Inbox className="h-6 w-6 text-slate-400" aria-hidden />
          No hay normas que coincidan con estos filtros. Prueba con otra combinación o agrega una norma nueva.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
          <table className="w-full min-w-[720px] text-sm">
            <caption className="sr-only">Matriz Legal — normas aplicables y su estado de cumplimiento</caption>
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                <th scope="col" className="px-4 py-3">Norma</th>
                <th scope="col" className="px-4 py-3">Tipo</th>
                <th scope="col" className="px-4 py-3">Cumplimiento</th>
                <th scope="col" className="px-4 py-3">Cobertura</th>
                <th scope="col" className="px-4 py-3">En incumplimiento</th>
                <th scope="col" className="px-4 py-3">Responsable</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((norm) => {
                const pct = computeNormCompliance(norm);
                return (
                  <tr key={norm.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium text-slate-800">
                      <Link href={`/matriz-legal/${norm.id}`} className="hover:underline">
                        {norm.nombre}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{FUENTE_LABEL[norm.fuente]}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={normSemaforo(pct)} />
                      <span className="ml-2 text-slate-500">{Math.round(pct * 100)}%</span>
                    </td>
                    {/* Cobertura y cumplimiento responden preguntas distintas: un
                        100% de cumplimiento sobre el 20% evaluado no es cumplimiento,
                        es una muestra. Mostrarlos juntos evita esa lectura. */}
                    <td className="px-4 py-3">
                      <span className={countArticulosSinEvaluar(norm) > 0 ? 'text-amber-700' : 'text-slate-600'}>
                        {Math.round(computeNormCoverage(norm) * 100)}%
                      </span>
                      {countArticulosSinEvaluar(norm) > 0 && (
                        <span className="ml-1 text-xs text-slate-500">
                          ({countArticulosSinEvaluar(norm)} sin evaluar)
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">{countArticulosEnIncumplimiento(norm)}</td>
                    <td className="px-4 py-3 text-slate-500">{getUserName(norm.responsableId)}</td>
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
