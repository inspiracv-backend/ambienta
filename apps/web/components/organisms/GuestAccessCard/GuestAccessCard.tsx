'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useSession } from '@/lib/session';
import { mockUsers } from '@/mocks/users';

/** S-02 Acceso Cliente Invitado: RUT + clave, diseño limpio y mínimo. */
export function GuestAccessCard() {
  const router = useRouter();
  const { login } = useSession();
  const [rut, setRut] = useState('');
  const [clave, setClave] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!rut.trim() || !clave.trim()) {
      setError('Ingresa tu RUT y clave para continuar.');
      return;
    }

    setIsLoading(true);
    const guest = mockUsers.find((u) => u.role === 'cliente_invitado');

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

  return (
    <div className="w-full max-w-sm rounded-card border border-slate-200 bg-white p-8 shadow-sm">
      <h1 className="text-xl font-semibold text-slate-900">Acceso Cliente Invitado</h1>
      <p className="mt-1 text-sm text-slate-500">Ingresa con tu RUT y clave para gestionar tus solicitudes.</p>

      <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
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

      <p className="mt-6 text-center text-xs text-slate-400">
        ¿No tienes cuenta?{' '}
        <a href="/crear-ticket" className="font-medium text-brand-600 hover:underline">
          Crea una solicitud sin registrarte
        </a>
      </p>
    </div>
  );
}
