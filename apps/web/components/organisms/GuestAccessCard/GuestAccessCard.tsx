'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { KeyRound, ShieldCheck } from 'lucide-react';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useSession } from '@/lib/session';
import { generateDynamicPassword, generateMockRut } from '@/lib/rut';
import { mockUsers } from '@/mocks/users';

type Modo = 'inicio' | 'generado' | 'login';

/**
 * S-02 Acceso Cliente Invitado (rediseñado en v1.7, Decisión cerrada #11):
 * el "link especial" es esta misma pantalla — al usarla el sistema asigna
 * automáticamente RUT + clave dinámica (RF-02, RF-07), sin que el invitado
 * escriba nada. Se conserva el login manual RUT+clave (RF-01) como camino
 * secundario para quien ya tiene credenciales de una visita anterior.
 * RF-03 (Admin Empresa registra al invitado como usuario permanente) queda
 * documentado como gap — depende de la gestión de usuarios de la Sección N,
 * aún no construida.
 */
export function GuestAccessCard() {
  const router = useRouter();
  const { login } = useSession();
  const [modo, setModo] = useState<Modo>('inicio');
  const [credenciales, setCredenciales] = useState<{ rut: string; clave: string } | null>(null);

  const [rut, setRut] = useState('');
  const [clave, setClave] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const guest = mockUsers.find((u) => u.role === 'cliente_invitado');

  function handleGenerar() {
    setIsLoading(true);
    setTimeout(() => {
      setCredenciales({ rut: generateMockRut(), clave: generateDynamicPassword() });
      setIsLoading(false);
      setModo('generado');
    }, 500);
  }

  function handleContinuar() {
    if (guest) login(guest.id);
    router.push('/crear-ticket');
  }

  function handleLoginSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!rut.trim() || !clave.trim()) {
      setError('Ingresa tu RUT y clave para continuar.');
      return;
    }

    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      if (!guest) {
        setError('No pudimos verificar tus credenciales. Revisa tu RUT y clave.');
        return;
      }
      login(guest.id);
      router.push('/crear-ticket');
    }, 500);
  }

  if (modo === 'generado' && credenciales) {
    return (
      <div className="w-full max-w-sm rounded-card border border-slate-200 bg-white p-8 shadow-sm">
        <ShieldCheck className="h-8 w-8 text-brand-600" aria-hidden />
        <h1 className="mt-3 text-xl font-semibold text-slate-900">Tu acceso está listo</h1>
        <p className="mt-1 text-sm text-slate-500">
          Guarda estos datos: los necesitarás para volver a consultar tu solicitud.
        </p>

        <dl className="mt-5 flex flex-col gap-3 rounded-lg bg-brand-50 p-4 text-sm">
          <div className="flex items-center justify-between">
            <dt className="font-medium text-slate-600">RUT</dt>
            <dd className="font-mono text-slate-900">{credenciales.rut}</dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="font-medium text-slate-600">Clave</dt>
            <dd className="font-mono text-slate-900">{credenciales.clave}</dd>
          </div>
        </dl>

        <Button className="mt-6 w-full" onClick={handleContinuar}>
          Continuar a crear ticket
        </Button>
      </div>
    );
  }

  if (modo === 'login') {
    return (
      <div className="w-full max-w-sm rounded-card border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-900">Ya tengo RUT y clave</h1>
        <p className="mt-1 text-sm text-slate-500">Ingresa las credenciales que se te asignaron en tu solicitud anterior.</p>

        <form className="mt-6 flex flex-col gap-4" onSubmit={handleLoginSubmit} noValidate>
          <FormField label="RUT" htmlFor="rut" required>
            <Input id="rut" name="rut" placeholder="12.345.678-9" value={rut} onChange={(e) => setRut(e.target.value)} />
          </FormField>
          <FormField label="Clave" htmlFor="clave" required error={error ?? undefined}>
            <Input id="clave" name="clave" type="password" value={clave} onChange={(e) => setClave(e.target.value)} invalid={!!error} />
          </FormField>
          <Button type="submit" isLoading={isLoading} className="w-full">
            Ingresar
          </Button>
        </form>

        <button
          type="button"
          onClick={() => setModo('inicio')}
          className="mt-6 w-full text-center text-xs font-medium text-brand-600 hover:underline"
        >
          Volver
        </button>
      </div>
    );
  }

  return (
    <div className="w-full max-w-sm rounded-card border border-slate-200 bg-white p-8 shadow-sm">
      <h1 className="text-xl font-semibold text-slate-900">Acceso Cliente Invitado</h1>
      <p className="mt-1 text-sm text-slate-500">
        Genera un acceso temporal para crear y hacer seguimiento a tus solicitudes — no necesitas cuenta previa.
      </p>

      <Button
        icon={<KeyRound className="h-4 w-4" aria-hidden />}
        isLoading={isLoading}
        className="mt-6 w-full"
        onClick={handleGenerar}
      >
        Generar mi acceso
      </Button>

      <p className="mt-6 text-center text-xs text-slate-400">
        ¿Ya tienes RUT y clave?{' '}
        <button type="button" onClick={() => setModo('login')} className="font-medium text-brand-600 hover:underline">
          Ingresa aquí
        </button>
      </p>
    </div>
  );
}
