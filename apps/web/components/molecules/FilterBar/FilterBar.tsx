import type { FilterBarProps } from './FilterBar.types';

/** Filtros persistentes y visibles (H6) — reutilizado por Matriz Legal y futuras tablas (Catálogo, Usuarios). */
export function FilterBar({ filters }: FilterBarProps) {
  return (
    <div className="flex flex-wrap gap-3">
      {filters.map((filter) => (
        <label key={filter.id} className="flex flex-col gap-1 text-xs font-medium text-slate-600">
          {filter.label}
          <select
            id={filter.id}
            value={filter.value}
            onChange={(e) => filter.onChange(e.target.value)}
            className="h-10 rounded-lg border border-slate-300 px-2 text-sm text-slate-700"
          >
            {filter.options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      ))}
    </div>
  );
}
