import Link from 'next/link';
import { AlertTriangle, Settings } from 'lucide-react';
import { StatusBadge } from '@/components/atoms';
import { cn } from '@/lib/utils';
import type { DashboardHeroCardProps } from './DashboardHeroCard.types';

function diasRestantes(iso: string) {
  return Math.ceil((new Date(iso).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
}

/**
 * S-06: card hero con próximo vencimiento crítico + resumen de % cumplimiento
 * global. El botón de configuración del cálculo (RF-51 / S-11) vive por norma
 * en Matriz Legal (Sección D) — aquí solo enlaza hacia allá.
 */
export function DashboardHeroCard({ obligation, cumplimientoPct }: DashboardHeroCardProps) {
  const dias = obligation ? diasRestantes(obligation.proximoVencimiento) : null;
  const esCritico = dias !== null && dias <= 7;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div
        className={cn(
          'rounded-card border p-6',
          esCritico ? 'border-semaforo-no-cumple bg-semaforo-no-cumple-bg' : 'border-slate-200 bg-white',
        )}
      >
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          {esCritico && <AlertTriangle className="h-4 w-4 text-semaforo-no-cumple" aria-hidden />}
          Próximo vencimiento crítico
        </div>
        {obligation ? (
          <>
            <p className="mt-2 text-lg font-semibold text-slate-900">{obligation.nombre}</p>
            <p className="mt-1 text-sm text-slate-600">
              {dias !== null && dias >= 0 ? `${dias} días restantes` : 'Vencida'}
            </p>
            <StatusBadge status={obligation.estado} className="mt-3" />
          </>
        ) : (
          <p className="mt-2 text-sm text-slate-500">No hay vencimientos próximos para este tenant.</p>
        )}
      </div>

      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            % de cumplimiento global
          </span>
          <Link
            href="/matriz-legal"
            title="Configurar en Matriz Legal"
            aria-label="Ir a Matriz Legal para configurar el cálculo de cumplimiento"
            className="text-slate-400 hover:text-slate-700"
          >
            <Settings className="h-4 w-4" aria-hidden />
          </Link>
        </div>
        <p className="mt-2 text-3xl font-semibold text-brand-700">{Math.round(cumplimientoPct * 100)}%</p>
      </div>
    </div>
  );
}
