import { cn } from '@/lib/utils';
import type { MetricCounterProps } from './MetricCounter.types';

const TONE_CLASSES: Record<NonNullable<MetricCounterProps['tone']>, string> = {
  neutral: 'text-slate-700 bg-slate-50',
  warning: 'text-semaforo-parcial bg-semaforo-parcial-bg',
  danger: 'text-semaforo-no-cumple bg-semaforo-no-cumple-bg',
};

export function MetricCounter({ label, value, icon: MetricIcon, tone = 'neutral' }: MetricCounterProps) {
  return (
    <div className={cn('flex items-center gap-3 rounded-card p-4', TONE_CLASSES[tone])}>
      <MetricIcon className="h-6 w-6 shrink-0" aria-hidden />
      <div>
        <p className="text-2xl font-semibold leading-none">{value}</p>
        <p className="mt-1 text-xs text-slate-600">{label}</p>
      </div>
    </div>
  );
}
