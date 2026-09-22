'use client';

import { useState, type FormEvent } from 'react';
import { CheckSquare, Square } from 'lucide-react';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useNombreDeUsuario } from '@/lib/get-user-name';
import { usePersonasAsignables } from '@/lib/crm-etapas-store';
import { mensajeDeError } from '@/lib/api-client';
import { fechaCalendario } from '@/lib/fechas';
import { etiquetaDeEstado, useTareasDelPlan } from '@/lib/tareas-del-plan';

/**
 * Las tareas del plan (#169): marcar, y agregar con responsable y fecha.
 *
 * Una tarea que no está `todo` ni `done` (bloqueada, en revisión…) muestra su
 * estado y no una casilla: marcarla la pisaría con "hecha" sin que nadie haya
 * decidido desbloquearla.
 */
export function TareasDelPlanPanel({ planId }: { planId: string }) {
  const nombre = useNombreDeUsuario();
  const { personas } = usePersonasAsignables();
  const { tareas, errorDeCarga, errorDeEscritura, marcar, agregar } = useTareasDelPlan(planId);

  const [titulo, setTitulo] = useState('');
  const [responsableId, setResponsableId] = useState('');
  const [vence, setVence] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [errorAlta, setErrorAlta] = useState<string | null>(null);

  async function handleAgregar(e: FormEvent) {
    e.preventDefault();
    if (!titulo.trim()) {
      setErrorAlta('Escribe qué hay que hacer.');
      return;
    }
    setGuardando(true);
    setErrorAlta(null);
    try {
      await agregar({ titulo: titulo.trim(), responsableId: responsableId || null, vence: vence || null });
      setTitulo('');
      setResponsableId('');
      setVence('');
    } catch (err) {
      setErrorAlta(`No se agregó: ${mensajeDeError(err)}`);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="rounded-card border border-slate-200 bg-white p-6">
      <h2 className="mb-3 text-sm font-semibold text-slate-700">Tareas del plan</h2>

      {errorDeCarga ? (
        <p role="alert" className="text-sm text-semaforo-no-cumple">
          No se pudieron cargar las tareas: {errorDeCarga}
        </p>
      ) : tareas === null ? (
        <p className="text-sm text-slate-500">Cargando tareas…</p>
      ) : tareas.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">
          Este plan todavía no tiene tareas.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {tareas.map((t) => {
            const marcable = t.estado === 'todo' || t.estado === 'done';
            const hecha = t.estado === 'done';
            return (
              <li key={t.id} className="flex items-center gap-2 rounded-lg border border-slate-100 px-3 py-2 text-sm">
                {marcable ? (
                  <button
                    type="button"
                    onClick={() => void marcar(t, !hecha)}
                    aria-pressed={hecha}
                    aria-label={hecha ? `Reabrir «${t.titulo}»` : `Marcar «${t.titulo}» como hecha`}
                    className="shrink-0"
                  >
                    {hecha ? (
                      <CheckSquare className="h-4 w-4 text-brand-600" aria-hidden />
                    ) : (
                      <Square className="h-4 w-4 text-slate-400" aria-hidden />
                    )}
                  </button>
                ) : (
                  <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                    {etiquetaDeEstado(t.estado)}
                  </span>
                )}
                <span className={hecha ? 'flex-1 text-slate-400 line-through' : 'flex-1 text-slate-700'}>{t.titulo}</span>
                <span className="text-xs text-slate-500">
                  {nombre(t.responsableId)}
                  {t.vence ? ` · vence ${fechaCalendario(t.vence.slice(0, 10))}` : ''}
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {errorDeEscritura && <p role="alert" className="mt-2 text-sm text-semaforo-no-cumple">{errorDeEscritura}</p>}

      <form onSubmit={handleAgregar} className="mt-4 grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-[1fr_12rem_10rem_auto] sm:items-end" noValidate>
        <FormField label="Nueva tarea" htmlFor={`tarea-titulo-${planId}`} error={errorAlta ?? undefined}>
          <Input id={`tarea-titulo-${planId}`} value={titulo} onChange={(e) => setTitulo(e.target.value)} placeholder="Ej: instalar bandeja de contención" />
        </FormField>
        <FormField label="Responsable" htmlFor={`tarea-resp-${planId}`}>
          <select
            id={`tarea-resp-${planId}`}
            className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
            value={responsableId}
            onChange={(e) => setResponsableId(e.target.value)}
          >
            <option value="">Sin asignar</option>
            {personas.map((p) => (
              <option key={p.id} value={p.id}>{p.nombre}</option>
            ))}
          </select>
        </FormField>
        <FormField label="Vence" htmlFor={`tarea-vence-${planId}`}>
          <input
            id={`tarea-vence-${planId}`}
            type="date"
            className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
            value={vence}
            onChange={(e) => setVence(e.target.value)}
          />
        </FormField>
        <Button type="submit" disabled={guardando}>{guardando ? 'Agregando…' : 'Agregar'}</Button>
      </form>
    </div>
  );
}
