'use client';

import { useCallback, useEffect, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { ShieldCheck, X } from 'lucide-react';
import type { User } from '@ambienta/shared';
import { Button, Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';
import {
  cargarRoles,
  cargarRolesDe,
  fijarRoles,
  type RolDePermisos,
} from '@/lib/roles-de-permisos';
import { mensajeDeError } from '@/lib/api-client';

/**
 * Asignar el rol que decide qué puede hacer una persona (#140, RF-08).
 *
 * ## Por qué esto es distinto de «Permisos»
 *
 * `PermisosUsuarioModal` administra excepciones individuales sobre un catálogo
 * que **hoy no coincide con el de la API** — cero claves en común, ver #217 —
 * así que sus cambios no llegan a la base.
 *
 * Esto administra `user_roles`, que es **lo único que la guarda de cada ruta
 * consulta**. Va en su propio modal y no dentro de «Editar» por el mismo
 * criterio que ya se aplicó a los permisos: mezclarlo con el nombre y la planta
 * haría que se cambie de paso, sin pensarlo.
 *
 * ## Y por qué no es el `role` de la columna
 *
 * Esa columna sale de `users.user_type` y dice **qué clase de cuenta** es la
 * persona; esto dice **qué puede hacer**. La migración `09_roles_por_codigo`
 * derivó una del otro una vez, y desde entonces son independientes.
 *
 * ## Lo que puede responder el servidor, y por qué se muestra tal cual
 *
 * Un **409** cuando el cambio dejaría a la empresa sin nadie que pueda
 * administrar usuarios. Ese mensaje dice qué hacer para poder seguir —asignarle
 * antes ese permiso a alguien más— y uno genérico no. Se muestra literal.
 */
export function RolDePermisosModal({
  open,
  onOpenChange,
  user,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: User | null;
}) {
  const { user: sesion } = useSession();
  const tenantId = sesion?.tenantId ?? null;

  const [catalogo, setCatalogo] = useState<RolDePermisos[]>([]);
  const [elegidos, setElegidos] = useState<string[]>([]);
  const [cargando, setCargando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [efectos, setEfectos] = useState<string[]>([]);

  const cargar = useCallback(async () => {
    if (!tenantId || !user) return;
    setCargando(true);
    setError(null);
    setEfectos([]);
    try {
      const [roles, suyos] = await Promise.all([
        cargarRoles(tenantId),
        cargarRolesDe(tenantId, user.id),
      ]);
      setCatalogo(roles);
      setElegidos(suyos.ids);
    } catch (e) {
      // **Se dice.** Con el catálogo vacío y sin mensaje, el modal parecería
      // decir que la empresa no tiene roles configurados, que es otra cosa.
      setCatalogo([]);
      setElegidos([]);
      setError(mensajeDeError(e));
    } finally {
      setCargando(false);
    }
  }, [tenantId, user]);

  useEffect(() => {
    if (open) void cargar();
  }, [open, cargar]);

  function alternar(id: string) {
    setElegidos((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  async function guardar() {
    if (!tenantId || !user) return;
    setGuardando(true);
    setError(null);
    const r = await fijarRoles(tenantId, user.id, elegidos);
    setGuardando(false);

    if (!r.ok) {
      setError(r.error ?? 'No se pudo guardar el rol.');
      return;
    }
    // Se muestra qué cambió en vez de cerrar en silencio: retirar un rol quita
    // accesos que la persona tenía, y quien lo hace debería verlo escrito.
    setElegidos(r.ids);
    setEfectos(r.efectos);
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-5 shadow-lg">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Dialog.Title className="flex items-center gap-2 text-base font-semibold text-slate-900">
                <ShieldCheck className="h-4 w-4 text-brand-600" aria-hidden />
                Rol de permisos
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-slate-500">
                {user?.nombre} · decide <strong>qué puede hacer</strong> en el
                sistema. Es distinto del tipo de cuenta que muestra la tabla.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Cerrar"
                className="rounded p-1 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </Dialog.Close>
          </div>

          {error && (
            <p
              role="alert"
              className="mt-4 rounded-card border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
            >
              {error}
            </p>
          )}

          {efectos.length > 0 && (
            <ul
              role="status"
              className="mt-4 list-disc space-y-1 rounded-card border border-emerald-200 bg-emerald-50 px-6 py-3 text-sm text-emerald-800"
            >
              {efectos.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}

          <div className="mt-4">
            {cargando ? (
              <div className="flex justify-center py-8">
                <Spinner label="Cargando roles" />
              </div>
            ) : catalogo.length === 0 ? (
              <p className="rounded-lg border border-dashed border-slate-200 p-4 text-center text-sm text-slate-500">
                {error
                  ? 'No se pudieron cargar los roles.'
                  : 'Esta empresa no tiene roles configurados.'}
              </p>
            ) : (
              <fieldset className="space-y-2">
                <legend className="sr-only">Roles de la empresa</legend>
                {catalogo.map((rol) => (
                  <label
                    key={rol.id}
                    className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50"
                  >
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={elegidos.includes(rol.id)}
                      onChange={() => alternar(rol.id)}
                      disabled={guardando}
                    />
                    <span>
                      <span className="block text-sm font-medium text-slate-800">
                        {rol.nombre}
                      </span>
                      {rol.descripcion && (
                        <span className="block text-xs text-slate-500">
                          {rol.descripcion}
                        </span>
                      )}
                    </span>
                  </label>
                ))}
              </fieldset>
            )}
          </div>

          {/*
            Sin ningún rol la persona **no puede hacer nada**, y es una forma
            legítima de retirarle el acceso sin sacarla de la nómina. Se avisa
            en vez de impedirlo: lo que el servidor sí rechaza es dejar a la
            empresa sin nadie que administre usuarios.
          */}
          {!cargando && catalogo.length > 0 && elegidos.length === 0 && (
            <p className="mt-3 rounded-card border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Sin ningún rol, esta persona no podrá hacer nada en el sistema.
            </p>
          )}

          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button variant="secondary" disabled={guardando}>
                Cerrar
              </Button>
            </Dialog.Close>
            <Button onClick={() => void guardar()} isLoading={guardando} disabled={cargando}>
              Guardar
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
