import Link from 'next/link';
import { StatusBadge } from '@/components/atoms';
import type { DeadlineListItemProps } from './DeadlineListItem.types';

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

/** RF-49: acceso directo desde el Dashboard al detalle de la obligación (Sección E). */
export function DeadlineListItem({ obligation }: DeadlineListItemProps) {
  return (
    <li className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2.5">
      <div className="min-w-0">
        <Link href={`/obligaciones/${obligation.id}`} className="truncate text-sm font-medium text-slate-800 hover:underline">
          {obligation.nombre}
        </Link>
        <p className="text-xs text-slate-500">
          {obligation.codigo} · Vence {formatFecha(obligation.proximoVencimiento)}
        </p>
      </div>
      <StatusBadge status={obligation.estado} />
    </li>
  );
}
