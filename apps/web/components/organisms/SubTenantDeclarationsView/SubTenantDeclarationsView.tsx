import Link from 'next/link';
import { Inbox } from 'lucide-react';
import { StatusBadge } from '@/components/atoms';
import type { SubTenantDeclarationsViewProps } from './SubTenantDeclarationsView.types';

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

/**
 * S-30 Declaraciones del Sub-tenant — reutiliza la entidad `Obligation` de la
 * Sección E (mismo modelo, sin duplicar). La creación queda para una futura
 * extensión de `CreateObligationModal` con soporte de `subTenantId`.
 */
export function SubTenantDeclarationsView({ obligations, subTenantNombre }: SubTenantDeclarationsViewProps) {
  if (obligations.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
        <Inbox className="h-6 w-6 text-slate-400" aria-hidden />
        {subTenantNombre} no tiene declaraciones registradas todavía.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
      <table className="w-full min-w-[640px] text-sm">
        <caption className="sr-only">Declaraciones de {subTenantNombre}</caption>
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
            <th scope="col" className="px-4 py-3">Declaración</th>
            <th scope="col" className="px-4 py-3">Período</th>
            <th scope="col" className="px-4 py-3">Estado</th>
            <th scope="col" className="px-4 py-3">Próximo vencimiento</th>
          </tr>
        </thead>
        <tbody>
          {obligations.map((o) => (
            <tr key={o.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
              <td className="px-4 py-3 font-medium text-slate-800">
                <Link href={`/obligaciones/${o.id}`} className="hover:underline">
                  {o.nombre}
                </Link>
                <p className="text-xs font-normal text-slate-500">{o.sistema}</p>
              </td>
              <td className="px-4 py-3 text-slate-500">{o.periodo}</td>
              <td className="px-4 py-3">
                <StatusBadge status={o.estado} />
              </td>
              <td className="px-4 py-3 text-slate-500">{formatFecha(o.proximoVencimiento)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
