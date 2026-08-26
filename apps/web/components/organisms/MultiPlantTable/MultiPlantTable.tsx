import { StatusBadge } from '@/components/atoms';
import type { MultiPlantTableProps } from './MultiPlantTable.types';

/**
 * El semaforo de una planta, con `null` — nada evaluado — como `pendiente`.
 *
 * **Antes `null` caia en `no_cumple`.** Dos de las tres plantas del seed no
 * tienen una sola evaluacion, y el tablero ejecutivo las mostraba en rojo con
 * "0 %": la pantalla que el Admin Empresa mira para decidir donde poner
 * recursos lo mandaba a apagar un incendio que nadie habia comprobado que
 * existiera.
 */
function estadoSemaforo(pct: number | null) {
  if (pct === null) return 'pendiente' as const;
  if (pct >= 0.8) return 'cumple' as const;
  if (pct >= 0.5) return 'parcial' as const;
  return 'no_cumple' as const;
}

/** El porcentaje como texto, o el aviso de que todavia no hay ninguno. */
function texto(pct: number | null): string {
  return pct === null ? 'Sin evaluar' : `${Math.round(pct * 100)}%`;
}

/**
 * S-07 Dashboard Multi-Instalación. Tabla ejecutiva en desktop, tarjetas en
 * mobile (mismo dato, dos presentaciones) — organismo pensado para
 * generalizarse a un `DataTable` compartido cuando se implementen Matriz
 * Legal/Catálogo/Usuarios (H4, ver seccion-c-dashboard.md).
 * Ordenado por peor cumplimiento primero.
 */
export function MultiPlantTable({ metrics }: MultiPlantTableProps) {
  // Peor cumplimiento primero, **y las plantas sin evaluar al final**.
  //
  // Ordenarlas como si valieran cero las pondria arriba del todo, que es el
  // lugar reservado a lo urgente. Una planta que nadie miro no es la peor: es
  // una incognita, y encabezar la lista con incognitas tapa los problemas
  // reales que hay debajo.
  const ordered = [...metrics].sort((a, b) => {
    if (a.cumplimientoPct === null && b.cumplimientoPct === null) return 0;
    if (a.cumplimientoPct === null) return 1;
    if (b.cumplimientoPct === null) return -1;
    return a.cumplimientoPct - b.cumplimientoPct;
  });

  return (
    <div className="rounded-card border border-slate-200 bg-white">
      {/* Desktop: tabla */}
      <table className="hidden w-full text-sm md:table">
        <caption className="sr-only">Cumplimiento por planta, ordenado de peor a mejor</caption>
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
            <th scope="col" className="px-4 py-3">Planta</th>
            <th scope="col" className="px-4 py-3">Cumplimiento</th>
            <th scope="col" className="px-4 py-3">Incumplimientos</th>
            <th scope="col" className="px-4 py-3">NC activas</th>
            <th scope="col" className="px-4 py-3">Próximo vencimiento</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map(({ plant, cumplimientoPct, incumplimientos, noConformidadesActivas, proximoVencimiento }) => (
            <tr key={plant.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
              <td className="px-4 py-3 font-medium text-slate-800">{plant.nombre}</td>
              <td className="px-4 py-3">
                <StatusBadge status={estadoSemaforo(cumplimientoPct)} />
                <span className="ml-2 text-slate-500">{texto(cumplimientoPct)}</span>
              </td>
              <td className="px-4 py-3">{incumplimientos}</td>
              <td className="px-4 py-3">{noConformidadesActivas}</td>
              <td className="px-4 py-3 text-slate-500">{proximoVencimiento?.nombre ?? 'Sin pendientes'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Mobile: tarjetas */}
      <ul className="flex flex-col gap-3 p-4 md:hidden">
        {ordered.map(({ plant, cumplimientoPct, incumplimientos, noConformidadesActivas, proximoVencimiento }) => (
          <li key={plant.id} className="rounded-lg border border-slate-100 p-3">
            <div className="flex items-center justify-between">
              <span className="font-medium text-slate-800">{plant.nombre}</span>
              <StatusBadge status={estadoSemaforo(cumplimientoPct)} />
            </div>
            <dl className="mt-2 grid grid-cols-2 gap-y-1 text-xs text-slate-500">
              <dt>Incumplimientos</dt>
              <dd className="text-right">{incumplimientos}</dd>
              <dt>NC activas</dt>
              <dd className="text-right">{noConformidadesActivas}</dd>
              <dt>Próximo vencimiento</dt>
              <dd className="text-right">{proximoVencimiento?.nombre ?? 'Sin pendientes'}</dd>
            </dl>
          </li>
        ))}
      </ul>
    </div>
  );
}
