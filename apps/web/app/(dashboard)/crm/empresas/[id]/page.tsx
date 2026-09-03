'use client';

import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  Handshake,
  Mail,
  Phone,
  Plus,
  RefreshCw,
  Star,
} from 'lucide-react';
import { Button, Input, Spinner, StatusBadge, Textarea } from '@/components/atoms';
import type { SemaforoStatus } from '@/components/atoms/StatusBadge/StatusBadge.types';
import { Breadcrumbs, EmptyState, PageHeader } from '@/components/molecules';
import {
  ContactoCrmModal,
  MoverTratoModal,
  PromoverTratoModal,
  RegistrarActividadCrm,
  TratoCrmModal,
} from '@/components/organisms';
import {
  ESTADO_DE_EMPRESA,
  TIPO_DE_ACTIVIDAD,
  formatearFecha,
  formatearMonto,
  motivoParaNoPromover,
  nombreDelResponsable,
  sePuedePromover,
  type ContactoCrm,
  type EstadoDeEmpresa,
  type TratoCrm,
} from '@/lib/crm';
import { useFichaDeEmpresa } from '@/lib/crm-empresas-store';
import { usePersonasAsignables } from '@/lib/crm-etapas-store';

/**
 * La ficha de una empresa del CRM: contactos, oportunidades y línea de tiempo.
 *
 * ## Por qué existe
 *
 * El CRM tenía **una** pantalla —el kanban, que llamaba a dos de las 28
 * operaciones de la API—, y con eso el módulo no se podía usar. No se
 * podía registrar un contacto, anotar una llamada, crear una oportunidad ni
 * promover una ganada al contrato que la materializó. El módulo estaba completo
 * por API e inutilizable como producto.
 *
 * ## Todo lo de una empresa en un solo sitio
 *
 * Las cuatro cosas se miran juntas: quien va a llamar quiere el teléfono, lo
 * último que se habló y en qué quedó la propuesta. Repartirlo en pestañas
 * obligaría a recordar entre una y otra.
 *
 * ## Cada sección dice si su dato falló
 *
 * Un fallo en contactos no vacía los tratos, y una sección que no cargó lo
 * **dice** en vez de mostrarse vacía: una lista vacía afirma que no hay nada,
 * y en una ficha comercial esa afirmación lleva a no llamar a alguien.
 */

const COLOR_DEL_ESTADO: Record<EstadoDeEmpresa, SemaforoStatus> = {
  client: 'cumple',
  prospect: 'pendiente',
  inactive: 'na',
};

export default function FichaDeEmpresaPage({ params }: { params: { id: string } }) {
  const {
    empresa,
    contactos,
    tratos,
    etapas,
    actividades,
    listasCortadas,
    cargando,
    errores,
    agregarContacto,
    editarContacto,
    registrarActividad,
    crearTrato,
    editarTrato,
    moverTrato,
    editarActividad,
    retirar,
    promover,
    recargar,
  } = useFichaDeEmpresa(params.id);
  const { personas } = usePersonasAsignables();

  const [contactoEnEdicion, setContactoEnEdicion] = useState<ContactoCrm | null>(null);
  const [modalContacto, setModalContacto] = useState(false);
  const [tratoEnEdicion, setTratoEnEdicion] = useState<TratoCrm | null>(null);
  const [modalTrato, setModalTrato] = useState(false);
  const [tratoAMover, setTratoAMover] = useState<TratoCrm | null>(null);
  const [tratoAPromover, setTratoAPromover] = useState<TratoCrm | null>(null);
  const [efectos, setEfectos] = useState<string[]>([]);
  const [actividadEnEdicion, setActividadEnEdicion] = useState<string | null>(null);
  const [errorDeAccion, setErrorDeAccion] = useState<string | null>(null);

  /** Retira y **dice si no pudo**. Sin esto, una acción rechazada dejaría la
   *  fila en pantalla y quien la pidió creería que se hizo. */
  async function retirarCon(
    que: 'contacts' | 'deals' | 'activities',
    id: string,
    queEs: string,
  ) {
    if (!window.confirm(`¿Retirar ${queEs}? Deja de aparecer, y su historial se conserva.`)) {
      return;
    }
    const r = await retirar(que, id);
    setErrorDeAccion(r.ok ? null : (r.error ?? 'No se pudo retirar.'));
  }

  const etapaDe = useMemo(() => {
    const porId = new Map(etapas.map((e) => [e.id, e]));
    return (trato: TratoCrm) => porId.get(trato.etapaId) ?? null;
  }, [etapas]);

  if (cargando) {
    return (
      <p className="flex items-center gap-2 text-sm text-slate-500">
        <Spinner className="h-4 w-4" />
        Cargando la ficha…
      </p>
    );
  }

  if (!empresa) {
    return (
      <div className="flex flex-col gap-4">
        <Breadcrumbs items={[{ label: 'Empresas', href: '/crm/empresas' }, { label: 'Ficha' }]} />
        <div className="rounded-card border border-semaforo-incumple/30 bg-semaforo-incumple-bg p-4">
          <p className="flex items-center gap-2 text-sm font-medium text-semaforo-incumple">
            <AlertTriangle className="h-4 w-4" aria-hidden />
            No se pudo abrir esta ficha.
          </p>
          <p className="mt-1 text-sm text-slate-600">
            {errores.empresa ?? 'La empresa no existe o no es de esta cuenta.'}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => void recargar()}>
            Reintentar
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <Breadcrumbs
        items={[{ label: 'Empresas', href: '/crm/empresas' }, { label: empresa.nombre }]}
      />

      <PageHeader
        titulo={empresa.nombre}
        descripcion={[empresa.rut, empresa.rubro].filter(Boolean).join(' · ') || 'Sin RUT ni rubro registrados.'}
        acciones={
          <Button
            variant="secondary"
            icon={<RefreshCw className="h-4 w-4" aria-hidden />}
            onClick={() => void recargar()}
          >
            Actualizar
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="inline-flex items-center gap-1.5">
          <StatusBadge status={COLOR_DEL_ESTADO[empresa.estado]} />
          <span className="text-slate-600">{ESTADO_DE_EMPRESA[empresa.estado]}</span>
        </span>
        <span className="text-slate-600">
          {nombreDelResponsable(empresa.responsableId, personas)}
        </span>
        {empresa.sitioWeb && (
          <a
            href={empresa.sitioWeb}
            target="_blank"
            rel="noreferrer noopener"
            className="text-brand-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            {empresa.sitioWeb}
          </a>
        )}
      </div>

      {empresa.notas && (
        <p className="whitespace-pre-line rounded-card border border-slate-200 bg-white p-4 text-sm text-slate-600">
          {empresa.notas}
        </p>
      )}

      {listasCortadas.length > 0 && (
        <p className="rounded-card border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          La API cortó la lista de {listasCortadas.join(' y ')} en su tope, así que
          esta ficha podría no mostrarlos todos.
        </p>
      )}

      {errorDeAccion && (
        <p
          role="alert"
          className="rounded-card border border-semaforo-incumple/30 bg-semaforo-incumple-bg px-3 py-2 text-sm text-semaforo-incumple"
        >
          {errorDeAccion}
        </p>
      )}

      {efectos.length > 0 && (
        <ul className="rounded-card border border-semaforo-cumple/30 bg-semaforo-cumple-bg px-4 py-3 text-sm text-slate-700">
          {efectos.map((e) => (
            <li key={e}>· {e}</li>
          ))}
        </ul>
      )}

      {/* ── Contactos ─────────────────────────────────────────────────── */}
      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900">Contactos</h2>
          <Button
            variant="secondary"
            icon={<Plus className="h-4 w-4" aria-hidden />}
            onClick={() => {
              setContactoEnEdicion(null);
              setModalContacto(true);
            }}
          >
            Nuevo contacto
          </Button>
        </div>

        {errores.contactos ? (
          <p role="alert" className="rounded-card border border-semaforo-incumple/30 bg-semaforo-incumple-bg px-3 py-2 text-sm text-semaforo-incumple">
            No se pudieron traer los contactos: {errores.contactos}
          </p>
        ) : contactos.length === 0 ? (
          <p className="rounded-card border border-slate-200 bg-white px-3 py-3 text-sm text-slate-500">
            Todavía no hay contactos registrados en esta empresa.
          </p>
        ) : (
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {contactos.map((c) => (
              <li key={c.id} className="rounded-card border border-slate-200 bg-white p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="flex items-center gap-1.5 font-medium text-slate-900">
                      {c.nombre}
                      {c.esPrincipal && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                          <Star className="h-3 w-3" aria-hidden />
                          Principal
                        </span>
                      )}
                    </p>
                    {c.cargo && <p className="text-xs text-slate-500">{c.cargo}</p>}
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setContactoEnEdicion(c);
                        setModalContacto(true);
                      }}
                    >
                      Editar
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => void retirarCon('contacts', c.id, `a ${c.nombre}`)}
                    >
                      Retirar
                    </Button>
                  </div>
                </div>
                <div className="mt-2 flex flex-col gap-1 text-sm text-slate-600">
                  {c.correo && (
                    <a href={`mailto:${c.correo}`} className="flex items-center gap-1.5 hover:underline">
                      <Mail className="h-3.5 w-3.5" aria-hidden />
                      {c.correo}
                    </a>
                  )}
                  {c.telefono && (
                    <a href={`tel:${c.telefono}`} className="flex items-center gap-1.5 hover:underline">
                      <Phone className="h-3.5 w-3.5" aria-hidden />
                      {c.telefono}
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ── Oportunidades ─────────────────────────────────────────────── */}
      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900">Oportunidades</h2>
          <Button
            variant="secondary"
            icon={<Plus className="h-4 w-4" aria-hidden />}
            onClick={() => {
              setTratoEnEdicion(null);
              setModalTrato(true);
            }}
          >
            Nueva oportunidad
          </Button>
        </div>

        {errores.tratos ? (
          <p role="alert" className="rounded-card border border-semaforo-incumple/30 bg-semaforo-incumple-bg px-3 py-2 text-sm text-semaforo-incumple">
            No se pudieron traer las oportunidades: {errores.tratos}
          </p>
        ) : tratos.length === 0 ? (
          <EmptyState
            icono={Handshake}
            titulo="Sin oportunidades"
            descripcion="Crea la primera para que aparezca en el pipeline."
            accion={
              <Button
                onClick={() => {
                  setTratoEnEdicion(null);
                  setModalTrato(true);
                }}
              >
                Nueva oportunidad
              </Button>
            }
          />
        ) : (
          <ul className="flex flex-col gap-3">
            {tratos.map((t) => {
              const etapa = etapaDe(t);
              const bloqueo = motivoParaNoPromover(t, etapa);
              return (
                <li key={t.id} className="rounded-card border border-slate-200 bg-white p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-900">{t.titulo}</p>
                      <p className="mt-0.5 text-sm text-slate-500">
                        {etapa?.nombre ?? 'Etapa desconocida'} ·{' '}
                        {t.monto === null ? 'Sin valorar' : formatearMonto(t.monto, t.moneda)} ·
                        Cierre {formatearFecha(t.cierreEstimado)} ·{' '}
                        {nombreDelResponsable(t.responsableId, personas)}
                      </p>
                      {t.motivoPerdida && (
                        <p className="mt-1 text-sm text-slate-600">
                          Se perdió: {t.motivoPerdida}
                        </p>
                      )}
                      {t.contratoId && (
                        <p className="mt-1 text-xs text-slate-500">
                          Enlazado a un contrato.
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setTratoEnEdicion(t);
                          setModalTrato(true);
                        }}
                      >
                        Editar
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setTratoAMover(t)}
                        disabled={etapas.length === 0}
                      >
                        Mover
                      </Button>
                      {/* El botón aparece solo cuando el servidor lo va a
                          aceptar. Una acción visible que responde error es peor
                          que una que no está: se intenta, se falla, y no queda
                          claro si el problema es el trato o el sistema. */}
                      {sePuedePromover(t, etapa) && (
                        <Button size="sm" onClick={() => setTratoAPromover(t)}>
                          Promover a contrato
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void retirarCon('deals', t.id, `«${t.titulo}»`)}
                      >
                        Retirar
                      </Button>
                    </div>
                  </div>
                  {/* Y cuando no se puede, se dice por qué en vez de dejar el
                      hueco: la pregunta «por qué a este trato sí y a este no»
                      es la que se hace mirando la lista. */}
                  {bloqueo && !t.contratoId && (
                    <p className="mt-2 text-xs text-slate-500">{bloqueo}</p>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        {errores.etapas && (
          <p className="text-xs text-slate-500">
            No se pudieron traer las etapas del pipeline, así que no se puede mover
            un trato de columna: {errores.etapas}
          </p>
        )}
      </section>

      {/* ── Línea de tiempo ───────────────────────────────────────────── */}
      <section className="flex flex-col gap-3">
        <h2 className="text-base font-semibold text-slate-900">Actividad</h2>

        <RegistrarActividadCrm onRegistrar={registrarActividad} />

        {errores.actividades ? (
          <p role="alert" className="rounded-card border border-semaforo-incumple/30 bg-semaforo-incumple-bg px-3 py-2 text-sm text-semaforo-incumple">
            No se pudo traer la línea de tiempo: {errores.actividades}
          </p>
        ) : actividades.length === 0 ? (
          <p className="text-sm text-slate-500">
            Todavía no hay nada anotado con esta empresa.
          </p>
        ) : (
          <ol className="flex flex-col gap-3">
            {actividades.map((a) => (
              <li key={a.id} className="rounded-card border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-medium text-slate-900">
                    <span className="mr-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                      {TIPO_DE_ACTIVIDAD[a.tipo] ?? a.tipo}
                    </span>
                    {a.asunto}
                  </p>
                  <span className="text-xs text-slate-500">{formatearFecha(a.ocurrioEn)}</span>
                </div>

                {actividadEnEdicion === a.id ? (
                  /* Se corrige en su sitio y no en un modal: casi siempre es
                     arreglar una palabra, y para eso abrir una ventana cuesta
                     más que el arreglo. El tipo y el padre no se tocan — mover
                     una llamada de un trato a otro reescribiría dos líneas de
                     tiempo a la vez. */
                  <form
                    className="mt-2 flex flex-col gap-2"
                    onSubmit={async (e) => {
                      e.preventDefault();
                      const datos = new FormData(e.currentTarget);
                      const r = await editarActividad(a.id, {
                        asunto: String(datos.get('asunto') ?? ''),
                        detalle: String(datos.get('detalle') ?? ''),
                      });
                      setErrorDeAccion(r.ok ? null : (r.error ?? 'No se pudo guardar.'));
                      if (r.ok) setActividadEnEdicion(null);
                    }}
                  >
                    <label className="sr-only" htmlFor={`asunto-${a.id}`}>
                      Asunto
                    </label>
                    <Input id={`asunto-${a.id}`} name="asunto" defaultValue={a.asunto} required />
                    <label className="sr-only" htmlFor={`detalle-${a.id}`}>
                      Detalle
                    </label>
                    <Textarea
                      id={`detalle-${a.id}`}
                      name="detalle"
                      rows={2}
                      defaultValue={a.detalle ?? ''}
                    />
                    <div className="flex justify-end gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => setActividadEnEdicion(null)}
                      >
                        Cancelar
                      </Button>
                      <Button type="submit" size="sm">
                        Guardar
                      </Button>
                    </div>
                  </form>
                ) : (
                  <>
                    {a.detalle && (
                      <p className="mt-1 whitespace-pre-line text-sm text-slate-600">
                        {a.detalle}
                      </p>
                    )}
                    <div className="mt-1 flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setActividadEnEdicion(a.id)}
                      >
                        Corregir
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void retirarCon('activities', a.id, 'esta anotación')}
                      >
                        Retirar
                      </Button>
                    </div>
                  </>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>

      <ContactoCrmModal
        open={modalContacto}
        onOpenChange={setModalContacto}
        contacto={contactoEnEdicion}
        onGuardar={(datos) =>
          contactoEnEdicion
            ? editarContacto(contactoEnEdicion.id, datos)
            : agregarContacto(datos)
        }
      />

      <TratoCrmModal
        open={modalTrato}
        onOpenChange={setModalTrato}
        trato={tratoEnEdicion}
        contactos={contactos}
        onGuardar={(datos) =>
          tratoEnEdicion ? editarTrato(tratoEnEdicion.id, datos) : crearTrato(datos)
        }
      />

      <MoverTratoModal
        open={tratoAMover !== null}
        onOpenChange={(abierto) => {
          if (!abierto) setTratoAMover(null);
        }}
        trato={tratoAMover}
        etapas={etapas}
        onMover={async (id, etapaId, motivo) => {
          const r = await moverTrato(id, etapaId, motivo);
          if (r.ok) setEfectos(r.efectos ?? []);
          return r;
        }}
      />

      <PromoverTratoModal
        open={tratoAPromover !== null}
        onOpenChange={(abierto) => {
          if (!abierto) setTratoAPromover(null);
        }}
        empresa={empresa}
        trato={tratoAPromover}
        onPromover={async (id, contratoId) => {
          const r = await promover(id, contratoId);
          if (r.ok) setEfectos(r.efectos ?? []);
          return r;
        }}
      />
    </div>
  );
}
