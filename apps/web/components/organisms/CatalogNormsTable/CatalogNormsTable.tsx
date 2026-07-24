'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Inbox, RefreshCw, Search } from 'lucide-react';
import { Button, Input, StatusBadge } from '@/components/atoms';
import { FilterBar } from '@/components/molecules';
import { syncSemaforo, SYNC_LABEL, FUENTE_LABEL } from '@/lib/catalog-status';
import type { CatalogNormsTableProps } from './CatalogNormsTable.types';

/** S-25 Catálogo Normativo (3 capas): búsqueda, filtros, estado de sincronización, panel Superadmin. */
export function CatalogNormsTable({ norms, tenantPlantIds, isSuperadmin, isAdminEmpresa, onMarcarAplicable }: CatalogNormsTableProps) {
  const [busqueda, setBusqueda] = useState('');
  const [fuenteFiltro, setFuenteFiltro] = useState('todos');

  const filtered = useMemo(
    () =>
      norms.filter((n) => {
        if (fuenteFiltro !== 'todos' && n.fuente !== fuenteFiltro) return false;
        if (busqueda.trim() && !n.nombre.toLowerCase().includes(busqueda.trim().toLowerCase())) return false;
        return true;
      }),
    [norms, fuenteFiltro, busqueda],
  );

  const bcnDesactualizadas = norms.filter((n) => n.fuente === 'BCN' && n.sincronizacion?.estado !== 'sincronizado').length;

  return (
    <div className="flex flex-col gap-4">
      {isSuperadmin && (
        <div className="flex items-center justify-between rounded-card border border-slate-200 bg-white p-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-700">Salud del agente BCN</h2>
            <p className="text-xs text-slate-500">
              {bcnDesactualizadas === 0 ? 'Todas las normas públicas están sincronizadas.' : `${bcnDesactualizadas} norma(s) pública(s) desactualizada(s) o con error.`}
            </p>
          </div>
          <Button
            variant="secondary"
            disabled
            title="Requiere apps/ai-service (RF-45) — sin spec de API aprobada"
            icon={<RefreshCw className="h-4 w-4" aria-hidden />}
          >
            Forzar sincronización
          </Button>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
          Buscar
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
            <Input className="pl-9" placeholder="Nombre de la norma" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
          </div>
        </label>
        <FilterBar
          filters={[
            {
              id: 'filtro-fuente-catalogo',
              label: 'Tipo',
              value: fuenteFiltro,
              onChange: setFuenteFiltro,
              options: [
                { value: 'todos', label: 'Todos los tipos' },
                { value: 'BCN', label: 'Pública (BCN)' },
                { value: 'ISO', label: 'ISO interna' },
                { value: 'RCA', label: 'RCA del tenant' },
              ],
            },
          ]}
        />
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
          <Inbox className="h-6 w-6 text-slate-400" aria-hidden />
          No hay normas que coincidan con la búsqueda o filtros.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
          <table className="w-full min-w-[760px] text-sm">
            <caption className="sr-only">Catálogo normativo</caption>
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                <th scope="col" className="px-4 py-3">Norma</th>
                <th scope="col" className="px-4 py-3">Tipo</th>
                <th scope="col" className="px-4 py-3">Sincronización</th>
                {isAdminEmpresa && <th scope="col" className="px-4 py-3">Aplicable a mi planta</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.map((n) => {
                const yaAplicada = n.plantIds.some((id) => tenantPlantIds.includes(id));
                return (
                  <tr key={n.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium text-slate-800">
                      <Link href={`/matriz-legal/${n.id}`} className="hover:underline">
                        {n.nombre}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{FUENTE_LABEL[n.fuente]}</td>
                    <td className="px-4 py-3">
                      {n.sincronizacion ? (
                        <>
                          <StatusBadge status={syncSemaforo(n.sincronizacion.estado)} />
                          <span className="ml-2 text-xs text-slate-500">{SYNC_LABEL[n.sincronizacion.estado]}</span>
                        </>
                      ) : (
                        <span className="text-slate-400">No aplica</span>
                      )}
                    </td>
                    {isAdminEmpresa && (
                      <td className="px-4 py-3">
                        {yaAplicada ? (
                          <span className="text-xs font-medium text-semaforo-cumple">Ya aplicada</span>
                        ) : (
                          <Button variant="secondary" size="md" onClick={() => onMarcarAplicable(n.id)}>
                            Marcar como aplicable
                          </Button>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
