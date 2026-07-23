'use client';

import { useState } from 'react';
import { ExternalLink, Settings } from 'lucide-react';
import type { Articulo } from '@ambienta/shared';
import { Button, StatusBadge } from '@/components/atoms';
import { ArticleEvaluationModal } from '@/components/organisms/ArticleEvaluationModal';
import { ComplianceConfigModal } from '@/components/organisms/ComplianceConfigModal';
import { computeNormCompliance, articuloSemaforo, normSemaforo } from '@/lib/legal-matrix';
import { getUserName } from '@/lib/get-user-name';
import { useLegalMatrix } from '@/lib/legal-matrix-store';
import type { NormDetailViewProps } from './NormDetailView.types';

const FUENTE_LABEL = { BCN: 'Pública (BCN)', ISO: 'ISO interna', RCA: 'RCA del tenant' } as const;

/** S-09 Detalle de Norma + Evaluación por Artículo. */
export function NormDetailView({ norm: normProp, activeTenantId, responsableOptions }: NormDetailViewProps) {
  const { norms } = useLegalMatrix();
  const norm = norms.find((n) => n.id === normProp.id) ?? normProp;

  const [editingArticulo, setEditingArticulo] = useState<Articulo | null>(null);
  const [configOpen, setConfigOpen] = useState(false);

  const pct = computeNormCompliance(norm);

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{FUENTE_LABEL[norm.fuente]}</span>
            <h1 className="mt-1 text-xl font-semibold text-slate-900">{norm.nombre}</h1>
            {norm.fuenteUrl && (
              <a
                href={norm.fuenteUrl}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-sm text-brand-600 hover:underline"
              >
                Ver fuente oficial <ExternalLink className="h-3.5 w-3.5" aria-hidden />
              </a>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <StatusBadge status={normSemaforo(pct)} />
              <p className="mt-1 text-2xl font-semibold text-brand-700">{Math.round(pct * 100)}%</p>
            </div>
            <Button variant="secondary" onClick={() => setConfigOpen(true)} icon={<Settings className="h-4 w-4" aria-hidden />}>
              Configurar cálculo
            </Button>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
        <table className="w-full min-w-[840px] text-sm">
          <caption className="sr-only">Artículos de {norm.nombre} y su estado de cumplimiento</caption>
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
              <th scope="col" className="px-4 py-3">Artículo</th>
              <th scope="col" className="px-4 py-3">Estado</th>
              <th scope="col" className="px-4 py-3">Forma de cumplimiento</th>
              <th scope="col" className="px-4 py-3">Responsable</th>
              <th scope="col" className="px-4 py-3">Evidencia</th>
              <th scope="col" className="px-4 py-3">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {norm.articulos.map((articulo) => (
              <tr key={articulo.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-800">{articulo.numero}</p>
                  <p className="text-slate-500">{articulo.descripcion}</p>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={articuloSemaforo(articulo.respuesta)} />
                </td>
                <td className="max-w-xs px-4 py-3 text-slate-500">{articulo.formaCumplimiento ?? '—'}</td>
                <td className="px-4 py-3 text-slate-500">{getUserName(articulo.responsableId)}</td>
                <td className="px-4 py-3">
                  {articulo.evidenciaUrl ? (
                    <a href={articulo.evidenciaUrl} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">
                      Ver evidencia
                    </a>
                  ) : (
                    <span className="text-slate-400">Sin evidencia</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <Button variant="ghost" size="md" onClick={() => setEditingArticulo(articulo)}>
                    Evaluar
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ArticleEvaluationModal
        articulo={editingArticulo}
        normId={norm.id}
        normNombre={norm.nombre}
        tenantId={activeTenantId}
        responsableOptions={responsableOptions}
        onOpenChange={(open) => !open && setEditingArticulo(null)}
      />
      <ComplianceConfigModal norm={norm} open={configOpen} onOpenChange={setConfigOpen} />
    </div>
  );
}
