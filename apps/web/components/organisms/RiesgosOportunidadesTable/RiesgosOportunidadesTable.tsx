'use client';

import { useMemo, useState } from 'react';
import { Inbox } from 'lucide-react';
import { FEATURE_FLAGS, type RiesgoOportunidad, type Plant } from '@ambienta/shared';
import { StatusBadge } from '@/components/atoms';
import { FilterBar } from '@/components/molecules';
import { getUserName } from '@/lib/get-user-name';

const NIVEL_LABEL: Record<string, string> = {
  bajo: 'Bajo',
  medio: 'Medio',
  alto: 'Alto',
  critico: 'Crítico',
};

const ESTADO_LABEL: Record<string, string> = {
  identificado: 'Identificado',
  en_tratamiento: 'En tratamiento',
  controlado: 'Controlado',
  cerrado: 'Cerrado',
};

const ORIGEN_LABEL: Record<string, string> = {
  aspecto_ambiental: 'Aspecto ambiental',
  requisito_legal: 'Requisito legal',
  contexto: 'Contexto',
  parte_interesada: 'Parte interesada',
  auditoria: 'Auditoría',
  cambio_climatico: 'Cambio climático',
  registro_mejora: 'Registro de mejora',
};

const TRATAMIENTO_LABEL: Record<string, string> = {
  evitar: 'Evitar',
  mitigar: 'Mitigar',
  transferir: 'Transferir',
  aceptar: 'Aceptar',
  aprovechar: 'Aprovechar',
  descartar: 'Descartar',
};

function nivelSemaforo(nivel?: string): 'cumple' | 'parcial' | 'no_cumple' {
  if (nivel === 'critico' || nivel === 'alto') return 'no_cumple';
  if (nivel === 'medio') return 'parcial';
  return 'cumple';
}

interface Props {
  riesgos: RiesgoOportunidad[];
  plants: Plant[];
}

export function RiesgosOportunidadesTable({ riesgos, plants }: Props) {
  if (!FEATURE_FLAGS.matricesIso) return null;

  const [plantaFiltro, setPlantaFiltro] = useState('todas');
  const [tipoFiltro, setTipoFiltro] = useState('todos');
  const [estadoFiltro, setEstadoFiltro] = useState('todos');

  const filtered = useMemo(
    () =>
      riesgos.filter((r) => {
        if (plantaFiltro !== 'todas' && r.plantId !== plantaFiltro) return false;
        if (tipoFiltro !== 'todos' && r.tipo !== tipoFiltro) return false;
        if (estadoFiltro !== 'todos' && r.estado !== estadoFiltro) return false;
        return true;
      }),
    [riesgos, plantaFiltro, tipoFiltro, estadoFiltro],
  );

  return (
    <div className="flex flex-col gap-4">
      <FilterBar
        filters={[
          {
            id: 'filtro-planta-ryo',
            label: 'Planta',
            value: plantaFiltro,
            onChange: setPlantaFiltro,
            options: [{ value: 'todas', label: 'Todas las plantas' }, ...plants.map((p) => ({ value: p.id ?? '', label: p.nombre ?? '' }))],
          },
          {
            id: 'filtro-tipo-ryo',
            label: 'Tipo',
            value: tipoFiltro,
            onChange: setTipoFiltro,
            options: [
              { value: 'todos', label: 'Todos' },
              { value: 'riesgo', label: 'Riesgo' },
              { value: 'oportunidad', label: 'Oportunidad' },
            ],
          },
          {
            id: 'filtro-estado-ryo',
            label: 'Estado',
            value: estadoFiltro,
            onChange: setEstadoFiltro,
            options: [
              { value: 'todos', label: 'Todos' },
              { value: 'identificado', label: 'Identificado' },
              { value: 'en_tratamiento', label: 'En tratamiento' },
              { value: 'controlado', label: 'Controlado' },
              { value: 'cerrado', label: 'Cerrado' },
            ],
          },
        ]}
      />

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 py-12 text-slate-400">
          <Inbox className="h-8 w-8" aria-hidden />
          <p className="text-sm">No hay riesgos u oportunidades que coincidan con los filtros.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Riesgos y oportunidades</caption>
            <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Código</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Descripción</th>
                <th className="px-4 py-3">Origen</th>
                <th className="px-4 py-3">Nivel</th>
                <th className="px-4 py-3">Tratamiento</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Responsable</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs font-medium text-slate-900">{r.codigo}</td>
                  <td className="px-4 py-3">
                    <span className={r.tipo === 'riesgo' ? 'text-red-700' : 'text-green-700'}>
                      {r.tipo === 'riesgo' ? 'Riesgo' : 'Oportunidad'}
                    </span>
                  </td>
                  <td className="max-w-xs px-4 py-3 text-slate-700">{r.descripcion}</td>
                  <td className="px-4 py-3 text-slate-600">{ORIGEN_LABEL[r.origen] ?? r.origen}</td>
                  <td className="px-4 py-3">
                    {r.evaluacion ? (
                      <StatusBadge status={nivelSemaforo(r.evaluacion.nivel)} />
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{r.tratamiento ? TRATAMIENTO_LABEL[r.tratamiento] : '—'}</td>
                  <td className="px-4 py-3 text-slate-600">{ESTADO_LABEL[r.estado] ?? r.estado}</td>
                  <td className="px-4 py-3 text-slate-600">{getUserName(r.responsableId)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
