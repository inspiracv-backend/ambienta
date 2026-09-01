'use client';

import { useCallback, useEffect, useId, useState, type ReactNode } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, Loader2, RotateCcw, X } from 'lucide-react';
import type { User } from '@ambienta/shared';
import { Button, Textarea } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useToast } from '@/lib/toast-store';
import { ROLE_LABEL } from '@/lib/roles';
import {
  cargarCatalogo,
  cargarPermisosDe,
  estadoDe,
  fijarPermiso,
  nombreDeRespaldo,
  porModulo,
  quitarExcepcion,
  type EstadoDePermiso,
  type PermisoDelCatalogo,
  type PermisosDelUsuario,
} from '@/lib/permisos';
import { cn } from '@/lib/utils';

const MOTIVO_MINIMO = 3;

const ETIQUETA: Record<EstadoDePermiso, { texto: string; clase: string } | null> = {
  'del-rol': { texto: 'Del rol', clase: 'bg-slate-100 text-slate-600' },
  concedido: { texto: 'Concedido aparte', clase: 'bg-brand-50 text-brand-700' },
  denegado: { texto: 'Denegado', clase: 'bg-semaforo-incumple-bg text-semaforo-incumple' },
  'sin-permiso': null,
};

/**
 * Matriz de permisos de una persona (RF-12, #217).
 *
 * ## Qué cambió, y por qué no es cosmético
 *
 * Esta pantalla listaba **13 permisos escritos a mano** en `packages/shared`
 * que no tenían **ni una clave en común** con los 39 que la API verifica. Y no
 * guardaba: `updatePermisos` solo tocaba el estado local, mientras el aviso
 * decía *"el cambio quedó en su historial"*. Marcar casillas no restringía a
 * nadie.
 *
 * Ahora el catálogo viene de `GET /permissions` y cada cambio va a
 * `PUT|DELETE /users/{id}/permissions/{codigo}`, con los mismos códigos que
 * usa la guarda. Sin traducción en el medio.
 *
 * ## Tres estados, no dos
 *
 * Una casilla marcada/desmarcada no alcanza: *desmarcado* significa dos cosas
 * distintas —"su rol no se lo da" y "su rol se lo da y se lo quitamos"— y la
 * segunda es una fila explícita que hay que poder ver y revertir. Por eso cada
 * permiso muestra de dónde viene y ofrece la acción que corresponde.
 *
 * ## Cada cambio se aplica solo, y no en lote
 *
 * La API escribe un permiso por petición y **exige un motivo**. Juntar N
 * cambios en un botón "Guardar" obligaría a mandar N peticiones y decidir qué
 * decir cuando la mitad falla — y el camino fácil ahí es avisar éxito igual,
 * que es exactamente el defecto que esta pantalla tenía. Aplicando de a uno,
 * lo que se ve marcado es lo que el servidor confirmó.
 */
export function PermisosUsuarioModal({
  open,
  onOpenChange,
  user,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: User | null;
}) {
  const formId = useId();
  const { mostrarToast } = useToast();

  const [catalogo, setCatalogo] = useState<PermisoDelCatalogo[] | null>(null);
  const [permisos, setPermisos] = useState<PermisosDelUsuario | null>(null);
  const [cargando, setCargando] = useState(false);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);
  const [aplicando, setAplicando] = useState<string | null>(null);
  const [motivo, setMotivo] = useState('');

  const tenantId = user?.tenantId ?? null;
  const userId = user?.id ?? null;

  const cargar = useCallback(async () => {
    if (!userId || !tenantId) return;
    setCargando(true);
    setErrorDeCarga(null);
    try {
      const [cat, act] = await Promise.all([
        cargarCatalogo(tenantId),
        cargarPermisosDe(userId, tenantId),
      ]);
      setCatalogo(cat);
      setPermisos(act);
    } catch {
      // No se deja el catálogo anterior a la vista: sería el de otra persona,
      // o peor, una lista que ya no refleja lo que el servidor cree.
      setCatalogo(null);
      setPermisos(null);
      setErrorDeCarga('No se pudieron cargar los permisos.');
    } finally {
      setCargando(false);
    }
  }, [userId, tenantId]);

  // Al abrir con otra persona hay que recargar: si no, se arrastra lo de la
  // anterior y se estarían mostrando permisos ajenos como si fueran suyos.
  useEffect(() => {
    if (!open) return;
    setMotivo('');
    setCatalogo(null);
    setPermisos(null);
    void cargar();
  }, [open, cargar]);

  if (!user) return null;

  const motivoValido = motivo.trim().length >= MOTIVO_MINIMO;

  async function aplicar(codigo: string, accion: () => Promise<PermisosDelUsuario>) {
    setAplicando(codigo);
    try {
      // La API devuelve el conjunto entero: se adopta tal cual en vez de
      // recalcularlo acá, que es como las dos versiones se desincronizan.
      setPermisos(await accion());
      setMotivo('');
    } catch {
      mostrarToast({
        tipo: 'error',
        mensaje: 'El permiso no se pudo cambiar',
        descripcion: 'Nada quedó guardado. Revisá tu conexión y volvé a intentar.',
      });
    } finally {
      setAplicando(null);
    }
  }

  const total = catalogo?.length ?? 0;
  const efectivos = permisos?.permisos.length ?? 0;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 flex-col rounded-card bg-white shadow-lg">
          <div className="flex items-start justify-between border-b border-slate-200 p-6">
            <div>
              <Dialog.Title className="text-lg font-semibold text-slate-900">
                Permisos de {user.nombre}
              </Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-slate-500">
                Rol {ROLE_LABEL[user.role]}
                {user.descriptorCargo?.cargo ? ` · ${user.descriptorCargo.cargo}` : ''} · Cada cambio
                se guarda al aplicarlo.
              </Dialog.Description>
            </div>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex-1 overflow-y-auto p-6">
              {cargando && (
                <p className="flex items-center gap-2 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  Cargando los permisos…
                </p>
              )}

              {errorDeCarga && !cargando && (
                <div className="rounded-lg border border-semaforo-incumple/30 bg-semaforo-incumple-bg p-4">
                  <p className="flex items-center gap-2 text-sm font-medium text-semaforo-incumple">
                    <AlertTriangle className="h-4 w-4" aria-hidden />
                    {errorDeCarga}
                  </p>
                  {/* Se dice qué NO se sabe. Mostrar una matriz vacía sería
                      afirmar que esta persona no tiene ningún permiso. */}
                  <p className="mt-1 text-xs text-slate-600">
                    No se muestra nada porque no sabemos qué permisos tiene. Puede seguir
                    teniéndolos todos.
                  </p>
                  <button
                    type="button"
                    onClick={() => void cargar()}
                    className="mt-2 text-xs font-semibold text-brand-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                  >
                    Reintentar
                  </button>
                </div>
              )}

              {catalogo && permisos && (
                <>
                  <div className="mb-4">
                    <FormField
                      label="Motivo del cambio"
                      htmlFor={`${formId}-motivo`}
                      hint={`Obligatorio, mínimo ${MOTIVO_MINIMO} caracteres. Queda en el historial y explica la decisión en una auditoría.`}
                    >
                      <Textarea
                        id={`${formId}-motivo`}
                        rows={2}
                        value={motivo}
                        onChange={(e) => setMotivo(e.target.value)}
                        placeholder="Ej: asume la aprobación de cierres mientras el jefe de área está de vacaciones."
                      />
                    </FormField>
                  </div>

                  <div className="flex flex-col gap-5">
                    {porModulo(catalogo).map((grupo) => (
                      <section key={grupo.modulo}>
                        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                          {grupo.modulo}
                        </h3>
                        <div className="mt-2 flex flex-col gap-1.5">
                          {grupo.permisos.map((permiso) => (
                            <FilaDePermiso
                              key={permiso.codigo}
                              permiso={permiso}
                              estado={estadoDe(permiso.codigo, permisos)}
                              ocupado={aplicando === permiso.codigo}
                              motivoValido={motivoValido}
                              onConceder={() =>
                                userId && tenantId
                                  ? aplicar(permiso.codigo, () =>
                                      fijarPermiso(userId, permiso.codigo, true, motivo.trim(), tenantId),
                                    )
                                  : undefined
                              }
                              onDenegar={() =>
                                userId && tenantId
                                  ? aplicar(permiso.codigo, () =>
                                      fijarPermiso(userId, permiso.codigo, false, motivo.trim(), tenantId),
                                    )
                                  : undefined
                              }
                              onRestablecer={() =>
                                userId && tenantId
                                  ? aplicar(permiso.codigo, () =>
                                      quitarExcepcion(userId, permiso.codigo, tenantId),
                                    )
                                  : undefined
                              }
                            />
                          ))}
                        </div>
                      </section>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div className="flex items-center justify-between gap-2 border-t border-slate-200 p-4">
              <p className="text-xs text-slate-500">
                {catalogo && permisos
                  ? `${efectivos} de ${total} permisos`
                  : 'Sin datos de permisos'}
              </p>
              <Dialog.Close asChild>
                <Button type="button" variant="secondary">
                  Cerrar
                </Button>
              </Dialog.Close>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function FilaDePermiso({
  permiso,
  estado,
  ocupado,
  motivoValido,
  onConceder,
  onDenegar,
  onRestablecer,
}: {
  permiso: PermisoDelCatalogo;
  estado: EstadoDePermiso;
  ocupado: boolean;
  motivoValido: boolean;
  onConceder: () => void;
  onDenegar: () => void;
  onRestablecer: () => void;
}) {
  const etiqueta = ETIQUETA[estado];
  const esExcepcion = estado === 'concedido' || estado === 'denegado';

  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-lg border p-2.5',
        esExcepcion ? 'border-brand-300 bg-brand-50/40' : 'border-slate-200',
      )}
    >
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-1.5">
          <span className="text-sm font-medium text-slate-800">
            {permiso.descripcion.trim() || nombreDeRespaldo(permiso.codigo)}
          </span>
          {etiqueta && (
            <span className={cn('rounded-full px-1.5 py-0.5 text-[10px] font-semibold', etiqueta.clase)}>
              {etiqueta.texto}
            </span>
          )}
        </span>
        {/* El código va a la vista a propósito: es lo que la API verifica y lo
            que hay que citar cuando alguien pregunta por qué un 403. */}
        <code className="mt-0.5 block font-mono text-[11px] text-slate-400">{permiso.codigo}</code>
      </span>

      <span className="flex shrink-0 items-center gap-1.5">
        {ocupado ? (
          <Loader2 className="h-4 w-4 animate-spin text-slate-400" aria-label="Aplicando" />
        ) : (
          <>
            {esExcepcion && (
              <AccionDeFila onClick={onRestablecer} titulo="Volver a lo que da el rol">
                <RotateCcw className="h-3.5 w-3.5" aria-hidden />
                Restablecer
              </AccionDeFila>
            )}
            {estado !== 'concedido' && (
              <AccionDeFila
                onClick={onConceder}
                deshabilitado={!motivoValido}
                titulo={motivoValido ? 'Conceder por encima del rol' : 'Escribí el motivo primero'}
              >
                Conceder
              </AccionDeFila>
            )}
            {estado !== 'denegado' && (
              <AccionDeFila
                onClick={onDenegar}
                deshabilitado={!motivoValido}
                titulo={motivoValido ? 'Denegar aunque el rol lo dé' : 'Escribí el motivo primero'}
              >
                Denegar
              </AccionDeFila>
            )}
          </>
        )}
      </span>
    </div>
  );
}

function AccionDeFila({
  onClick,
  deshabilitado,
  titulo,
  children,
}: {
  onClick: () => void;
  deshabilitado?: boolean;
  titulo: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={deshabilitado}
      title={titulo}
      className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </button>
  );
}
