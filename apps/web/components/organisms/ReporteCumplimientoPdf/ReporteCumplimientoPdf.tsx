'use client';

import { useState } from 'react';
import { FileText, Printer } from 'lucide-react';
import type { LegalNorm, NonConformity, Obligation, Plant, Tenant, User } from '@ambienta/shared';
import { Button } from '@/components/atoms';
import { computeNormCompliance, countArticulosEnIncumplimiento } from '@/lib/legal-matrix';
import { computePlantMetrics } from '@/lib/dashboard-metrics';
import { NC_ESTADO_LABEL, CRITICIDAD_LABEL } from '@/lib/audit-status';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { ReportePdf } from '@/components/organisms/ReportePdf';
import { cn } from '@/lib/utils';

function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

/**
 * Informe de cumplimiento imprimible (RF-57).
 *
 * Complementa la exportación a CSV en vez de reemplazarla: el CSV sirve para
 * que alguien procese los datos, el PDF para entregarlo. Un fiscalizador o un
 * certificador no recibe una planilla — recibe un documento con la
 * identificación de la empresa, la fecha de emisión y quién lo emitió.
 *
 * La emisión queda registrada en el audit log: RNF-26 pide que los datos sean
 * exportables para auditorías externas, y saber qué salió del sistema y
 * cuándo es parte de esa trazabilidad.
 */
export function ReporteCumplimientoPdf({
  tenant,
  usuario,
  plants,
  obligations,
  norms,
  nonConformities,
}: {
  tenant: Tenant;
  usuario: User;
  plants: Plant[];
  obligations: Obligation[];
  norms: LegalNorm[];
  nonConformities: NonConformity[];
}) {
  const [visible, setVisible] = useState(false);
  const registrar = useRegistrarAuditoria();

  const metrics = computePlantMetrics(plants, obligations, nonConformities);
  const cumplimientoGlobal =
    metrics.length > 0 ? metrics.reduce((s, m) => s + m.cumplimientoPct, 0) / metrics.length : 0;
  const ncAbiertas = nonConformities.filter((nc) => nc.estado !== 'cerrada');

  function handleImprimir() {
    registrar({
      entidadTipo: 'tenant',
      entidadId: tenant.id,
      entidadLabel: tenant.nombre,
      tenantId: tenant.id,
      accion: 'exportado',
      resumen: 'Emitió el informe de cumplimiento en PDF',
      cambios: [
        { campo: 'Plantas incluidas', antes: null, despues: String(plants.length) },
        { campo: 'Cumplimiento global', antes: null, despues: pct(cumplimientoGlobal) },
      ],
    });
    window.print();
  }

  return (
    <section aria-labelledby="informe-pdf" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div>
          <h2 id="informe-pdf" className="text-sm font-semibold text-slate-900">
            Informe de cumplimiento (PDF)
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Documento con el encabezado de la empresa, para entregar a un fiscalizador o certificador.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="md"
            onClick={() => setVisible((v) => !v)}
            icon={<FileText className="h-4 w-4" aria-hidden />}
          >
            {visible ? 'Ocultar vista previa' : 'Ver vista previa'}
          </Button>
          {visible && (
            <Button size="md" onClick={handleImprimir} icon={<Printer className="h-4 w-4" aria-hidden />}>
              Imprimir / Guardar PDF
            </Button>
          )}
        </div>
      </div>

      {visible && (
        <ReportePdf
          tenant={tenant}
          titulo="Informe de cumplimiento"
          subtitulo={`${plants.length} planta(s) · ${norms.length} norma(s)`}
          emitidoPor={usuario.nombre}
        >
          <section className="evitar-corte">
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-800">Resumen ejecutivo</h2>
            <dl className="mt-2 grid grid-cols-3 gap-3">
              <div className="rounded border border-slate-200 p-3">
                <dt className="text-[10px] uppercase tracking-wide text-slate-500">Cumplimiento global</dt>
                <dd className="mt-0.5 text-2xl font-bold tabular-nums text-slate-900">{pct(cumplimientoGlobal)}</dd>
              </div>
              <div className="rounded border border-slate-200 p-3">
                <dt className="text-[10px] uppercase tracking-wide text-slate-500">Obligaciones</dt>
                <dd className="mt-0.5 text-2xl font-bold tabular-nums text-slate-900">{obligations.length}</dd>
              </div>
              <div className="rounded border border-slate-200 p-3">
                <dt className="text-[10px] uppercase tracking-wide text-slate-500">No conformidades abiertas</dt>
                <dd
                  className={cn(
                    'mt-0.5 text-2xl font-bold tabular-nums',
                    ncAbiertas.length > 0 ? 'text-semaforo-no-cumple' : 'text-slate-900',
                  )}
                >
                  {ncAbiertas.length}
                </dd>
              </div>
            </dl>
          </section>

          <section className="mt-6 evitar-corte">
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-800">Cumplimiento por planta</h2>
            <table className="mt-2 w-full border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-300 text-left">
                  <th className="py-1.5 pr-2 font-semibold">Planta</th>
                  <th className="py-1.5 pr-2 font-semibold">Ubicación</th>
                  <th className="py-1.5 pr-2 text-right font-semibold">Cumplimiento</th>
                  <th className="py-1.5 text-right font-semibold">Incumplimientos</th>
                </tr>
              </thead>
              <tbody>
                {metrics.map((m) => (
                  <tr key={m.plant.id} className="border-b border-slate-100">
                    <td className="py-1.5 pr-2 font-medium text-slate-800">{m.plant.nombre}</td>
                    <td className="py-1.5 pr-2 text-slate-500">
                      {m.plant.comuna}, {m.plant.region}
                    </td>
                    <td className="py-1.5 pr-2 text-right tabular-nums">{pct(m.cumplimientoPct)}</td>
                    <td
                      className={cn(
                        'py-1.5 text-right tabular-nums',
                        m.incumplimientos > 0 && 'font-semibold text-semaforo-no-cumple',
                      )}
                    >
                      {m.incumplimientos}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="mt-6">
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-800">Matriz legal</h2>
            <table className="mt-2 w-full border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-300 text-left">
                  <th className="py-1.5 pr-2 font-semibold">Norma</th>
                  <th className="py-1.5 pr-2 font-semibold">Fuente</th>
                  <th className="py-1.5 pr-2 text-right font-semibold">Cumplimiento</th>
                  <th className="py-1.5 text-right font-semibold">Art. en incumplimiento</th>
                </tr>
              </thead>
              <tbody>
                {norms.map((n) => (
                  <tr key={n.id} className="border-b border-slate-100">
                    <td className="py-1.5 pr-2 font-medium text-slate-800">{n.nombre}</td>
                    <td className="py-1.5 pr-2 text-slate-500">{n.fuente}</td>
                    <td className="py-1.5 pr-2 text-right tabular-nums">{pct(computeNormCompliance(n))}</td>
                    <td className="py-1.5 text-right tabular-nums">{countArticulosEnIncumplimiento(n)}</td>
                  </tr>
                ))}
                {norms.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-2 text-slate-500">
                      Sin normas asignadas a las plantas de este informe.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>

          <section className="mt-6">
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-800">No conformidades abiertas</h2>
            {ncAbiertas.length === 0 ? (
              <p className="mt-2 text-xs text-slate-500">
                No hay no conformidades abiertas al momento de emitir este informe.
              </p>
            ) : (
              <table className="mt-2 w-full border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-300 text-left">
                    <th className="py-1.5 pr-2 font-semibold">Hallazgo</th>
                    <th className="py-1.5 pr-2 font-semibold">Criticidad</th>
                    <th className="py-1.5 font-semibold">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {ncAbiertas.map((nc) => (
                    <tr key={nc.id} className="border-b border-slate-100">
                      <td className="py-1.5 pr-2 text-slate-800">{nc.hallazgo}</td>
                      <td className="py-1.5 pr-2">{CRITICIDAD_LABEL[nc.criticidad]}</td>
                      <td className="py-1.5">{NC_ESTADO_LABEL[nc.estado]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </ReportePdf>
      )}
    </section>
  );
}
