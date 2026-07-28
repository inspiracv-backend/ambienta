import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

interface EmptyStateProps {
  icono?: LucideIcon;
  titulo: string;
  /** Qué hacer para salir del estado vacío, no solo la constatación de que está vacío. */
  descripcion: string;
  accion?: ReactNode;
}

/**
 * Estado vacío con salida.
 *
 * Los estados vacíos del sistema decían solo "No hay X" — cierto pero inútil:
 * el usuario queda sin saber si es porque filtró de más, porque aún no cargó
 * nada, o porque algo falló. Este componente obliga a dar el siguiente paso
 * (H1: el sistema informa qué está pasando; H10: ayuda en contexto).
 */
export function EmptyState({ icono: Icono, titulo, descripcion, accion }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-card border border-dashed border-slate-300 bg-slate-50/50 px-6 py-12 text-center">
      {Icono && (
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-white text-slate-400 shadow-sm">
          <Icono className="h-5 w-5" aria-hidden />
        </span>
      )}
      <div className="max-w-sm">
        <p className="text-sm font-semibold text-slate-800">{titulo}</p>
        <p className="mt-1 text-sm text-slate-500">{descripcion}</p>
      </div>
      {accion}
    </div>
  );
}
