'use client';

import { useId, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, Plus, ShieldAlert, UserPlus, X } from 'lucide-react';
import type { User } from '@ambienta/shared';
import { AccountBadge, Avatar, Button, Input } from '@/components/atoms';
import { EmptyState, FormField, PageHeader } from '@/components/molecules';
import { useUsers } from '@/lib/users-store';
import { useToast } from '@/lib/toast-store';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { eventoCambioDeEstado, eventoUsuarioInvitado } from '@/lib/user-audit';
import { cn } from '@/lib/utils';

function formatFecha(iso: string | null): string {
  if (!iso) return 'Nunca ingresó';
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

/**
 * Equipo de plataforma (RF-81, RF-84).
 *
 * El Superadmin no podía incorporar a nadie más: el equipo interno era un solo
 * usuario del mock, así que no había forma de sumar a alguien de soporte ni de
 * dar de baja a quien saliera de la empresa.
 *
 * ⚠️ **Todos entran con permisos completos de plataforma.** RF-84 distingue
 * "equipo interno" de "Superadmin", lo que implica al menos dos niveles —
 * Superadmin con control total y Soporte con acceso acotado a tickets. Esa
 * separación es una pregunta de gobernanza abierta (§3.1 del Análisis de
 * Actores) y sigue sin resolverse, así que aquí no se inventa: quien se
 * incorpora puede hacer todo lo que hace un Superadmin, y la interfaz lo dice
 * en vez de sugerir un control de permisos que no existe.
 */
export function EquipoPlataformaView({ currentUserId }: { currentUserId: string }) {
  const formId = useId();
  const { users, inviteUser, setEstado } = useUsers();
  const { mostrarToast } = useToast();
  const registrar = useRegistrarAuditoria();

  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [nombre, setNombre] = useState('');
  const [email, setEmail] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [pendingDesactivar, setPendingDesactivar] = useState<User | null>(null);
  const [confirmacion, setConfirmacion] = useState('');

  // Equipo de plataforma = los que no pertenecen a ninguna empresa.
  const equipo = users.filter((u) => u.tenantId === null);
  const activos = equipo.filter((u) => u.estado !== 'desactivado');

  function handleInvitar(e: FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!nombre.trim()) next.nombre = 'Ingresa el nombre.';
    if (!/^\S+@\S+\.\S+$/.test(email)) next.email = 'Ingresa un correo válido.';
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    const nuevo = inviteUser({
      tenantId: null,
      nombre: nombre.trim(),
      email: email.trim(),
      role: 'superadmin',
      plantIds: [],
      departamentoId: null,
    });
    registrar({ ...eventoUsuarioInvitado(nuevo), tenantId: null });

    mostrarToast({
      tipo: 'exito',
      mensaje: `${nuevo.nombre} se incorporó al equipo`,
      descripcion: 'Tiene acceso completo a la administración de la plataforma.',
    });

    setNombre('');
    setEmail('');
    setErrors({});
    setIsInviteOpen(false);
  }

  function handleDesactivar() {
    if (!pendingDesactivar) return;
    const anterior = pendingDesactivar.estado;
    setEstado(pendingDesactivar.id, 'desactivado');
    registrar({ ...eventoCambioDeEstado(pendingDesactivar, anterior, 'desactivado'), tenantId: null });

    mostrarToast({
      tipo: 'info',
      mensaje: `${pendingDesactivar.nombre} fue dado de baja`,
      descripcion: 'Pierde el acceso a la plataforma de inmediato.',
      onUndo: () => {
        setEstado(pendingDesactivar.id, anterior);
        registrar({ ...eventoCambioDeEstado(pendingDesactivar, 'desactivado', anterior), tenantId: null });
      },
    });

    setPendingDesactivar(null);
    setConfirmacion('');
  }

  function handleReactivar(user: User) {
    setEstado(user.id, 'activo');
    registrar({ ...eventoCambioDeEstado(user, user.estado, 'activo'), tenantId: null });
    mostrarToast({ tipo: 'exito', mensaje: `${user.nombre} fue reactivado` });
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        titulo="Equipo de plataforma"
        descripcion="Personas con acceso a la administración de Ambienta"
        acciones={
          <Button onClick={() => setIsInviteOpen(true)} icon={<Plus className="h-4 w-4" aria-hidden />}>
            Incorporar persona
          </Button>
        }
      />

      {/* La advertencia va arriba y no escondida: incorporar a alguien aquí le
          da acceso a todos los clientes de la plataforma. */}
      <div className="flex items-start gap-2 rounded-card border border-semaforo-parcial/30 bg-semaforo-parcial-bg p-4">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-semaforo-parcial" aria-hidden />
        <div className="text-xs leading-relaxed text-slate-700">
          <p className="font-semibold">Quien se incorpore tendrá acceso completo a la plataforma.</p>
          <p className="mt-0.5">
            Podrá dar de alta empresas, cambiar límites y suspender cuentas. Todavía no existen perfiles con permisos
            acotados (por ejemplo, un rol de Soporte solo para tickets): esa separación está pendiente de definición.
          </p>
        </div>
      </div>

      {equipo.length === 0 ? (
        <EmptyState
          icono={UserPlus}
          titulo="No hay nadie más en el equipo"
          descripcion="Incorpora a las personas que administrarán la plataforma junto a ti."
        />
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
          <table className="w-full min-w-[640px] text-sm">
            <caption className="sr-only">Equipo de plataforma</caption>
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                <th scope="col" className="px-4 py-3">Persona</th>
                <th scope="col" className="px-4 py-3">Estado</th>
                <th scope="col" className="px-4 py-3">Última actividad</th>
                <th scope="col" className="px-4 py-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {equipo.map((u) => {
                const esUnoMismo = u.id === currentUserId;
                const esUltimoActivo = activos.length === 1 && activos[0]?.id === u.id;

                return (
                  <tr key={u.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Avatar nombre={u.nombre} avatarUrl={u.avatarUrl} size="sm" />
                        <div>
                          <p className="font-medium text-slate-800">
                            {u.nombre}{' '}
                            {esUnoMismo && <span className="text-xs font-normal text-slate-400">(tú)</span>}
                          </p>
                          <p className="text-xs text-slate-500">{u.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <AccountBadge estado={u.estado === 'desactivado' ? 'suspendido' : 'activo'} />
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">{formatFecha(u.ultimaActividad)}</td>
                    <td className="px-4 py-3 text-right">
                      {u.estado === 'desactivado' ? (
                        <Button variant="secondary" size="md" onClick={() => handleReactivar(u)}>
                          Reactivar
                        </Button>
                      ) : (
                        <Button
                          variant="secondary"
                          size="md"
                          // Nadie se da de baja a sí mismo, y no se puede
                          // dejar la plataforma sin ningún administrador
                          // activo: quedaría inaccesible para todos.
                          disabled={esUnoMismo || esUltimoActivo}
                          title={
                            esUnoMismo
                              ? 'No puedes darte de baja a ti mismo'
                              : esUltimoActivo
                                ? 'Es el único administrador activo'
                                : undefined
                          }
                          onClick={() => setPendingDesactivar(u)}
                        >
                          Dar de baja
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Incorporar ─────────────────────────────────────────────────── */}
      <Dialog.Root
        open={isInviteOpen}
        onOpenChange={(open) => {
          setIsInviteOpen(open);
          if (!open) setErrors({});
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-6 shadow-lg">
            <div className="flex items-start justify-between">
              <Dialog.Title className="text-lg font-semibold text-slate-900">Incorporar al equipo</Dialog.Title>
              <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
                <X className="h-5 w-5" aria-hidden />
              </Dialog.Close>
            </div>
            <Dialog.Description className="mt-1 text-xs text-slate-500">
              Tendrá acceso completo a la administración de la plataforma y a todas las empresas cliente.
            </Dialog.Description>

            <form onSubmit={handleInvitar} className="mt-4 flex flex-col gap-4" noValidate>
              <FormField label="Nombre" htmlFor={`${formId}-nombre`} required error={errors.nombre}>
                <Input
                  id={`${formId}-nombre`}
                  value={nombre}
                  invalid={!!errors.nombre}
                  onChange={(e) => setNombre(e.target.value)}
                />
              </FormField>
              <FormField label="Correo" htmlFor={`${formId}-email`} required error={errors.email}>
                <Input
                  id={`${formId}-email`}
                  type="email"
                  value={email}
                  invalid={!!errors.email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </FormField>

              <div className="flex justify-end gap-2">
                <Dialog.Close asChild>
                  <Button type="button" variant="secondary">
                    Cancelar
                  </Button>
                </Dialog.Close>
                <Button type="submit">Incorporar</Button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* ── Dar de baja ────────────────────────────────────────────────── */}
      <Dialog.Root
        open={!!pendingDesactivar}
        onOpenChange={(open) => {
          if (!open) {
            setPendingDesactivar(null);
            setConfirmacion('');
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-6 shadow-lg">
            <div className="flex items-center gap-2 text-semaforo-no-cumple">
              <AlertTriangle className="h-5 w-5" aria-hidden />
              <Dialog.Title className="text-lg font-semibold text-slate-900">Dar de baja del equipo</Dialog.Title>
            </div>
            <Dialog.Description className="mt-3 text-sm text-slate-600">
              <strong>{pendingDesactivar?.nombre}</strong> perderá el acceso a la plataforma de inmediato. La acción
              es reversible y su historial se conserva.
            </Dialog.Description>

            <div className="mt-4">
              <FormField label={`Escribe "${pendingDesactivar?.nombre ?? ''}" para confirmar`} htmlFor="confirmar-baja">
                <Input
                  id="confirmar-baja"
                  value={confirmacion}
                  onChange={(e) => setConfirmacion(e.target.value)}
                  autoComplete="off"
                />
              </FormField>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <Dialog.Close asChild>
                <Button variant="secondary">Cancelar</Button>
              </Dialog.Close>
              <Button
                variant="danger"
                disabled={confirmacion.trim() !== pendingDesactivar?.nombre}
                onClick={handleDesactivar}
              >
                Dar de baja
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
