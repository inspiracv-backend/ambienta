'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { CheckCircle2, Plus } from 'lucide-react';
import { Button, StatusBadge } from '@/components/atoms';
import { useAudits } from '@/lib/audits-store';
import { usePlanAccion } from '@/lib/plan-accion-store';
import { getUserName } from '@/lib/get-user-name';
import { ncSemaforo, CRITICIDAD_LABEL } from '@/lib/audit-status';
import type { NonConformityDetailViewProps } from './NonConformityDetailView.types';

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

const PREGUNTAS = ['1er ¿Por qué?', '2do ¿Por qué?', '3er ¿Por qué?', '4to ¿Por qué?', '5to ¿Por qué?'];

/** S-23 Detalle de No Conformidad + 5 ¿Por qué?, planes de acción asociados y cierre con firma. */
export function NonConformityDetailView({ nonConformity: ncProp, plant, responsableOptions }: NonConformityDetailViewProps) {
  const router = useRouter();
  const { nonConformities, updatePorques, closeNonConformity } = useAudits();
  const { plans, createPlan, findByOrigen } = usePlanAccion();
  const nc = nonConformities.find((n) => n.id === ncProp.id) ?? ncProp;

  const [porques, setPorques] = useState<string[]>(nc.cincoPorques);
  const [cierreResponsableId, setCierreResponsableId] = useState(nc.responsableId);
  const [firmada, setFirmada] = useState(false);

  useEffect(() => setPorques(nc.cincoPorques), [nc.cincoPorques]);

  const existingPlan = findByOrigen(nc.id);
  const puedeCerrar = nc.estado !== 'cerrada';

  function handlePorqueChange(index: number, value: string) {
    const next = [...porques];
    next[index] = value;
    setPorques(next);
  }

  function handleGuardarPorques() {
    updatePorques(nc.id, porques.filter((p) => p.trim().length > 0));
  }

  function handleGenerarPlan() {
    const plan = createPlan({
      tenantId: nc.tenantId,
      origenTipo: 'no_conformidad',
      origenId: nc.id,
      origenLabel: nc.hallazgo,
      titulo: `Plan de acción — ${nc.hallazgo}`,
      responsableId: nc.responsableId,
      fechaLimite: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    });
    router.push(`/planes-accion/${plan.id}`);
  }

  function handleCerrar() {
    if (!firmada) return;
    closeNonConformity(nc.id, cierreResponsableId);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
              {plant?.nombre ?? nc.plantId} · Criticidad {CRITICIDAD_LABEL[nc.criticidad]}
            </span>
            <h1 className="mt-1 text-xl font-semibold text-slate-900">{nc.hallazgo}</h1>
            <p className="mt-1 text-sm text-slate-500">
              Detectado {formatFecha(nc.fechaDeteccion)} · Responsable {getUserName(nc.responsableId)}
            </p>
          </div>
          <StatusBadge status={ncSemaforo(nc.estado)} />
        </div>
      </div>

      <div className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-1 text-sm font-semibold text-slate-700">Análisis de causa raíz — 5 ¿Por qué?</h2>
        <p className="mb-4 text-xs text-slate-500">Complétalo de forma iterativa; no es necesario llenar las 5 preguntas de una vez.</p>
        <div className="flex flex-col gap-3">
          {PREGUNTAS.map((label, i) => (
            <label key={label} className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-slate-600">{label}</span>
              <textarea
                rows={2}
                disabled={nc.estado === 'cerrada'}
                className="w-full rounded-lg border border-slate-300 p-2 text-sm disabled:bg-slate-50 disabled:text-slate-400"
                value={porques[i] ?? ''}
                onChange={(e) => handlePorqueChange(i, e.target.value)}
              />
            </label>
          ))}
        </div>
        {nc.estado !== 'cerrada' && (
          <Button variant="secondary" className="mt-3" onClick={handleGuardarPorques}>
            Guardar analisis
          </Button>
        )}
      </div>

      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-700">Plan de Acción asociado</h2>
          {!existingPlan && (
            <Button size="md" icon={<Plus className="h-4 w-4" aria-hidden />} onClick={handleGenerarPlan}>
              Generar Plan de Acción
            </Button>
          )}
        </div>
        {existingPlan ? (
          <Link href={`/planes-accion/${existingPlan.id}`} className="mt-2 inline-block text-sm text-brand-600 hover:underline">
            {existingPlan.titulo}
          </Link>
        ) : (
          <p className="mt-2 text-sm text-slate-400">Aún no se ha generado un plan de acción para este hallazgo.</p>
        )}
      </div>

      <div className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Cierre</h2>
        {nc.cierre ? (
          <div className="flex items-center gap-2 text-sm text-semaforo-cumple">
            <CheckCircle2 className="h-4 w-4" aria-hidden />
            Cerrada el {formatFecha(nc.cierre.fecha)} por {getUserName(nc.cierre.responsableId)} (firmada)
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-slate-600">Responsable del cierre</span>
              <select
                className="h-11 w-full max-w-xs rounded-lg border border-slate-300 px-3 text-sm"
                value={cierreResponsableId}
                onChange={(e) => setCierreResponsableId(e.target.value)}
              >
                {responsableOptions.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.nombre}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={firmada} onChange={(e) => setFirmada(e.target.checked)} />
              Firmo y confirmo el cierre de esta no conformidad (RF-37)
            </label>
            <Button onClick={handleCerrar} disabled={!firmada || !puedeCerrar} className="w-fit">
              Cerrar No Conformidad
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
