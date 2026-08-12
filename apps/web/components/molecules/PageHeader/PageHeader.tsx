import type { ReactNode } from 'react';

interface PageHeaderProps {
  titulo: string;
  descripcion?: string;
  /** Acciones principales de la pantalla, alineadas a la derecha en desktop. */
  acciones?: ReactNode;
}

/**
 * Encabezado de pantalla. Cada página venía repitiendo el mismo bloque
 * `<div><h1/><p/></div>` con clases ligeramente distintas, así que el tamaño
 * del título y el espaciado variaban de una sección a otra (H4: consistencia).
 *
 * En móvil las acciones bajan debajo del título en vez de comprimirlo.
 */
export function PageHeader({ titulo, descripcion, acciones }: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{titulo}</h1>
        {descripcion && <p className="mt-1 text-sm text-slate-500">{descripcion}</p>}
      </div>
      {acciones && <div className="flex shrink-0 flex-wrap items-center gap-2">{acciones}</div>}
    </div>
  );
}
