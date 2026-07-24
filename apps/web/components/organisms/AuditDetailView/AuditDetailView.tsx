import Link from 'next/link';
import { Plus } from 'lucide-react';
import { Button, StatusBadge } from '@/components/atoms';
import { auditSemaforo, AUDIT_ESTADO_LABEL, ncSemaforo, NC_ESTADO_LABEL } from '@/lib/audit-status';
import type { AuditDetailViewProps } from './AuditDetailView.types';

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

/** S-21 Detalle de Auditoría: procesos, departamentos, normativas asociadas y hallazgos generados desde ella. */
export function AuditDetailView({ audit, plant, normativas, hallazgos }: AuditDetailViewProps) {
  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Auditoría {audit.tipo} · {plant?.nombre ?? audit.plantId}
            </span>
            <h1 className="mt-1 text-xl font-semibold text-slate-900">{formatFecha(audit.fecha)}</h1>
          </div>
          <div className="text-right">
            <StatusBadge status={auditSemaforo(audit.estado)} />
            <p className="mt-1 text-sm text-slate-500">{AUDIT_ESTADO_LABEL[audit.estado]}</p>
          </div>
        </div>

        <div className="mt-4">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Procesos y departamentos</h2>
          <p className="mt-1 text-sm text-slate-700">{audit.procesos.join(', ')}</p>
        </div>

        <div className="mt-4">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Normativas asociadas</h2>
          {normativas.length === 0 ? (
            <p className="mt-1 text-sm text-slate-400">Sin normativas vinculadas.</p>
          ) : (
            <ul className="mt-1 flex flex-col gap-1">
              {normativas.map((n) => (
                <li key={n.id}>
                  <Link href={`/matriz-legal/${n.id}`} className="text-sm text-brand-600 hover:underline">
                    {n.nombre}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-700">Hallazgos generados desde esta auditoría</h2>
          <Link href={`/no-conformidades/nueva?auditId=${audit.id}&plantId=${audit.plantId}`}>
            <Button size="md" icon={<Plus className="h-4 w-4" aria-hidden />}>
              Registrar hallazgo
            </Button>
          </Link>
        </div>

        {hallazgos.length === 0 ? (
          <p className="mt-3 rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
            Sin hallazgos registrados todavía.
          </p>
        ) : (
          <ul className="mt-3 flex flex-col gap-2">
            {hallazgos.map((nc) => (
              <li key={nc.id}>
                <Link
                  href={`/no-conformidades/${nc.id}`}
                  className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2.5 hover:bg-slate-50"
                >
                  <span className="text-sm text-slate-800">{nc.hallazgo}</span>
                  <StatusBadge status={ncSemaforo(nc.estado)} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
