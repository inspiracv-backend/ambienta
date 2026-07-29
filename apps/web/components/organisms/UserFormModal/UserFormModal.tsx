'use client';

import { useId, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useUsers } from '@/lib/users-store';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useToast } from '@/lib/toast-store';
import {
  eventoCambioDeDepartamento,
  eventoCambioDePlantas,
  eventoCambioDeRol,
  eventoUsuarioInvitado,
} from '@/lib/user-audit';
import { ROLE_LABEL, ROLE_DESCRIPTION } from '@/lib/roles';
import type { AssignableRole, UserFormModalProps } from './UserFormModal.types';

const ROLES_ASIGNABLES: AssignableRole[] = ['admin_empresa', 'usuario_interno', 'gestor'];

/**
 * S-41: un solo modal parametrizado para "Invitar usuario" (sin `user`) y
 * "Editar usuario" (con `user`) — evita duplicar ~90% del formulario. El
 * selector de rol se acota a los roles que un Admin Empresa puede asignar
 * dentro de su propio tenant (ver gap en seccion-n-usuarios-roles-perfil.md).
 */
export function UserFormModal({ open, onOpenChange, user, tenantId, esGestorTenant, plants, departamentos }: UserFormModalProps) {
  const formId = useId();
  const { inviteUser, updateRole, updatePlants, updateDepartamento, updateDescriptorCargo } = useUsers();
  const registrar = useRegistrarAuditoria();
  const { mostrarToast } = useToast();
  const esEdicion = !!user;

  const [nombre, setNombre] = useState(user?.nombre ?? '');
  const [email, setEmail] = useState(user?.email ?? '');
  const [role, setRole] = useState<AssignableRole>((user?.role as AssignableRole) ?? 'usuario_interno');
  const [plantIds, setPlantIds] = useState<string[]>(user?.plantIds ?? []);
  const [departamentoId, setDepartamentoId] = useState<string>(user?.departamentoId ?? '');
  const [cargo, setCargo] = useState(user?.descriptorCargo?.cargo ?? '');
  const [errors, setErrors] = useState<Record<string, string>>({});

  const rolesDisponibles = ROLES_ASIGNABLES.filter((r) => r !== 'gestor' || esGestorTenant);

  function resetForm() {
    setNombre(user?.nombre ?? '');
    setEmail(user?.email ?? '');
    setRole((user?.role as AssignableRole) ?? 'usuario_interno');
    setPlantIds(user?.plantIds ?? []);
    setDepartamentoId(user?.departamentoId ?? '');
    setErrors({});
  }

  function togglePlant(plantId: string) {
    setPlantIds((prev) => (prev.includes(plantId) ? prev.filter((id) => id !== plantId) : [...prev, plantId]));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!esEdicion) {
      if (!nombre.trim()) next.nombre = 'Ingresa un nombre.';
      if (!/^\S+@\S+\.\S+$/.test(email)) next.email = 'Ingresa un correo válido.';
    }
    if (role === 'usuario_interno' && !departamentoId) next.departamentoId = 'Selecciona un departamento (RF-11).';
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    const depto = role === 'usuario_interno' ? departamentoId : null;

    if (esEdicion && user) {
      // Se registra un evento por dimensión cambiada, no uno genérico
      // "actualizó el usuario": cambiar el rol y cambiar la planta son hechos
      // distintos para quien audita, y el rol además es una decisión de
      // seguridad. Solo se anota lo que efectivamente cambió.
      if (user.role !== role) {
        updateRole(user.id, role);
        registrar(eventoCambioDeRol(user, user.role, role));
      }
      if (JSON.stringify(user.plantIds) !== JSON.stringify(plantIds)) {
        updatePlants(user.id, plantIds);
        registrar(eventoCambioDePlantas(user, user.plantIds, plantIds, plants));
      }
      if ((user.descriptorCargo?.cargo ?? '') !== cargo.trim()) {
        updateDescriptorCargo(user.id, {
          cargo: cargo.trim(),
          funciones: user.descriptorCargo?.funciones ?? [],
          responsabilidades: user.descriptorCargo?.responsabilidades ?? [],
          ...(user.descriptorCargo?.documentoUrl ? { documentoUrl: user.descriptorCargo.documentoUrl } : {}),
        });
      }
      if (user.departamentoId !== depto) {
        updateDepartamento(user.id, depto);
        registrar(eventoCambioDeDepartamento(user, user.departamentoId, depto, departamentos));
      }
      mostrarToast({ tipo: 'exito', mensaje: `${user.nombre} actualizado`, descripcion: 'Los cambios quedaron en su historial.' });
    } else {
      const nuevo = inviteUser({
        tenantId,
        nombre: nombre.trim(),
        email: email.trim(),
        role,
        plantIds,
        departamentoId: depto,
      });
      registrar(eventoUsuarioInvitado(nuevo));
      mostrarToast({
        tipo: 'exito',
        mensaje: `Invitación creada para ${nuevo.nombre}`,
        descripcion: 'Aparecerá como "Invitado" hasta que ingrese por primera vez.',
      });
    }
    onOpenChange(false);
  }

  return (
    <Dialog.Root open={open} onOpenChange={(next) => { onOpenChange(next); if (!next) resetForm(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-6 shadow-lg">
          <div className="flex items-start justify-between">
            <Dialog.Title className="text-lg font-semibold text-slate-900">
              {esEdicion ? `Editar a ${user?.nombre}` : 'Invitar usuario'}
            </Dialog.Title>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4" noValidate>
            {!esEdicion && (
              <>
                <FormField label="Nombre" htmlFor={`${formId}-nombre`} required error={errors.nombre}>
                  <Input id={`${formId}-nombre`} value={nombre} invalid={!!errors.nombre} onChange={(e) => setNombre(e.target.value)} />
                </FormField>
                <FormField label="Correo" htmlFor={`${formId}-email`} required error={errors.email}>
                  <Input id={`${formId}-email`} type="email" value={email} invalid={!!errors.email} onChange={(e) => setEmail(e.target.value)} />
                </FormField>
              </>
            )}

            <FormField label="Rol" htmlFor={`${formId}-rol`} hint={ROLE_DESCRIPTION[role]}>
              <select
                id={`${formId}-rol`}
                className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
                value={role}
                onChange={(e) => setRole(e.target.value as AssignableRole)}
              >
                {rolesDisponibles.map((r) => (
                  <option key={r} value={r}>
                    {ROLE_LABEL[r]}
                  </option>
                ))}
              </select>
            </FormField>

            {/* El cargo es distinto del rol: el rol define qué puede hacer en
                el sistema, el cargo qué responsabilidades tiene en la empresa.
                Es lo que se revisa en una auditoría de competencia (ISO 9001 §7.2). */}
            <FormField
              label="Cargo en la empresa"
              htmlFor={`${formId}-cargo`}
              hint="Distinto del rol del sistema. Se usa en auditorías de competencia."
            >
              <Input
                id={`${formId}-cargo`}
                value={cargo}
                onChange={(e) => setCargo(e.target.value)}
                placeholder="Ej: Jefe de Medio Ambiente"
              />
            </FormField>

            <fieldset className="flex flex-col gap-2">
              <legend className="text-sm font-medium text-slate-700">Plantas asignadas</legend>
              {plants.map((p) => (
                <label key={p.id} className="flex items-center gap-2 text-sm text-slate-700">
                  <input type="checkbox" checked={plantIds.includes(p.id)} onChange={() => togglePlant(p.id)} className="h-4 w-4" />
                  {p.nombre}
                </label>
              ))}
            </fieldset>

            {role === 'usuario_interno' && (
              <FormField label="Departamento" htmlFor={`${formId}-depto`} required error={errors.departamentoId}>
                <select
                  id={`${formId}-depto`}
                  className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
                  value={departamentoId}
                  onChange={(e) => setDepartamentoId(e.target.value)}
                >
                  <option value="">Selecciona un departamento</option>
                  {departamentos.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.nombre}
                    </option>
                  ))}
                </select>
              </FormField>
            )}

            <div className="mt-2 flex justify-end gap-2">
              <Dialog.Close asChild>
                <Button type="button" variant="secondary">Cancelar</Button>
              </Dialog.Close>
              <Button type="submit">{esEdicion ? 'Guardar cambios' : 'Enviar invitación'}</Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
