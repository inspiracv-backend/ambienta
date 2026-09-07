'use client';

import { useId, useState, type FormEvent } from 'react';
import Link from 'next/link';
import * as Dialog from '@radix-ui/react-dialog';
import { CalendarDays, Check, ExternalLink, Plus, Scale, Undo2, X } from 'lucide-react';
import type { ObligationTask } from '@ambienta/shared';
import { Button, Input, StatusBadge } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { TaskDetailModal } from '@/components/organisms/TaskDetailModal';
import { mensajeDeError } from '@/lib/api-client';
import { getUserName } from '@/lib/get-user-name';
import { useObligations } from '@/lib/obligations-store';
import { usarPresentaciones } from '@/lib/usar-presentaciones';
import { usarDocumentosVinculados } from '@/lib/usar-documentos-vinculados';
import { HiloDeComentarios } from '@/components/molecules/HiloDeComentarios';
import type { ObligationDetailViewProps } from './ObligationDetailView.types';

/**
 * El estado de una presentacion, traducido al semaforo compartido.
 *
 * **Manda la base**, igual que en `lib/iso-vocabulario.ts`: el CHECK de
 * `declaration_submissions.status` admite siete valores y este mapa cubre los
 * que el flujo produce hoy. Lo que no reconoce cae en `parcial` y **se muestra
 * crudo** en la etiqueta, en vez de esconderse tras un guion: un valor feo se
 * arregla, uno escondido no.
 */
const ESTADO_DE_PRESENTACION: Record<string, 'cumple' | 'parcial' | 'no_cumple'> = {
  submitted: 'parcial',
  accepted: 'cumple',
  rejected: 'no_cumple',
  rectified: 'parcial',
  draft: 'parcial',
  ready: 'parcial',
  validation_error: 'no_cumple',
};

const ETIQUETA_DE_PRESENTACION: Record<string, string> = {
  submitted: 'Presentada',
  accepted: 'Aceptada',
  rejected: 'Rechazada',
  rectified: 'Rectificada',
  draft: 'Borrador',
  ready: 'Lista',
  validation_error: 'Con errores',
};

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

/** S-14 Detalle de Obligación (Megaproyecto). */
export function ObligationDetailView({ obligation: obligationProp, responsableOptions }: ObligationDetailViewProps) {
  const { obligations, addTask, moverDeclaracion } = useObligations();
  const obligation = obligations.find((o) => o.id === obligationProp.id) ?? obligationProp;

  const [editingTask, setEditingTask] = useState<ObligationTask | null>(null);
  const [isAddTaskOpen, setIsAddTaskOpen] = useState(false);
  const formId = useId();
  const [titulo, setTitulo] = useState('');
  const [vencimiento, setVencimiento] = useState('');
  const [responsableId, setResponsableId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [errorFlujo, setErrorFlujo] = useState<string | null>(null);
  const [enCurso, setEnCurso] = useState(false);
  const [folio, setFolio] = useState('');
  const [motivo, setMotivo] = useState('');
  // Se revalida con el estado y el folio: presentar agrega una fila,
  // aceptar y rechazar cierran la ultima. Sin esto la pantalla mostraria
  // el historial de antes de la accion que el usuario acaba de hacer.
  const { documentos, error: errorRespaldo } = usarDocumentosVinculados(
    'obligation',
    obligation.id,
  );
  const { presentaciones, error: errorHistorial } = usarPresentaciones(
    obligation.id,
    `${obligation.estado}|${obligation.folio ?? ''}`,
  );
  const today = new Date().toISOString().slice(0, 10);

  /**
   * Mueve la declaracion y **muestra el error del servidor tal cual**.
   *
   * Los 409 de este flujo dicen exactamente que falta —"hace falta el folio
   * que devolvio el sistema oficial", "una declaracion en 'draft' no puede
   * pasar a 'accepted'"— y son mas utiles que cualquier frase generica que se
   * escriba aca. Taparlos con "no se pudo guardar" obliga a la persona a
   * adivinar, que es justo lo que el mensaje evita.
   */
  async function mover(
    accion: 'submit' | 'approve' | 'reject' | 'fulfill',
    datos: { folio?: string; motivo?: string } = {},
  ) {
    setEnCurso(true);
    setErrorFlujo(null);
    try {
      await moverDeclaracion(obligation.id, accion, datos);
      setFolio('');
      setMotivo('');
    } catch (e) {
      setErrorFlujo(mensajeDeError(e));
    } finally {
      setEnCurso(false);
    }
  }

  function handleAddTask(e: FormEvent) {
    e.preventDefault();
    if (!titulo.trim() || !vencimiento) {
      setError('Completa el título y la fecha de vencimiento.');
      return;
    }
    if (vencimiento < today) {
      setError('La fecha no puede ser anterior a hoy.');
      return;
    }
    addTask(obligation.id, { titulo: titulo.trim(), vencimiento: new Date(vencimiento).toISOString(), responsableId });
    setTitulo('');
    setVencimiento('');
    setResponsableId('');
    setError(null);
    setIsAddTaskOpen(false);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
              {obligation.sistema} · {obligation.periodo}
            </span>
            <h1 className="mt-1 text-xl font-semibold text-slate-900">{obligation.nombre}</h1>
            <p className="mt-1 text-sm text-slate-500">Vence {formatFecha(obligation.proximoVencimiento)}</p>
          </div>
          <StatusBadge status={obligation.estado} />
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button size="md" icon={<Plus className="h-4 w-4" aria-hidden />} onClick={() => setIsAddTaskOpen(true)}>
            Agregar tarea
          </Button>
          <Link
            href="/calendario"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <CalendarDays className="h-4 w-4" aria-hidden />
            Ver en Calendario/Gantt
          </Link>
          {/* Estuvo como chip muerto ("Vincular a Matriz Legal — Proximamente")
              mientras el vinculo no estaba definido (#110). Ya lo esta: se
              cuelga de la evaluacion del articulo, y el sentido matriz →
              obligacion se dispara desde el dialogo de evaluar. Aca se muestra
              el sentido inverso — de donde vino esta obligacion.

              Cuando no viene de la matriz **no se muestra nada**: un control
              deshabilitado permanente es ruido, y "nacio libremente" es un
              estado legitimo que RF-14 contempla, no una carencia. */}
          {obligation.sistemaUrl && (
            <a
              href={obligation.sistemaUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <ExternalLink className="h-4 w-4" aria-hidden />
              Ir al sistema oficial
            </a>
          )}

          {obligation.normaOrigenId && (
            <Link
              href={`/matriz-legal/${obligation.normaOrigenId}`}
              className="inline-flex items-center gap-1.5 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-sm font-medium text-brand-700 hover:bg-brand-100"
            >
              <Scale className="h-4 w-4" aria-hidden />
              Ver el artículo de la Matriz Legal que la origina
            </Link>
          )}
        </div>
      </div>

      {/* El flujo de RF-31 (#115) y el folio del portal (#114).
          Estuvieron sin pantalla mientras la API tenia `submit` a medias y un
          `fulfill` que respondia 422 siempre. */}
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="text-sm font-semibold text-slate-900">Presentacion ante el sistema oficial</h2>
        <p className="mt-0.5 text-sm text-slate-500">
          El folio es el comprobante que devuelve el portal.{' '}
          <span className="font-medium text-slate-600">Sin el no se puede aceptar la declaracion</span>:
          es la unica prueba de que se presento.
        </p>

        <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Folio registrado</dt>
            <dd className="font-medium text-slate-800">
              {obligation.folio || <span className="font-normal text-slate-400">Todavia ninguno</span>}
            </dd>
          </div>
          {obligation.motivoRechazo && (
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Motivo del ultimo rechazo</dt>
              <dd className="font-medium text-semaforo-no-cumple">{obligation.motivoRechazo}</dd>
            </div>
          )}
        </dl>

        <div className="mt-4 flex flex-wrap items-end gap-3">
          <FormField label="Folio del sistema oficial" htmlFor={`${formId}-folio`}>
            <Input
              id={`${formId}-folio`}
              value={folio}
              onChange={(e) => setFolio(e.target.value)}
              placeholder="Ej: SIDREP-2026-99812"
            />
          </FormField>
          <Button
            variant="secondary"
            type="button"
            disabled={enCurso || !folio.trim()}
            onClick={() => mover('fulfill', { folio: folio.trim() })}
          >
            Registrar folio
          </Button>
        </div>

        <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
          <Button type="button" disabled={enCurso} onClick={() => mover('submit')}>
            Marcar como presentada
          </Button>
          <Button
            variant="secondary"
            type="button"
            disabled={enCurso}
            icon={<Check className="h-4 w-4" aria-hidden />}
            onClick={() => mover('approve', folio.trim() ? { folio: folio.trim() } : {})}
          >
            Aceptar
          </Button>
          <Button
            variant="secondary"
            type="button"
            disabled={enCurso || !motivo.trim()}
            icon={<Undo2 className="h-4 w-4" aria-hidden />}
            onClick={() => mover('reject', { motivo: motivo.trim() })}
          >
            Rechazar
          </Button>
          <Input
            aria-label="Motivo del rechazo"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Motivo del rechazo (obligatorio para rechazar)"
            className="min-w-[18rem] flex-1"
          />
        </div>

        {errorFlujo && (
          <p role="alert" className="mt-3 rounded-lg bg-semaforo-no-cumple-bg px-3 py-2 text-sm text-semaforo-no-cumple">
            {errorFlujo}
          </p>
        )}
      </div>

      {/* El historial de presentaciones (#21).

          La obligacion guarda **un solo** folio: el ultimo. Una declaracion
          rechazada y vuelta a presentar produce dos, y con una sola columna el
          primero se pierde al escribir el segundo — sin ningun error. Y el
          folio es lo unico que la empresa puede mostrarle a un fiscalizador
          para sostener que declaro. */}
      {/* La conversacion sobre esta declaracion (RF-111, #74).

          El cliente lo nombro directo: la informacion se maneja por correo y se
          pierde. Lo que se pierde no es el dato —ese esta en la base— sino **por
          que se decidio lo que se decidio**: quien dijo que la evidencia servia,
          que se acordo cuando el plazo se corrio. */}
      <HiloDeComentarios entityType="obligation" entityId={obligation.id} />

      {/* El respaldo documental (RF-108, #73).

          La pregunta de un fiscalizador tiene esta forma: senala un requisito y
          pide la evidencia. Hasta hoy `entity_documents` existia con CRUD
          completo, cero filas y **ningun archivo del frontend que la nombrara**,
          y solo se podia consultar al reves — desde el documento hacia lo que
          respalda, que no contesta esa pregunta. */}
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-sm font-semibold text-slate-900">Respaldo documental</h2>
          {/* **El contador no se dibuja mientras no se sabe.** Un «0» junto al
              titulo es la afirmacion mas fuerte del panel: dice que este
              requisito no tiene con que sostenerse. */}
          {documentos !== null && !errorRespaldo && (
            <span className="text-xs tabular-nums text-slate-500">
              {documentos.length} {documentos.length === 1 ? 'documento' : 'documentos'}
            </span>
          )}
        </div>

        {errorRespaldo ? (
          <p role="alert" className="mt-4 text-sm text-semaforo-no-cumple">
            No se pudo consultar el respaldo: {errorRespaldo}
          </p>
        ) : documentos === null ? (
          <p role="status" className="mt-4 text-sm text-slate-400">
            Comprobando…
          </p>
        ) : documentos.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">
            Ningun documento controlado respalda esta declaracion todavia.
          </p>
        ) : (
          <ul className="mt-4 flex flex-col divide-y divide-slate-100">
            {documentos.map((d) => (
              <li key={d.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-3 first:pt-0 last:pb-0">
                {/* El codigo primero: es lo que se cita en una auditoria. */}
                <span className="font-medium text-slate-900">{d.codigo ?? 'Sin codigo'}</span>
                <span className="text-slate-700">{d.titulo}</span>
                <span className="text-xs uppercase tracking-wide text-slate-400">{d.tipo}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="text-sm font-semibold text-slate-900">Historial de presentaciones</h2>
        <p className="mt-0.5 text-sm text-slate-500">
          Cada intento con su propio folio, del mas reciente al primero.
        </p>

        {errorHistorial ? (
          <p role="alert" className="mt-4 text-sm text-semaforo-no-cumple">
            No se pudo consultar el historial: {errorHistorial}
          </p>
        ) : presentaciones === null ? (
          <p role="status" className="mt-4 text-sm text-slate-400">
            Comprobando…
          </p>
        ) : presentaciones.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">
            {/*
              **El caso incomodo, y hay que decirlo.** Una declaracion ya
              aceptada con el historial vacio parece perdida de datos, y no lo
              es: las que se presentaron antes de que existiera este registro no
              tienen filas. Fabricarselas seria inventar una fecha, una version
              y un autor — los tres falsos, y justo el dato que se discute ante
              un fiscalizador.
            */}
            {['draft', 'open', 'in_progress'].includes(obligation.estadoDeclaracion ?? 'draft') ? (
              'Todavia no se ha presentado.'
            ) : (
              <>
                Sin presentaciones registradas.{' '}
                <span className="text-slate-400">
                  Esta declaracion se presento antes de que el sistema llevara
                  este historial, asi que no hay filas anteriores. El folio de
                  arriba sigue siendo valido.
                </span>
              </>
            )}
          </p>
        ) : (
          <ol className="mt-4 flex flex-col divide-y divide-slate-100">
            {presentaciones.map((p) => (
              <li key={p.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-3 first:pt-0 last:pb-0">
                <span className="font-medium tabular-nums text-slate-900">v{p.versionNo}</span>
                <StatusBadge
                  status={ESTADO_DE_PRESENTACION[p.estado] ?? 'parcial'}
                  label={ETIQUETA_DE_PRESENTACION[p.estado] ?? p.estado}
                />
                {p.presentadaEl && (
                  <span className="text-slate-500">{formatFecha(p.presentadaEl)}</span>
                )}
                <span className="text-slate-700">
                  {/*
                    Un intento sin folio no es un error: se presento y el portal
                    todavia no respondio. Decirlo asi evita que se lea como un
                    dato que se perdio.
                  */}
                  {p.folio ? (
                    <>Folio <span className="font-medium">{p.folio}</span></>
                  ) : (
                    <span className="text-slate-400">Sin folio todavia</span>
                  )}
                </span>
                {p.motivoRechazo && (
                  <span className="w-full text-semaforo-no-cumple">
                    Rechazada: {p.motivoRechazo}
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
        <table className="w-full min-w-[680px] text-sm">
          <caption className="sr-only">Tareas y subtareas de {obligation.nombre}</caption>
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
              <th scope="col" className="px-4 py-3">Tarea</th>
              <th scope="col" className="px-4 py-3">Vencimiento</th>
              <th scope="col" className="px-4 py-3">Responsable</th>
              <th scope="col" className="px-4 py-3">Estado</th>
              <th scope="col" className="px-4 py-3">Evidencia</th>
              <th scope="col" className="px-4 py-3">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {obligation.tasks.map((task) => (
              <tr key={task.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-800">{task.titulo}</td>
                <td className="px-4 py-3 text-slate-500">{formatFecha(task.vencimiento)}</td>
                <td className="px-4 py-3 text-slate-500">{getUserName(task.responsableId)}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={task.estado} />
                </td>
                <td className="px-4 py-3">
                  {task.evidenciaUrl ? (
                    <a href={task.evidenciaUrl} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">
                      Ver evidencia
                    </a>
                  ) : (
                    <span className="text-slate-400">Sin evidencia</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <Button variant="ghost" size="md" onClick={() => setEditingTask(task)}>
                    Editar
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <TaskDetailModal
        task={editingTask}
        obligationId={obligation.id}
        obligationNombre={obligation.nombre}
        tenantId={obligation.tenantId}
        responsableOptions={responsableOptions}
        onOpenChange={(open) => !open && setEditingTask(null)}
      />

      <Dialog.Root open={isAddTaskOpen} onOpenChange={setIsAddTaskOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-6 shadow-lg">
            <div className="flex items-start justify-between">
              <Dialog.Title className="text-lg font-semibold text-slate-900">Agregar tarea</Dialog.Title>
              <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
                <X className="h-5 w-5" aria-hidden />
              </Dialog.Close>
            </div>
            <form onSubmit={handleAddTask} className="mt-4 flex flex-col gap-4" noValidate>
              <FormField label="Título" htmlFor={`${formId}-titulo`} required error={error ?? undefined}>
                <Input id={`${formId}-titulo`} value={titulo} invalid={!!error} onChange={(e) => setTitulo(e.target.value)} />
              </FormField>
              <FormField label="Vencimiento" htmlFor={`${formId}-vencimiento`} required>
                <Input id={`${formId}-vencimiento`} type="date" min={today} value={vencimiento} onChange={(e) => setVencimiento(e.target.value)} />
              </FormField>
              <FormField label="Responsable" htmlFor={`${formId}-responsable`}>
                <select
                  id={`${formId}-responsable`}
                  className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
                  value={responsableId}
                  onChange={(e) => setResponsableId(e.target.value)}
                >
                  <option value="">Sin asignar</option>
                  {responsableOptions.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.nombre}
                    </option>
                  ))}
                </select>
              </FormField>
              <div className="mt-2 flex justify-end gap-2">
                <Dialog.Close asChild>
                  <Button type="button" variant="secondary">Cancelar</Button>
                </Dialog.Close>
                <Button type="submit">Agregar</Button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
