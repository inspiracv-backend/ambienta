'use client';

import { useEffect, useMemo, useState } from 'react';
import { Minus, Plus } from 'lucide-react';
import { Button } from '@/components/atoms';
import { useLegalMatrix } from '@/lib/legal-matrix-store';
import { FUENTE_LABEL } from '@/lib/catalog-status';
import type { AssignNormsToPlantProps } from './AssignNormsToPlant.types';

/** S-26 Definir Normas Aplicables por Planta: selector de dos columnas, cambios aplicados recién al Guardar (H3). */
export function AssignNormsToPlant({ plants, norms }: AssignNormsToPlantProps) {
  const { setNormPlants } = useLegalMatrix();
  const [plantId, setPlantId] = useState(plants[0]?.id ?? '');
  const [draftIds, setDraftIds] = useState<Set<string>>(new Set());
  const [busqueda, setBusqueda] = useState('');
  const [saved, setSaved] = useState(false);

  // Solo se reinicializa el borrador cuando cambia la planta seleccionada, no en
  // cada actualización de `norms` — de lo contrario, guardar (que muta `norms`)
  // dispararía este efecto y borraría el mensaje de confirmación al instante.
  useEffect(() => {
    setDraftIds(new Set(norms.filter((n) => n.plantIds.includes(plantId)).map((n) => n.id)));
    setSaved(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plantId]);

  const disponibles = useMemo(
    () =>
      norms.filter((n) => !draftIds.has(n.id) && n.nombre.toLowerCase().includes(busqueda.trim().toLowerCase())),
    [norms, draftIds, busqueda],
  );
  const asignadas = useMemo(() => norms.filter((n) => draftIds.has(n.id)), [norms, draftIds]);

  function addNorm(normId: string) {
    setDraftIds((prev) => new Set(prev).add(normId));
    setSaved(false);
  }

  function removeNorm(normId: string) {
    setDraftIds((prev) => {
      const next = new Set(prev);
      next.delete(normId);
      return next;
    });
    setSaved(false);
  }

  function handleGuardar() {
    norms.forEach((n) => {
      const debeEstar = draftIds.has(n.id);
      const yaEsta = n.plantIds.includes(plantId);
      if (debeEstar && !yaEsta) setNormPlants(n.id, [...n.plantIds, plantId]);
      if (!debeEstar && yaEsta) setNormPlants(n.id, n.plantIds.filter((id) => id !== plantId));
    });
    setSaved(true);
  }

  return (
    <div className="flex flex-col gap-4">
      <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
        Planta
        <select
          className="h-11 w-full max-w-xs rounded-lg border border-slate-300 px-3 text-sm"
          value={plantId}
          onChange={(e) => setPlantId(e.target.value)}
        >
          {plants.map((p) => (
            <option key={p.id} value={p.id}>
              {p.nombre}
            </option>
          ))}
        </select>
      </label>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-card border border-slate-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-semibold text-slate-700">Catálogo disponible</h2>
          <input
            type="search"
            placeholder="Buscar norma..."
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            className="mb-3 h-10 w-full rounded-lg border border-slate-300 px-3 text-sm"
          />
          <ul className="flex max-h-80 flex-col gap-1.5 overflow-y-auto">
            {disponibles.map((n) => (
              <li key={n.id} className="flex items-center justify-between gap-2 rounded-lg border border-slate-100 px-3 py-2 text-sm">
                <span className="truncate">
                  {n.nombre} <span className="text-xs text-slate-400">· {FUENTE_LABEL[n.fuente]}</span>
                </span>
                <button type="button" onClick={() => addNorm(n.id)} aria-label={`Agregar ${n.nombre}`} className="shrink-0 text-brand-600 hover:text-brand-700">
                  <Plus className="h-4 w-4" aria-hidden />
                </button>
              </li>
            ))}
            {disponibles.length === 0 && <li className="p-3 text-center text-xs text-slate-400">Sin resultados.</li>}
          </ul>
        </div>

        <div className="rounded-card border border-slate-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-semibold text-slate-700">Normas asignadas ({asignadas.length})</h2>
          <ul className="flex max-h-80 flex-col gap-1.5 overflow-y-auto">
            {asignadas.map((n) => (
              <li key={n.id} className="flex items-center justify-between gap-2 rounded-lg border border-slate-100 px-3 py-2 text-sm">
                <span className="truncate">
                  {n.nombre} <span className="text-xs text-slate-400">· {FUENTE_LABEL[n.fuente]}</span>
                </span>
                <button type="button" onClick={() => removeNorm(n.id)} aria-label={`Quitar ${n.nombre}`} className="shrink-0 text-slate-400 hover:text-red-600">
                  <Minus className="h-4 w-4" aria-hidden />
                </button>
              </li>
            ))}
            {asignadas.length === 0 && <li className="p-3 text-center text-xs text-slate-400">Sin normas asignadas todavía.</li>}
          </ul>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button onClick={handleGuardar}>Guardar asignación</Button>
        {saved && <span className="text-sm text-semaforo-cumple">Guardado.</span>}
      </div>
    </div>
  );
}
