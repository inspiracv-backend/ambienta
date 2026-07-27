'use client';

import { useId, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { Laptop, Settings2, Smartphone } from 'lucide-react';
import { Avatar, Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { ROLE_LABEL } from '@/lib/roles';
import type { UserProfileViewProps } from './UserProfileView.types';

interface SesionMock {
  id: string;
  dispositivo: string;
  ubicacion: string;
  esActual: boolean;
}

const SESIONES_INICIALES: SesionMock[] = [
  { id: 'sesion-actual', dispositivo: 'Chrome · Windows', ubicacion: 'Santiago, Chile', esActual: true },
  { id: 'sesion-movil', dispositivo: 'App móvil · Android', ubicacion: 'Santiago, Chile', esActual: false },
];

/**
 * S-42 Perfil de Usuario. "Preferencias" enlaza a la configuración de
 * notificaciones ya existente (S-32, Sección J) en vez de duplicarla (H4).
 * Cambio de clave y sesiones activas son mock — no hay backend de auth real
 * (ver gaps en seccion-n-usuarios-roles-perfil.md).
 */
export function UserProfileView({ user, tenantNombre, onUpdateNombre }: UserProfileViewProps) {
  const formId = useId();

  const [nombre, setNombre] = useState(user.nombre);
  const [nombreGuardado, setNombreGuardado] = useState(false);

  const [claveNueva, setClaveNueva] = useState('');
  const [claveConfirmar, setClaveConfirmar] = useState('');
  const [errorClave, setErrorClave] = useState('');
  const [claveGuardada, setClaveGuardada] = useState(false);

  const [sesiones, setSesiones] = useState(SESIONES_INICIALES);

  function handleGuardarNombre(e: FormEvent) {
    e.preventDefault();
    if (!nombre.trim()) return;
    onUpdateNombre(nombre.trim());
    setNombreGuardado(true);
  }

  function handleCambiarClave(e: FormEvent) {
    e.preventDefault();
    setClaveGuardada(false);
    if (claveNueva.length < 8) {
      setErrorClave('La clave debe tener al menos 8 caracteres.');
      return;
    }
    if (claveNueva !== claveConfirmar) {
      setErrorClave('Las claves no coinciden.');
      return;
    }
    setErrorClave('');
    setClaveNueva('');
    setClaveConfirmar('');
    setClaveGuardada(true);
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div className="flex items-center gap-3">
        <Avatar nombre={user.nombre} avatarUrl={user.avatarUrl} size="md" />
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{user.nombre}</h1>
          <p className="text-sm text-slate-500">{ROLE_LABEL[user.role]} · {tenantNombre}</p>
        </div>
      </div>

      <section className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-base font-semibold text-slate-900">Datos personales</h2>
        <form onSubmit={handleGuardarNombre} className="flex flex-col gap-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField label="Nombre" htmlFor={`${formId}-nombre`}>
              <Input
                id={`${formId}-nombre`}
                value={nombre}
                onChange={(e) => { setNombre(e.target.value); setNombreGuardado(false); }}
              />
            </FormField>
            <FormField label="Correo" htmlFor={`${formId}-email`}>
              <Input id={`${formId}-email`} value={user.email} disabled className="bg-slate-50 text-slate-500" />
            </FormField>
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit">Guardar cambios</Button>
            {nombreGuardado && <span className="text-sm text-semaforo-cumple">Guardado.</span>}
          </div>
        </form>
      </section>

      <section className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-1 text-base font-semibold text-slate-900">Cambiar contraseña</h2>
        <p className="mb-4 text-xs text-slate-500">
          Si ingresaste con Microsoft o Google, esto te permite seguir autenticándote con RUT + clave sin depender del proveedor externo (RF-06).
        </p>
        <form onSubmit={handleCambiarClave} className="flex flex-col gap-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField label="Clave nueva" htmlFor={`${formId}-clave-nueva`} error={errorClave || undefined}>
              <Input
                id={`${formId}-clave-nueva`}
                type="password"
                value={claveNueva}
                invalid={!!errorClave}
                onChange={(e) => { setClaveNueva(e.target.value); setClaveGuardada(false); }}
              />
            </FormField>
            <FormField label="Confirmar clave" htmlFor={`${formId}-clave-confirmar`}>
              <Input
                id={`${formId}-clave-confirmar`}
                type="password"
                value={claveConfirmar}
                invalid={!!errorClave}
                onChange={(e) => { setClaveConfirmar(e.target.value); setClaveGuardada(false); }}
              />
            </FormField>
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit">Actualizar clave</Button>
            {claveGuardada && <span className="text-sm text-semaforo-cumple">Clave actualizada.</span>}
          </div>
        </form>
      </section>

      <section className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-base font-semibold text-slate-900">Sesiones activas</h2>
        <ul className="flex flex-col gap-3">
          {sesiones.map((s) => {
            const SesionIcon = s.dispositivo.includes('móvil') ? Smartphone : Laptop;
            return (
              <li key={s.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-4 py-3 text-sm">
                <div className="flex items-center gap-3">
                  <SesionIcon className="h-4 w-4 text-slate-400" aria-hidden />
                  <div>
                    <p className="font-medium text-slate-800">
                      {s.dispositivo} {s.esActual && <span className="text-xs font-normal text-brand-600">(esta sesión)</span>}
                    </p>
                    <p className="text-xs text-slate-500">{s.ubicacion}</p>
                  </div>
                </div>
                {!s.esActual && (
                  <Button variant="secondary" size="md" onClick={() => setSesiones((prev) => prev.filter((x) => x.id !== s.id))}>
                    Cerrar sesión
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-1 text-base font-semibold text-slate-900">Preferencias</h2>
        <p className="mb-4 text-xs text-slate-500">Canales de notificación y anticipación de recordatorios.</p>
        <Link
          href="/notificaciones/configuracion"
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          <Settings2 className="h-4 w-4" aria-hidden />
          Configurar notificaciones
        </Link>
      </section>
    </div>
  );
}
