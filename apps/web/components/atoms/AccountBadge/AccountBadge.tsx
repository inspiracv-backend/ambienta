import { CircleCheck, CircleSlash } from 'lucide-react';
import { cn } from '@/lib/utils';

type EstadoCuenta = 'activo' | 'suspendido';

const ESTADO: Record<EstadoCuenta, { label: string; clase: string; icono: typeof CircleCheck }> = {
  activo: { label: 'Activa', clase: 'bg-slate-100 text-slate-700', icono: CircleCheck },
  suspendido: { label: 'Suspendida', clase: 'bg-semaforo-no-cumple-bg text-semaforo-no-cumple', icono: CircleSlash },
};

/**
 * Estado administrativo de una cuenta (tenant o usuario).
 *
 * Existe separado de `StatusBadge` porque ese muestra el semáforo de
 * cumplimiento ambiental — cumple / parcial / no cumple. Una empresa
 * suspendida por impago no "no cumple" con la normativa ambiental, y
 * mostrarla en rojo con esa etiqueta le decía al Superadmin algo falso sobre
 * su situación regulatoria. Son dos ejes distintos que se veían igual.
 *
 * "Activa" va en gris y no en verde a propósito: es el estado normal, no un
 * logro. Reservar el color para lo excepcional hace que lo excepcional
 * destaque.
 */
export function AccountBadge({ estado }: { estado: EstadoCuenta }) {
  const { label, clase, icono: Icono } = ESTADO[estado];
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium', clase)}>
      <Icono className="h-3.5 w-3.5" aria-hidden />
      {label}
    </span>
  );
}
