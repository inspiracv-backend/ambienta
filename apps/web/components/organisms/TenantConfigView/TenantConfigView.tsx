'use client';

import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, Building2, Mail, Phone, X } from 'lucide-react';
import {
  MODULOS_PLATAFORMA,
  diasParaVencimiento,
  nombreDePais,
  type Certificacion,
  type ModuloPlataforma,
} from '@ambienta/shared';
import { CERTIFICACIONES } from '@ambienta/shared';
import { AccountBadge, Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useTenants } from '@/lib/tenants-store';
import { useToast } from '@/lib/toast-store';
import { MODULO_LABEL } from '@/lib/tenant-status';
import { cn } from '@/lib/utils';
import type { TenantConfigViewProps } from './TenantConfigView.types';

function nombreCertificacion(codigo: Certificacion): string {
  return CERTIFICACIONES.find((c) => c.codigo === codigo)?.nombre ?? codigo;
}

/**
 * S-37 Detalle/Configuración de Tenant.
 *
 * El Superadmin administra los campos de plataforma (límites, módulos,
 * estado); la información de negocio es de solo lectura — no edita contenido
 * de tenants (CLAUDE.md).
 *
 * La suspensión vive aquí, en una **zona de riesgo** al final, y no en la fila
 * del listado: suspender deja fuera a todos los usuarios de la empresa y no
 * debe estar a un clic de distancia del enlace para ver el detalle.
 */
export function TenantConfigView({ tenant: tenantProp, userCount }: TenantConfigViewProps) {
  const { tenants, setLimiteUsuarios, setModulosActivos, setEstado } = useTenants();
  const { mostrarToast } = useToast();
  const tenant = tenants.find((t) => t.id === tenantProp.id) ?? tenantProp;

  const [limite, setLimite] = useState(tenant.suscripcion.limiteUsuarios);
  const [modulos, setModulos] = useState<Set<ModuloPlataforma>>(new Set(tenant.modulosActivos));
  const [confirmacionSuspender, setConfirmacionSuspender] = useState('');
  const [isSuspenderOpen, setIsSuspenderOpen] = useState(false);

  const dias = diasParaVencimiento(tenant.suscripcion);

  function toggleModulo(m: ModuloPlataforma) {
    setModulos((prev) => {
      const next = new Set(prev);
      if (next.has(m)) next.delete(m);
      else next.add(m);
      return next;
    });
  }

  function handleGuardar() {
    setLimiteUsuarios(tenant.id, limite);
    setModulosActivos(tenant.id, Array.from(modulos));
    mostrarToast({
      tipo: 'exito',
      mensaje: 'Configuración guardada',
      descripcion: 'Los cambios quedaron registrados en el historial.',
    });
  }

  function handleSuspender() {
    setEstado(tenant.id, 'suspendido');
    setIsSuspenderOpen(false);
    setConfirmacionSuspender('');
    mostrarToast({
      tipo: 'info',
      mensaje: `${tenant.nombre} fue suspendida`,
      descripcion: 'Sus usuarios no podrán ingresar hasta reactivarla.',
      onUndo: () => setEstado(tenant.id, 'activo'),
    });
  }

  function handleReactivar() {
    setEstado(tenant.id, 'activo');
    mostrarToast({
      tipo: 'exito',
      mensaje: `${tenant.nombre} fue reactivada`,
      descripcion: 'Sus usuarios pueden volver a ingresar.',
    });
  }

  return (
    <div className="flex flex-col gap-6">
      {/* ── Información de la empresa (solo lectura) ──────────────────── */}
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            {tenant.logoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={tenant.logoUrl} alt={tenant.nombre} className="h-12 w-12 rounded-lg object-contain" />
            ) : (
              <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-100 text-slate-400">
                <Building2 className="h-6 w-6" aria-hidden />
              </span>
            )}
            <div>
              <h1 className="text-xl font-semibold text-slate-900">{tenant.nombre}</h1>
              <p className="mt-0.5 text-sm text-slate-500">
                {tenant.identificacion.tipo} {tenant.identificacion.numero} · {nombreDePais(tenant.pais)} ·{' '}
                {tenant.esGestor ? 'Gestor' : tenant.sector}
              </p>
              <p className="mt-0.5 text-xs text-slate-500">
                {tenant.plants.length} planta(s) · {userCount} usuario(s)
                {tenant.numeroTrabajadores ? ` · ${tenant.numeroTrabajadores} trabajadores` : ''}
              </p>
            </div>
          </div>
          <AccountBadge estado={tenant.estado} />
        </div>

        {tenant.certificaciones.length > 0 && (
          <div className="mt-4 border-t border-slate-100 pt-3">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Sistemas certificados</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {tenant.certificaciones.map((c) => (
                <span key={c} className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                  {nombreCertificacion(c)}
                </span>
              ))}
            </div>
          </div>
        )}

        {tenant.contactoComercial && (
          <div className="mt-4 border-t border-slate-100 pt-3">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Contacto comercial</p>
            <p className="mt-1 text-sm text-slate-800">
              {tenant.contactoComercial.nombre}
              {tenant.contactoComercial.cargo && (
                <span className="text-slate-500"> · {tenant.contactoComercial.cargo}</span>
              )}
            </p>
            <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
              {tenant.contactoComercial.email && (
                <span className="inline-flex items-center gap-1">
                  <Mail className="h-3.5 w-3.5" aria-hidden /> {tenant.contactoComercial.email}
                </span>
              )}
              {tenant.contactoComercial.telefono && (
                <span className="inline-flex items-center gap-1">
                  <Phone className="h-3.5 w-3.5" aria-hidden /> {tenant.contactoComercial.telefono}
                </span>
              )}
            </div>
            {tenant.notasComerciales && (
              <p className="mt-2 border-l-2 border-slate-200 pl-2 text-xs italic text-slate-600">
                {tenant.notasComerciales}
              </p>
            )}
          </div>
        )}
      </div>

      {/* ── Suscripción ───────────────────────────────────────────────── */}
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold text-slate-700">Suscripción</h2>
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              tenant.suscripcion.plan === 'demo'
                ? 'bg-semaforo-parcial-bg text-semaforo-parcial'
                : 'bg-slate-100 text-slate-600',
            )}
          >
            {tenant.suscripcion.plan === 'demo' ? 'Demo' : 'Contrato'}
          </span>
        </div>
        <p
          className={cn(
            'mt-1 text-sm',
            dias < 0 ? 'font-semibold text-semaforo-no-cumple' : dias <= 15 ? 'font-medium text-semaforo-parcial' : 'text-slate-500',
          )}
        >
          {dias < 0
            ? `Venció hace ${Math.abs(dias)} días`
            : dias === 0
              ? 'Vence hoy'
              : `Vigente por ${dias} días más`}
        </p>

        <div className="mt-4">
          <FormField label="Máximo de usuarios permitidos" htmlFor="limite-usuarios" hint={`Actualmente hay ${userCount} en uso`}>
            <Input
              id="limite-usuarios"
              type="number"
              min={userCount}
              value={limite}
              onChange={(e) => setLimite(Number(e.target.value))}
              className="max-w-[160px]"
            />
          </FormField>
        </div>
      </div>

      {/* ── Módulos ───────────────────────────────────────────────────── */}
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Módulos activos</h2>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {MODULOS_PLATAFORMA.map((m) => (
            <label key={m} className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={modulos.has(m)} onChange={() => toggleModulo(m)} className="h-4 w-4" />
              {MODULO_LABEL[m]}
            </label>
          ))}
        </div>
      </div>

      <div>
        <Button onClick={handleGuardar}>Guardar configuración</Button>
      </div>

      {/* ── Zona de riesgo ────────────────────────────────────────────── */}
      <section
        aria-labelledby="zona-riesgo"
        className="rounded-card border border-semaforo-no-cumple/30 bg-semaforo-no-cumple-bg/40 p-6"
      >
        <h2 id="zona-riesgo" className="flex items-center gap-2 text-sm font-semibold text-semaforo-no-cumple">
          <AlertTriangle className="h-4 w-4" aria-hidden />
          Zona de riesgo
        </h2>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-4">
          <div className="min-w-0">
            <p className="text-sm font-medium text-slate-800">
              {tenant.estado === 'activo' ? 'Suspender la empresa' : 'Reactivar la empresa'}
            </p>
            <p className="mt-0.5 text-xs text-slate-500">
              {tenant.estado === 'activo'
                ? `Los ${userCount} usuarios de ${tenant.nombre} perderán acceso de inmediato. Los datos se conservan.`
                : 'Sus usuarios podrán volver a ingresar de inmediato.'}
            </p>
          </div>
          {tenant.estado === 'activo' ? (
            <Button variant="danger" size="md" onClick={() => setIsSuspenderOpen(true)}>
              Suspender
            </Button>
          ) : (
            <Button variant="secondary" size="md" onClick={handleReactivar}>
              Reactivar
            </Button>
          )}
        </div>
      </section>

      {/* Confirmación por escrito: un clic de más no basta cuando la acción
          deja fuera a una empresa entera. */}
      <Dialog.Root
        open={isSuspenderOpen}
        onOpenChange={(open) => {
          setIsSuspenderOpen(open);
          if (!open) setConfirmacionSuspender('');
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-6 shadow-lg">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2 text-semaforo-no-cumple">
                <AlertTriangle className="h-5 w-5" aria-hidden />
                <Dialog.Title className="text-lg font-semibold text-slate-900">Suspender empresa</Dialog.Title>
              </div>
              <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
                <X className="h-5 w-5" aria-hidden />
              </Dialog.Close>
            </div>

            <Dialog.Description className="mt-3 text-sm text-slate-600">
              Los <strong>{userCount} usuarios</strong> de {tenant.nombre} perderán acceso de inmediato. Los datos se
              conservan y la acción es reversible.
            </Dialog.Description>

            <div className="mt-4">
              <FormField
                label={`Escribe "${tenant.nombre}" para confirmar`}
                htmlFor="confirmar-suspension"
              >
                <Input
                  id="confirmar-suspension"
                  value={confirmacionSuspender}
                  onChange={(e) => setConfirmacionSuspender(e.target.value)}
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
                disabled={confirmacionSuspender.trim() !== tenant.nombre}
                onClick={handleSuspender}
              >
                Suspender empresa
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
