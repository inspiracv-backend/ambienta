import Link from 'next/link';
import { FileText, ScrollText, ShieldCheck } from 'lucide-react';
import { StatusBadge } from '@/components/atoms';
import type { SubTenantDetailViewProps } from './SubTenantDetailView.types';

/** S-28 Detalle de Cliente: datos, contactos y personas autorizadas. */
export function SubTenantDetailView({ subTenant }: SubTenantDetailViewProps) {
  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">RUT {subTenant.rut}</span>
            <h1 className="mt-1 text-xl font-semibold text-slate-900">{subTenant.nombre}</h1>
          </div>
          <StatusBadge status={subTenant.estado === 'activo' ? 'cumple' : 'no_cumple'} />
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            href={`/gestores/${subTenant.id}/contratos`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <FileText className="h-4 w-4" aria-hidden />
            Contratos
          </Link>
          <Link
            href={`/gestores/${subTenant.id}/declaraciones`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <ScrollText className="h-4 w-4" aria-hidden />
            Declaraciones
          </Link>
        </div>
      </div>

      <div className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Contactos y personas autorizadas</h2>
        <ul className="flex flex-col gap-2">
          {subTenant.contactos.map((c) => (
            <li key={c.id} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2.5">
              <div>
                <p className="text-sm font-medium text-slate-800">{c.nombre}</p>
                <p className="text-xs text-slate-500">
                  {c.cargo} · {c.telefono} · {c.email}
                </p>
              </div>
              {c.autorizado && (
                <span className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
                  <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
                  Autorizado
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
