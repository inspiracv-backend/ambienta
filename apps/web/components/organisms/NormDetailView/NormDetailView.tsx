'use client';

import { useState } from 'react';
import { ChevronDown, ExternalLink, Settings } from 'lucide-react';
import type { Articulo } from '@ambienta/shared';
import { Button, StatusBadge } from '@/components/atoms';
import { ArticleEvaluationModal } from '@/components/organisms/ArticleEvaluationModal';
import { ComplianceConfigModal } from '@/components/organisms/ComplianceConfigModal';
import { articuloSemaforo, normSemaforoDe, resumenDeNorma } from '@/lib/legal-matrix';
import { getUserName } from '@/lib/get-user-name';
import { useLegalMatrix } from '@/lib/legal-matrix-store';
import type { NormDetailViewProps } from './NormDetailView.types';

const FUENTE_LABEL = { BCN: 'Pública (BCN)', ISO: 'ISO interna', RCA: 'RCA del tenant' } as const;

/**
 * Cuántos caracteres del artículo se muestran plegados.
 *
 * El articulado real de la BCN no se parece al sembrado: el artículo 3º del DS
 * 13 tiene **1.400 caracteres** y ocupaba media pantalla él solo. Plegado a dos
 * líneas la tabla vuelve a escanearse de un vistazo, y el texto completo sigue
 * a un clic — **no se esconde, se pliega**: es el texto legal que la persona
 * tiene que leer para evaluar.
 */
const PLEGADO = 220;

function TextoDeArticulo({ texto }: { texto: string }) {
  const [abierto, setAbierto] = useState(false);
  const largo = texto.length > PLEGADO;

  if (!largo) return <p className="mt-0.5 text-slate-500">{texto}</p>;

  return (
    <div className="mt-0.5">
      <p className={abierto ? 'text-slate-500' : 'line-clamp-2 text-slate-500'}>{texto}</p>
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline"
      >
        {abierto ? 'Ver menos' : 'Ver texto completo'}
        <ChevronDown className={abierto ? 'h-3.5 w-3.5 rotate-180' : 'h-3.5 w-3.5'} aria-hidden />
      </button>
    </div>
  );
}

/** S-09 Detalle de Norma + Evaluación por Artículo. */
export function NormDetailView({ norm: normProp, activeTenantId, responsableOptions }: NormDetailViewProps) {
  const { norms } = useLegalMatrix();
  const norm = norms.find((n) => n.id === normProp.id) ?? normProp;

  const [editingArticulo, setEditingArticulo] = useState<Articulo | null>(null);
  const [configOpen, setConfigOpen] = useState(false);

  const resumen = resumenDeNorma(norm);
  const avance = resumen.aplicables === 0 ? 0 : resumen.evaluados / resumen.aplicables;

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0 flex-1 basis-80">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{FUENTE_LABEL[norm.fuente]}</span>
            {/* `text-lg` y no `text-xl`: los titulos de la BCN vienen en
                mayusculas y con 90 caracteres —"APRUEBA REGLAMENTO DEL REGISTRO
                DE EMISIONES Y TRANSFERENCIAS DE CONTAMINANTES, RETC"— y a
                tamano de titular ocupaban dos lineas de grito. */}
            <h1 className="mt-1 text-lg font-semibold leading-snug text-slate-900">{norm.nombre}</h1>
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

          <div className="flex shrink-0 items-start gap-4">
            {/* El bloque que antes decia "No cumple / 0%" sin que nadie hubiera
                evaluado nada. Ahora el numero solo aparece cuando existe. */}
            <div
              role="group"
              aria-label="Resumen de cumplimiento de la norma"
              className="w-56 rounded-lg border border-slate-200 bg-slate-50 p-4"
            >
              <StatusBadge status={normSemaforoDe(resumen.pct)} />
              {resumen.pct === null ? (
                <p className="mt-2 text-sm text-slate-600">
                  Todavía no hay artículos evaluados, así que aún no se puede calcular el cumplimiento.
                </p>
              ) : (
                <p className="mt-2 text-3xl font-semibold tabular-nums text-brand-700">
                  {Math.round(resumen.pct * 100)}%
                  <span className="ml-1 text-xs font-normal text-slate-500">de cumplimiento</span>
                </p>
              )}

              <div className="mt-3">
                <div className="flex items-baseline justify-between text-xs text-slate-600">
                  <span>Avance de la revisión</span>
                  <span className="font-medium tabular-nums">
                    {resumen.evaluados}/{resumen.aplicables}
                  </span>
                </div>
                <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                  <div className="h-full rounded-full bg-brand-600" style={{ width: `${Math.round(avance * 100)}%` }} />
                </div>
                <p className="mt-1.5 text-xs text-slate-500">
                  {resumen.sinEvaluar === 0
                    ? 'Todos los artículos aplicables están evaluados.'
                    : `${resumen.sinEvaluar} ${resumen.sinEvaluar === 1 ? 'artículo' : 'artículos'} sin evaluar`}
                  {resumen.incumplidos > 0 && ` · ${resumen.incumplidos} en incumplimiento`}
                </p>
              </div>
            </div>

            <Button variant="secondary" onClick={() => setConfigOpen(true)} icon={<Settings className="h-4 w-4" aria-hidden />}>
              Configurar cálculo
            </Button>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
        <table className="w-full min-w-[840px] table-fixed text-sm">
          <caption className="sr-only">Artículos de {norm.nombre} y su estado de cumplimiento</caption>
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
              <th scope="col" className="w-[46%] px-4 py-3">Artículo</th>
              <th scope="col" className="w-[14%] px-4 py-3">Estado</th>
              <th scope="col" className="w-[16%] px-4 py-3">Forma de cumplimiento</th>
              <th scope="col" className="w-[12%] px-4 py-3">Responsable</th>
              <th scope="col" className="w-[7%] px-4 py-3">Evidencia</th>
              <th scope="col" className="w-[5%] px-4 py-3 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {norm.articulos.map((articulo) => (
              <tr
                key={articulo.id}
                // El ancla que hace util el atajo desde `/incumplimientos`:
                // sin ella, el enlace deja a la persona al principio de una
                // norma de 151 articulos buscando el que la trajo.
                id={`articulo-${articulo.id}`}
                className="border-b border-slate-100 align-top last:border-0 target:bg-amber-50 hover:bg-slate-50"
              >
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-800">{articulo.numero}</p>
                  <TextoDeArticulo texto={articulo.descripcion} />
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={articuloSemaforo(articulo.respuesta)} />
                </td>
                <td className="px-4 py-3 text-slate-500">{articulo.formaCumplimiento ?? '—'}</td>
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
                <td className="px-4 py-3 text-right">
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
