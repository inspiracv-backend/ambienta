import Link from 'next/link';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

type Tono = 'neutro' | 'positivo' | 'atencion' | 'critico';

interface StatCardProps {
  etiqueta: string;
  valor: string | number;
  /** Contexto que hace interpretable el número: "de 12 obligaciones", "esta semana". */
  detalle?: string;
  icono?: LucideIcon;
  tono?: Tono;
  /** Si se pasa, la tarjeta completa se vuelve un enlace a la pantalla que profundiza el dato. */
  href?: string;
}

const TONO: Record<Tono, { valor: string; icono: string; borde: string }> = {
  neutro: { valor: 'text-slate-900', icono: 'bg-slate-100 text-slate-500', borde: 'border-slate-200' },
  positivo: { valor: 'text-semaforo-cumple', icono: 'bg-semaforo-cumple-bg text-semaforo-cumple', borde: 'border-slate-200' },
  atencion: { valor: 'text-semaforo-parcial', icono: 'bg-semaforo-parcial-bg text-semaforo-parcial', borde: 'border-semaforo-parcial/30' },
  critico: { valor: 'text-semaforo-no-cumple', icono: 'bg-semaforo-no-cumple-bg text-semaforo-no-cumple', borde: 'border-semaforo-no-cumple/30' },
};

/**
 * Métrica de dashboard.
 *
 * Tres decisiones deliberadas:
 * - El `detalle` no es decorativo: un "3" sin contexto no dice si es mucho o
 *   poco. Sin denominador o periodo, el número no es accionable.
 * - El tono nunca es el único portador de significado — siempre va con la
 *   etiqueta en texto (mismo criterio de semáforo del resto del sistema:
 *   ícono + color + texto, para daltonismo).
 * - Con `href` la tarjeta entera es clickeable: ver un número alarmante y no
 *   poder profundizar es el patrón que más fricción genera en dashboards.
 */
export function StatCard({ etiqueta, valor, detalle, icono: Icono, tono = 'neutro', href }: StatCardProps) {
  const estilo = TONO[tono];

  const contenido = (
    <>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-slate-600">{etiqueta}</p>
        {Icono && (
          <span className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg', estilo.icono)}>
            <Icono className="h-4 w-4" aria-hidden />
          </span>
        )}
      </div>
      <p className={cn('mt-2 text-3xl font-semibold tabular-nums tracking-tight', estilo.valor)}>{valor}</p>
      {detalle && <p className="mt-1 text-xs text-slate-500">{detalle}</p>}
    </>
  );

  const clases = cn('block rounded-card border bg-white p-4 shadow-sm', estilo.borde);

  if (href) {
    return (
      <Link
        href={href}
        className={cn(
          clases,
          'transition hover:border-brand-400 hover:shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
        )}
      >
        {contenido}
      </Link>
    );
  }

  return <div className={clases}>{contenido}</div>;
}
