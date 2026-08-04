'use client';

import { useMemo, useState } from 'react';
import { Inbox } from 'lucide-react';
import { FEATURE_FLAGS, sinOperadorHabilitado, type EquipoRegulado, type Plant } from '@ambienta/shared';
import { StatusBadge } from '@/components/atoms';
import { FilterBar } from '@/components/molecules';
import { getUserName } from '@/lib/get-user-name';

const TIPO_LABEL: Record<string, string> = {
  caldera: 'Caldera',
  generador: 'Generador',
  grupo_electrogeno: 'Grupo electrógeno',
  estanque: 'Estanque',
  compresor: 'Compresor',
  otro: 'Otro',
};

const ESTADO_LABEL: Record<string, string> = {
  operativo: 'Operativo',
  fuera_de_servicio: 'Fuera de servicio',
  baja: 'Dado de baja',
};

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

interface Props {
  equipos: EquipoRegulado[];
  plants: Plant[];
}

export function EquiposReguladosTable({ equipos, plants }: Props) {
  if (!FEATURE_FLAGS.matricesIso) return null;

  const hoy = new Date().toISOString().slice(0, 10);
  const [plantaFiltro, setPlantaFiltro] = useState('todas');
  const [tipoFiltro, setTipoFiltro] = useState('todos');

  const filtered = useMemo(
    () =>
      equipos.filter((e) => {
        if (plantaFiltro !== 'todas' && e.plantId !== plantaFiltro) return false;
        if (tipoFiltro !== 'todos' && e.tipo !== tipoFiltro) return false;
        return true;
      }),
    [equipos, plantaFiltro, tipoFiltro],
  );

  return (
    <div className="flex flex-col gap-4">
      <FilterBar
        filters={[
          {
            id: 'filtro-planta-eq',
            label: 'Planta',
            value: plantaFiltro,
            onChange: setPlantaFiltro,
            options: [{ value: 'todas', label: 'Todas las plantas' }, ...plants.map((p) => ({ value: p.id ?? '', label: p.nombre ?? '' }))],
          },
          {
            id: 'filtro-tipo-eq',
            label: 'Tipo',
            value: tipoFiltro,
            onChange: setTipoFiltro,
            options: [
              { value: 'todos', label: 'Todos' },
              { value: 'caldera', label: 'Caldera' },
              { value: 'generador', label: 'Generador' },
              { value: 'grupo_electrogeno', label: 'Grupo electrógeno' },
              { value: 'estanque', label: 'Estanque' },
              { value: 'compresor', label: 'Compresor' },
            ],
          },
        ]}
      />

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 py-12 text-slate-400">
          <Inbox className="h-8 w-8" aria-hidden />
          <p className="text-sm">No hay equipos regulados que coincidan con los filtros.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Equipos regulados</caption>
            <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Nombre</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Marca / Modelo</th>
                <th className="px-4 py-3">Inscripción</th>
                <th className="px-4 py-3">Operadores</th>
                <th className="px-4 py-3">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((e) => {
                const sinOperador = sinOperadorHabilitado(e, hoy);
                return (
                  <tr key={e.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium text-slate-900">{e.nombre}</td>
                    <td className="px-4 py-3 text-slate-600">{TIPO_LABEL[e.tipo] ?? e.tipo}</td>
                    <td className="px-4 py-3 text-slate-600">
                      {[e.marca, e.modelo].filter(Boolean).join(' ') || '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {e.inscripcion ? (
                        <span>
                          {e.inscripcion.organismo} — {e.inscripcion.numero}
                          {e.inscripcion.vencimiento && (
                            <span className={e.inscripcion.vencimiento < hoy ? ' text-red-600' : ''}>
                              {' '}(vence {formatFecha(e.inscripcion.vencimiento)})
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="text-amber-600">Sin inscripción</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {e.operadores.length === 0 ? (
                        <span className="text-amber-600">Sin operador</span>
                      ) : (
                        <div className="flex flex-col gap-1">
                          {e.operadores.map((op) => (
                            <span key={op.usuarioId} className="text-xs text-slate-600">
                              {getUserName(op.usuarioId)} — {op.certificacion}
                              {op.vence && (
                                <span className={op.vence < hoy ? ' text-red-600 font-medium' : ' text-slate-400'}>
                                  {' '}(vence {formatFecha(op.vence)})
                                </span>
                              )}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {sinOperador ? (
                        <StatusBadge status="no_cumple" />
                      ) : (
                        <span className="text-slate-600">{ESTADO_LABEL[e.estado]}</span>
                      )}
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
