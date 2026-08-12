import Link from 'next/link';
import { BellOff, CheckCheck } from 'lucide-react';
import { Button, StatusBadge } from '@/components/atoms';
import { urgenciaSemaforo } from '@/lib/notification-status';
import type { NotificationCenterProps } from './NotificationCenter.types';

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

/** S-31 Centro de Notificaciones: indicadores de urgencia ícono+color+texto, marcar todas como leídas, estado vacío. */
export function NotificationCenter({ notifications, onMarkAllAsRead }: NotificationCenterProps) {
  const ordenadas = [...notifications].sort((a, b) => new Date(b.fecha).getTime() - new Date(a.fecha).getTime());
  const hayNoLeidas = notifications.some((n) => !n.leida);

  if (notifications.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
        <BellOff className="h-6 w-6 text-slate-400" aria-hidden />
        No tienes notificaciones por ahora.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <Button variant="secondary" size="md" disabled={!hayNoLeidas} icon={<CheckCheck className="h-4 w-4" aria-hidden />} onClick={onMarkAllAsRead}>
          Marcar todas como leídas
        </Button>
      </div>
      <ul className="flex flex-col gap-2">
        {ordenadas.map((n) => {
          const content = (
            <div className={`flex items-start justify-between gap-3 rounded-card border p-4 ${n.leida ? 'border-slate-100 bg-white' : 'border-brand-200 bg-brand-50/40'}`}>
              <div>
                <p className="text-sm font-medium text-slate-800">{n.titulo}</p>
                <p className="mt-0.5 text-sm text-slate-600">{n.mensaje}</p>
                <p className="mt-1 text-xs text-slate-400">{formatFecha(n.fecha)}</p>
              </div>
              <StatusBadge status={urgenciaSemaforo(n.urgencia)} className="shrink-0" />
            </div>
          );
          return (
            <li key={n.id}>
              {n.obligationId ? (
                <Link href={`/obligaciones/${n.obligationId}`} className="block hover:opacity-90">
                  {content}
                </Link>
              ) : (
                content
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
