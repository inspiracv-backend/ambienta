'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { KeyRound, ShieldCheck } from 'lucide-react';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useSession } from '@/lib/session';
import {
  empresaDelEnlace,
  generarCredenciales,
  iniciarSesion,
  type CredencialGenerada,
} from '@/lib/acceso-invitado';
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
 *
 * **Hasta el 25-ago-2026 esta pantalla no hablaba con nadie.** Generaba el RUT
 * y la clave en el navegador con un `setTimeout` de medio segundo, y el login
 * aceptaba cualquier cosa que no estuviera vacía. Se veía funcionando: mostraba
 * credenciales de aspecto correcto y dejaba pasar. Pero nada de eso existía del
 * lado del servidor, así que **volver al día siguiente con esas credenciales no
 * habría servido de nada** — y ese es justamente el requisito (RF-07).
 *
 * Ahora las emite y las valida la API. Lo que se ve en pantalla es lo que hay
 * en la base.
 */
export function GuestAccessCard() {
  const router = useRouter();
  const { login } = useSession();
  const [modo, setModo] = useState<Modo>('inicio');
  const [credenciales, setCredenciales] = useState<CredencialGenerada | null>(null);
  // De qué empresa es este enlace. Sin esto no se puede emitir nada: elegir una
  // por omisión le daría a la persona acceso a una empresa que no es la suya.
  const empresaId = empresaDelEnlace();

  const [rut, setRut] = useState('');
  const [clave, setClave] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const guest = mockUsers.find((u) => u.role === 'cliente_invitado');

  async function handleGenerar() {
    if (!empresaId) {
      setError('Este enlace no indica de qué empresa es. Pídele el enlace correcto a tu contacto.');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      setCredenciales(await generarCredenciales(empresaId));
      setModo('generado');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo generar el acceso.');
    } finally {
      setIsLoading(false);
    }
  }

  async function handleContinuar() {
    // **Se inicia sesión con las credenciales recién emitidas.**
    //
    // Sin esto la persona llega a `/crear-ticket` con su RUT y su clave en
    // pantalla pero **sin token**, y el formulario cae al camino simulado: el
    // ticket no quedaría ligado a su credencial y no podría volver a
    // encontrarlo. Se veía bien y no servía para nada, que es el mismo fallo
    // que esta pantalla tenía entera.
    if (!credenciales || !empresaId) return;

    setIsLoading(true);
    try {
      await iniciarSesion(empresaId, credenciales.rut, credenciales.clave);
      if (guest) login(guest.id);
      router.push('/crear-ticket');
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Tu acceso se generó, pero no pudimos iniciar la sesión. Ingresa con tu RUT y clave.',
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function handleLoginSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!rut.trim() || !clave.trim()) {
      setError('Ingresa tu RUT y clave para continuar.');
      return;
    }
    if (!empresaId) {
      setError('Este enlace no indica de qué empresa es. Pídele el enlace correcto a tu contacto.');
      return;
    }

    setIsLoading(true);
    try {
      await iniciarSesion(empresaId, rut, clave);
      if (guest) login(guest.id);
      router.push('/crear-ticket');
    } catch {
      // **Un solo mensaje para todos los motivos**, igual que la API: decir si
      // el RUT existe le confirmaría a quien prueba al azar que ese RUT es
      // cliente de esta empresa.
      setError('No pudimos verificar tus credenciales. Revisa tu RUT y clave.');
    } finally {
      setIsLoading(false);
    }
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

        <p className="mt-3 text-xs text-slate-500">
          Válidas por {credenciales.dias_de_vigencia} días, hasta el{' '}
          {new Date(credenciales.valido_hasta).toLocaleDateString('es-CL')}.
        </p>

        <Button className="mt-6 w-full" isLoading={isLoading} onClick={handleContinuar}>
          Continuar a crear ticket
        </Button>

        {error && (
          <p role="alert" className="mt-3 text-sm text-red-600">
            {error}
          </p>
        )}
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

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-600">
          {error}
        </p>
      )}

      <p className="mt-6 text-center text-xs text-slate-400">
        ¿Ya tienes RUT y clave?{' '}
        <button type="button" onClick={() => setModo('login')} className="font-medium text-brand-600 hover:underline">
          Ingresa aquí
        </button>
      </p>
    </div>
  );
}
