import { CheckCircle2, AlertTriangle, XCircle, MinusCircle, Clock, FileWarning, HelpCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SemaforoStatus, StatusBadgeProps } from './StatusBadge.types';

const STATUS_CONFIG: Record<
  SemaforoStatus,
  { label: string; icon: typeof CheckCircle2; classes: string }
> = {
  cumple: { label: 'Cumple', icon: CheckCircle2, classes: 'text-semaforo-cumple bg-semaforo-cumple-bg' },
  vigente: { label: 'Vigente', icon: CheckCircle2, classes: 'text-semaforo-cumple bg-semaforo-cumple-bg' },
  parcial: { label: 'Parcial', icon: AlertTriangle, classes: 'text-semaforo-parcial bg-semaforo-parcial-bg' },
  por_vencer: { label: 'Por vencer', icon: Clock, classes: 'text-semaforo-parcial bg-semaforo-parcial-bg' },
  no_cumple: { label: 'No cumple', icon: XCircle, classes: 'text-semaforo-no-cumple bg-semaforo-no-cumple-bg' },
  vencida: { label: 'Vencida', icon: XCircle, classes: 'text-semaforo-no-cumple bg-semaforo-no-cumple-bg' },
  sin_evidencia: { label: 'Sin evidencia', icon: FileWarning, classes: 'text-semaforo-no-cumple bg-semaforo-no-cumple-bg' },
  na: { label: 'No aplica', icon: MinusCircle, classes: 'text-semaforo-na bg-semaforo-na-bg' },
  pendiente: { label: 'Pendiente de evaluar', icon: HelpCircle, classes: 'text-semaforo-na bg-semaforo-na-bg' },
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const { label, icon: StatusIcon, classes } = STATUS_CONFIG[status];

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
        classes,
        className,
      )}
    >
      <StatusIcon className="h-3.5 w-3.5" aria-hidden />
      {label}
    </span>
  );
}
