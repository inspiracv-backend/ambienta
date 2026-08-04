'use client';

import { useEffect, useId, useMemo, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { RotateCcw, ShieldAlert, X } from 'lucide-react';
import type { Permiso, User } from '@ambienta/shared';
import { CATALOGO_PERMISOS, PERMISOS_POR_DEFECTO, permisosEfectivos } from '@ambienta/shared';
import { Button, Textarea } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useUsers } from '@/lib/users-store';
import { useToast } from '@/lib/toast-store';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { eventoCambioDePermisos } from '@/lib/user-audit';
import { ROLE_LABEL } from '@/lib/roles';
import { cn } from '@/lib/utils';

/** Grupos en el orden del catálogo, sin repetir. */
function gruposDelCatalogo(): string[] {
  return CATALOGO_PERMISOS.reduce<string[]>((acc, p) => (acc.includes(p.grupo) ? acc : [...acc, p.grupo]), []);
}

/**
 * Matriz de permisos de una persona (RF-12).
 *
 * Hasta ahora el Admin Empresa solo podía asignar un rol: cinco cajas fijas
 * para toda la empresa. Pero dos personas con el mismo rol tienen
 * responsabilidades distintas según su departamento — el Análisis de Actores
 * lo dice explícitamente (§2.3): el Usuario Interno "no es una fila única
 * sino un espacio de configuración".
 *
 * Decisiones de la interfaz:
 *
 * - **Se muestra qué viene del rol y qué se cambió a mano.** Sin eso, quien
 *   revisa la configuración no puede distinguir una decisión deliberada de un
 *   valor que nadie tocó. El botón de restablecer vuelve al set del rol.
 * - **Los permisos sensibles van marcados.** Conceder "aprobar cierres" rompe
 *   el control cruzado que revisa un certificador (quien registra un hallazgo
 *   no debería poder aprobarlo solo), así que no puede pasar inadvertido al
 *   copiar la configuración de otra persona.
 * - **Se pide un motivo.** RF-32 exige el "por qué" en el audit log, y un
 *   cambio de permisos es de los eventos donde más falta hace.
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
  const { updatePermisos } = useUsers();
  const { mostrarToast } = useToast();
  const registrar = useRegistrarAuditoria();

  const actuales = useMemo(
    () => (user ? permisosEfectivos(user.role, user.permisos as Permiso[] | undefined) : []),
    [user],
  );
  const porDefecto = useMemo(() => (user ? PERMISOS_POR_DEFECTO[user.role] : []), [user]);

  const [seleccion, setSeleccion] = useState<Permiso[]>(actuales);
  const [motivo, setMotivo] = useState('');

  // Al abrir con otra persona hay que recargar: si no, se arrastra la
  // selección del usuario anterior y se le aplicarían permisos ajenos.
  useEffect(() => {
    if (open) {
      setSeleccion(actuales);
      setMotivo('');
    }
  }, [open, actuales]);

  if (!user) return null;

  const setActuales = new Set(actuales);
  const setDefecto = new Set(porDefecto);
  const hayCambios =
    seleccion.length !== actuales.length || seleccion.some((p) => !setActuales.has(p));
  const difiereDelRol =
    seleccion.length !== porDefecto.length || seleccion.some((p) => !setDefecto.has(p));

  function toggle(permiso: Permiso) {
    setSeleccion((prev) => (prev.includes(permiso) ? prev.filter((p) => p !== permiso) : [...prev, permiso]));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!user || !hayCambios) return;

    updatePermisos(user.id, seleccion);
    registrar(eventoCambioDePermisos(user, actuales, seleccion, motivo.trim() || undefined));

    mostrarToast({
      tipo: 'exito',
      mensaje: `Permisos de ${user.nombre} actualizados`,
      descripcion: 'El cambio quedó en su historial con quién lo hizo y por qué.',
      onUndo: () => {
        updatePermisos(user.id, actuales);
        registrar(eventoCambioDePermisos(user, seleccion, actuales, 'Se deshizo el cambio anterior.'));
      },
    });

    onOpenChange(false);
  }

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
                {user.descriptorCargo?.cargo ? ` · ${user.descriptorCargo.cargo}` : ''} · Define qué puede hacer en
                el sistema, más allá de su rol.
              </Dialog.Description>
            </div>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
            <div className="flex-1 overflow-y-auto p-6">
              {difiereDelRol && (
                <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-semaforo-parcial/30 bg-semaforo-parcial-bg px-3 py-2">
                  <p className="text-xs text-slate-700">
                    Esta configuración se apartó de lo que trae el rol {ROLE_LABEL[user.role]}.
                  </p>
                  <button
                    type="button"
                    onClick={() => setSeleccion(porDefecto)}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                  >
                    <RotateCcw className="h-3.5 w-3.5" aria-hidden />
                    Restablecer los del rol
                  </button>
                </div>
              )}

              <div className="flex flex-col gap-5">
                {gruposDelCatalogo().map((grupo) => (
                  <fieldset key={grupo}>
                    <legend className="text-xs font-semibold uppercase tracking-wide text-slate-500">{grupo}</legend>
                    <div className="mt-2 flex flex-col gap-1.5">
                      {CATALOGO_PERMISOS.filter((p) => p.grupo === grupo).map((p) => {
                        const marcado = seleccion.includes(p.clave);
                        const esDefectoDelRol = setDefecto.has(p.clave);
                        return (
                          <label
                            key={p.clave}
                            className={cn(
                              'flex cursor-pointer items-start gap-2.5 rounded-lg border p-2.5 transition',
                              marcado ? 'border-brand-300 bg-brand-50/50' : 'border-slate-200 hover:border-slate-300',
                            )}
                          >
                            <input
                              type="checkbox"
                              className="mt-0.5 h-4 w-4"
                              checked={marcado}
                              onChange={() => toggle(p.clave)}
                            />
                            <span className="min-w-0 flex-1">
                              <span className="flex flex-wrap items-center gap-1.5">
                                <span className="text-sm font-medium text-slate-800">{p.nombre}</span>
                                {p.sensible && (
                                  <span className="inline-flex items-center gap-1 rounded-full bg-semaforo-parcial-bg px-1.5 py-0.5 text-[10px] font-semibold text-semaforo-parcial">
                                    <ShieldAlert className="h-3 w-3" aria-hidden />
                                    Sensible
                                  </span>
                                )}
                                {/* Distinguir el default del cambio manual es lo
                                    que permite auditar la configuración. */}
                                {marcado !== esDefectoDelRol && (
                                  <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
                                    {marcado ? 'Concedido aparte' : 'Revocado'}
                                  </span>
                                )}
                              </span>
                              <span className="mt-0.5 block text-xs text-slate-500">{p.descripcion}</span>
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </fieldset>
                ))}
              </div>

              <div className="mt-5 border-t border-slate-100 pt-4">
                <FormField
                  label="Motivo del cambio"
                  htmlFor={`${formId}-motivo`}
                  hint="Queda en el historial. Ayuda a explicar la decisión en una auditoría."
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
            </div>

            <div className="flex items-center justify-between gap-2 border-t border-slate-200 p-4">
              <p className="text-xs text-slate-500">
                {seleccion.length} de {CATALOGO_PERMISOS.length} permisos
              </p>
              <div className="flex gap-2">
                <Dialog.Close asChild>
                  <Button type="button" variant="secondary">
                    Cancelar
                  </Button>
                </Dialog.Close>
                <Button type="submit" disabled={!hayCambios}>
                  Guardar permisos
                </Button>
              </div>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
