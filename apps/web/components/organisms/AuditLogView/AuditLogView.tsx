'use client';

import { useMemo, useState } from 'react';
import { ArrowRight, Download, History, ShieldCheck } from 'lucide-react';
import type { EntidadAuditable } from '@ambienta/shared';
import { ACCION_LABEL, ENTIDAD_LABEL } from '@ambienta/shared';
import { Button, Input } from '@/components/atoms';
import { EmptyState, FormField } from '@/components/molecules';
import { useAuditLog } from '@/lib/audit-log-store';
import {
  actoresDe,
  exportarAuditoriaCsv,
  filtrarAuditoria,
  FILTROS_INICIALES,
  type FiltrosAuditoria,
} from '@/lib/audit-log-filters';
import { downloadTextFile } from '@/lib/reports';
import { useToast } from '@/lib/toast-store';
import { ROLE_LABEL } from '@/lib/roles';
import type { Role } from '@ambienta/shared';

const ENTIDADES: EntidadAuditable[] = [
  'ticket_soporte',
  'obligacion',
  'tarea',
  'norma',
  'articulo',
  'no_conformidad',
  'plan_accion',
  'usuario',
  'tenant',
  'contrato',
  'departamento',
  'planta',
];

/**
 * Historial consolidado del sistema (RF-32, RNF-25, RNF-26).
 *
 * Complementa al `HistorialTimeline` de cada entidad: ese responde "qué pasó
 * con esta norma", este responde "qué pasó en la empresa en marzo" o "qué hizo
 * este usuario" — que es la forma que toma una auditoría real, cruzando
 * entidades.
 *
 * `tenantIdVisible` decide el alcance y no es negociable: los roles de tenant
 * ven solo su empresa, el Superadmin solo la actividad de plataforma. En el
 * backend lo garantiza RLS.
 */
export function AuditLogView({ tenantIdVisible }: { tenantIdVisible: string | null }) {
  const { entries } = useAuditLog();
  const { mostrarToast } = useToast();
  const [filtros, setFiltros] = useState<FiltrosAuditoria>(FILTROS_INICIALES);

  const delAlcance = useMemo(
    () => filtrarAuditoria(entries, tenantIdVisible, FILTROS_INICIALES),
    [entries, tenantIdVisible],
  );
  const filtrados = useMemo(
    () => filtrarAuditoria(entries, tenantIdVisible, filtros),
    [entries, tenantIdVisible, filtros],
  );
  const actores = useMemo(() => actoresDe(delAlcance), [delAlcance]);

  const hayFiltros = JSON.stringify(filtros) !== JSON.stringify(FILTROS_INICIALES);

  function handleExportar() {
    if (filtrados.length === 0) return;
    downloadTextFile(
      `historial-ambienta-${new Date().toISOString().slice(0, 10)}.csv`,
      exportarAuditoriaCsv(filtrados),
      'text/csv;charset=utf-8',
    );
    mostrarToast({
      tipo: 'exito',
      mensaje: `${filtrados.length} evento(s) exportado(s)`,
      descripcion: 'El archivo incluye solo lo que estás viendo con los filtros actuales.',
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-card border border-slate-200 bg-white p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <FormField label="Buscar" htmlFor="audit-texto">
            <Input
              id="audit-texto"
              value={filtros.texto}
              onChange={(e) => setFiltros((f) => ({ ...f, texto: e.target.value }))}
              placeholder="Entidad, persona o motivo"
            />
          </FormField>

          <FormField label="Tipo" htmlFor="audit-entidad">
            <select
              id="audit-entidad"
              className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              value={filtros.entidadTipo}
              onChange={(e) => setFiltros((f) => ({ ...f, entidadTipo: e.target.value as FiltrosAuditoria['entidadTipo'] }))}
            >
              <option value="todas">Todos los tipos</option>
              {ENTIDADES.map((ent) => (
                <option key={ent} value={ent}>
                  {ENTIDAD_LABEL[ent]}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label="Persona" htmlFor="audit-actor">
            <select
              id="audit-actor"
              className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              value={filtros.actorId}
              onChange={(e) => setFiltros((f) => ({ ...f, actorId: e.target.value }))}
            >
              <option value="todos">Todas las personas</option>
              {actores.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.nombre}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label="Desde" htmlFor="audit-desde">
            <Input
              id="audit-desde"
              type="date"
              value={filtros.desde}
              onChange={(e) => setFiltros((f) => ({ ...f, desde: e.target.value }))}
            />
          </FormField>

          <FormField label="Hasta" htmlFor="audit-hasta">
            <Input
              id="audit-hasta"
              type="date"
              value={filtros.hasta}
              onChange={(e) => setFiltros((f) => ({ ...f, hasta: e.target.value }))}
            />
          </FormField>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3">
          <p className="text-xs text-slate-500">
            {filtrados.length} de {delAlcance.length} evento(s)
            {hayFiltros && (
              <button
                type="button"
                onClick={() => setFiltros(FILTROS_INICIALES)}
                className="ml-2 font-medium text-brand-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              >
                Limpiar filtros
              </button>
            )}
          </p>
          <Button
            variant="secondary"
            size="md"
            onClick={handleExportar}
            disabled={filtrados.length === 0}
            icon={<Download className="h-4 w-4" aria-hidden />}
          >
            Exportar CSV
          </Button>
        </div>
      </div>

      {filtrados.length === 0 ? (
        <EmptyState
          icono={History}
          titulo={hayFiltros ? 'Sin resultados para estos filtros' : 'Todavía no hay actividad registrada'}
          descripcion={
            hayFiltros
              ? 'Prueba ampliando el rango de fechas o quitando algún filtro.'
              : 'Cada acción sobre el sistema quedará aquí con su autor, fecha y motivo.'
          }
          accion={
            hayFiltros ? (
              <Button variant="secondary" size="md" onClick={() => setFiltros(FILTROS_INICIALES)}>
                Limpiar filtros
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
          <table className="w-full min-w-[720px] text-sm">
            <caption className="sr-only">Historial de acciones del sistema</caption>
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                <th scope="col" className="px-4 py-3">Fecha</th>
                <th scope="col" className="px-4 py-3">Quién</th>
                <th scope="col" className="px-4 py-3">Qué</th>
                <th scope="col" className="px-4 py-3">Sobre</th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map((e) => (
                <tr key={e.id} className="border-b border-slate-100 align-top last:border-0 hover:bg-slate-50">
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
                    <time dateTime={e.fecha}>
                      {new Date(e.fecha).toLocaleString('es-CL', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </time>
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-800">{e.actorNombre}</p>
                    <p className="text-xs text-slate-500">{ROLE_LABEL[e.actorRol as Role] ?? e.actorRol}</p>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-slate-700">{e.resumen}</p>
                    {e.cambios.length > 0 && (
                      <ul className="mt-1 flex flex-col gap-0.5">
                        {e.cambios.map((c, i) => (
                          <li key={`${c.campo}-${i}`} className="flex flex-wrap items-center gap-1 text-xs text-slate-500">
                            <span className="font-medium">{c.campo}:</span>
                            <span className="line-through decoration-slate-400">{c.antes ?? 'vacío'}</span>
                            <ArrowRight className="h-3 w-3" aria-hidden />
                            <span className="font-medium text-semaforo-cumple">{c.despues ?? 'vacío'}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                    {e.motivo && <p className="mt-1 text-xs italic text-slate-500">{e.motivo}</p>}
                    {e.aprobadoPorNombre && (
                      <p className="mt-1 flex items-center gap-1 text-xs font-medium text-semaforo-cumple">
                        <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
                        Aprobado por {e.aprobadoPorNombre}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
                      {ENTIDAD_LABEL[e.entidadTipo]}
                    </span>
                    <p className="mt-1 text-xs text-slate-600">{e.entidadLabel}</p>
                    <p className="mt-0.5 text-[10px] uppercase tracking-wide text-slate-400">{ACCION_LABEL[e.accion]}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
