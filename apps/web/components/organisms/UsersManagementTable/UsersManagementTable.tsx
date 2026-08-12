'use client';

import { useMemo, useState } from 'react';
import { AlertTriangle, Inbox, Plus, Search, X } from 'lucide-react';
import * as Dialog from '@radix-ui/react-dialog';
import type { User } from '@ambienta/shared';
import { Avatar, Button, Input, StatusBadge } from '@/components/atoms';
import { FilterBar } from '@/components/molecules';
import { UserFormModal } from '@/components/organisms/UserFormModal';
import { useUsers } from '@/lib/users-store';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useToast } from '@/lib/toast-store';
import { eventoCambioDeEstado } from '@/lib/user-audit';
import { PermisosUsuarioModal } from '@/components/organisms/PermisosUsuarioModal/PermisosUsuarioModal';
import { permisosEfectivos, type Permiso } from '@ambienta/shared';
import { ROLE_LABEL } from '@/lib/roles';
import { userSemaforo, USER_ESTADO_LABEL } from '@/lib/user-status';
import type { UsersManagementTableProps } from './UsersManagementTable.types';

function formatFecha(iso: string | null) {
  if (!iso) return 'Nunca';
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

/**
 * S-41 Gestión de Usuarios y Roles. Desactivar pide confirmación (H5, mismo
 * criterio que `TenantsManagementTable`); un usuario no puede desactivarse
 * a sí mismo (evita auto-bloqueo).
 */
export function UsersManagementTable({ users, plants, departamentos, tenantId, esGestorTenant, currentUserId }: UsersManagementTableProps) {
  const { setEstado } = useUsers();
  const registrar = useRegistrarAuditoria();
  const { mostrarToast } = useToast();

  /**
   * Activar/desactivar pasa por aquí y no por el store porque `UsersProvider`
   * está por encima de `SessionProvider` y no puede firmar eventos con el
   * actor (ver `lib/users-store.tsx`).
   */
  function cambiarEstado(user: (typeof users)[number], estadoNuevo: 'activo' | 'desactivado') {
    const estadoAnterior = user.estado;
    setEstado(user.id, estadoNuevo);
    registrar(eventoCambioDeEstado(user, estadoAnterior, estadoNuevo));
    mostrarToast({
      tipo: estadoNuevo === 'desactivado' ? 'info' : 'exito',
      mensaje: estadoNuevo === 'desactivado' ? `${user.nombre} fue desactivado` : `${user.nombre} fue reactivado`,
      descripcion: 'El cambio quedó registrado en el historial.',
      onUndo: () => {
        setEstado(user.id, estadoAnterior);
        registrar(eventoCambioDeEstado(user, estadoNuevo, estadoAnterior));
      },
    });
  }
  const [permisosTarget, setPermisosTarget] = useState<(typeof users)[number] | null>(null);
  const [busqueda, setBusqueda] = useState('');
  const [rolFiltro, setRolFiltro] = useState('todos');
  const [estadoFiltro, setEstadoFiltro] = useState('todos');
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<User | null>(null);
  const [pendingDeactivate, setPendingDeactivate] = useState<User | null>(null);

  const filtered = useMemo(
    () =>
      users.filter((u) => {
        if (rolFiltro !== 'todos' && u.role !== rolFiltro) return false;
        if (estadoFiltro !== 'todos' && u.estado !== estadoFiltro) return false;
        if (busqueda.trim()) {
          const q = busqueda.trim().toLowerCase();
          if (!u.nombre.toLowerCase().includes(q) && !u.email.toLowerCase().includes(q)) return false;
        }
        return true;
      }),
    [users, rolFiltro, estadoFiltro, busqueda],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
            Buscar
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
              <Input className="pl-9" placeholder="Nombre o correo" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
            </div>
          </label>
          <FilterBar
            filters={[
              {
                id: 'filtro-rol-usuarios',
                label: 'Rol',
                value: rolFiltro,
                onChange: setRolFiltro,
                options: [{ value: 'todos', label: 'Todos los roles' }, ...Object.entries(ROLE_LABEL).map(([value, label]) => ({ value, label }))],
              },
              {
                id: 'filtro-estado-usuarios',
                label: 'Estado',
                value: estadoFiltro,
                onChange: setEstadoFiltro,
                options: [
                  { value: 'todos', label: 'Todos los estados' },
                  { value: 'activo', label: 'Activo' },
                  { value: 'invitado', label: 'Invitado' },
                  { value: 'desactivado', label: 'Desactivado' },
                ],
              },
            ]}
          />
        </div>
        <Button icon={<Plus className="h-4 w-4" aria-hidden />} onClick={() => setIsInviteOpen(true)}>
          Invitar usuario
        </Button>
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
          <Inbox className="h-6 w-6 text-slate-400" aria-hidden />
          {users.length === 0 ? 'Aún no hay usuarios en esta empresa.' : 'No hay usuarios que coincidan con estos filtros.'}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
          <table className="w-full min-w-[820px] text-sm">
            <caption className="sr-only">Usuarios de la empresa</caption>
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                <th scope="col" className="px-4 py-3">Usuario</th>
                <th scope="col" className="px-4 py-3">Rol</th>
                <th scope="col" className="px-4 py-3">Planta(s)</th>
                <th scope="col" className="px-4 py-3">Departamento</th>
                <th scope="col" className="px-4 py-3">Estado</th>
                <th scope="col" className="px-4 py-3">Última actividad</th>
                <th scope="col" className="px-4 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => {
                const nombresPlantas = plants.filter((p) => u.plantIds.includes(p.id)).map((p) => p.nombre);
                const depto = departamentos.find((d) => d.id === u.departamentoId);
                const esUnoMismo = u.id === currentUserId;
                return (
                  <tr key={u.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Avatar nombre={u.nombre} avatarUrl={u.avatarUrl} size="sm" />
                        <div>
                          <p className="font-medium text-slate-800">
                            {u.nombre} {esUnoMismo && <span className="text-xs font-normal text-slate-400">(tú)</span>}
                          </p>
                          {/* El cargo es lo que se revisa en una auditoría de
                              competencia (ISO 9001 §7.2); el rol del sistema
                              va en su propia columna. */}
                          {u.descriptorCargo?.cargo && (
                            <p className="text-xs font-medium text-slate-600">{u.descriptorCargo.cargo}</p>
                          )}
                          <p className="text-xs text-slate-500">{u.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                        {ROLE_LABEL[u.role]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{nombresPlantas.join(', ') || '—'}</td>
                    <td className="px-4 py-3 text-slate-500">{depto?.nombre ?? '—'}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={userSemaforo(u.estado)} className="mr-1" />
                      <span className="text-slate-500">{USER_ESTADO_LABEL[u.estado]}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatFecha(u.ultimaActividad)}</td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <Button variant="secondary" size="md" onClick={() => setEditTarget(u)}>
                          Editar
                        </Button>
                        {/* Los permisos van en su propio modal y no dentro de
                            "Editar": mezclarlos con nombre y planta haría que
                            se cambien de paso, sin pensarlo. */}
                        <Button variant="secondary" size="md" onClick={() => setPermisosTarget(u)}>
                          Permisos
                        </Button>
                        {!esUnoMismo && (
                          <Button
                            variant={u.estado === 'desactivado' ? 'secondary' : 'danger'}
                            size="md"
                            onClick={() =>
                              u.estado === 'desactivado' ? cambiarEstado(u, 'activo') : setPendingDeactivate(u)
                            }
                          >
                            {u.estado === 'desactivado' ? 'Activar' : 'Desactivar'}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <PermisosUsuarioModal
        open={!!permisosTarget}
        onOpenChange={(open) => !open && setPermisosTarget(null)}
        user={permisosTarget}
      />

      <UserFormModal
        open={isInviteOpen}
        onOpenChange={setIsInviteOpen}
        tenantId={tenantId}
        esGestorTenant={esGestorTenant}
        plants={plants}
        departamentos={departamentos}
      />

      {editTarget && (
        <UserFormModal
          open={!!editTarget}
          onOpenChange={(open) => !open && setEditTarget(null)}
          user={editTarget}
          tenantId={tenantId}
          esGestorTenant={esGestorTenant}
          plants={plants}
          departamentos={departamentos}
        />
      )}

      <Dialog.Root open={!!pendingDeactivate} onOpenChange={(open) => !open && setPendingDeactivate(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-6 shadow-lg">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2 text-semaforo-no-cumple">
                <AlertTriangle className="h-5 w-5" aria-hidden />
                <Dialog.Title className="text-lg font-semibold text-slate-900">Desactivar usuario</Dialog.Title>
              </div>
              <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
                <X className="h-5 w-5" aria-hidden />
              </Dialog.Close>
            </div>
            <Dialog.Description className="mt-2 text-sm text-slate-600">
              <strong>{pendingDeactivate?.nombre}</strong> perderá acceso a la plataforma de inmediato. ¿Confirmas esta acción?
            </Dialog.Description>
            <div className="mt-6 flex justify-end gap-2">
              <Dialog.Close asChild>
                <Button variant="secondary">Cancelar</Button>
              </Dialog.Close>
              <Button
                variant="danger"
                onClick={() => {
                  if (pendingDeactivate) cambiarEstado(pendingDeactivate, 'desactivado');
                  setPendingDeactivate(null);
                }}
              >
                Sí, desactivar
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
