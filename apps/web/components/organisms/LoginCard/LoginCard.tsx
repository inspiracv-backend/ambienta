'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { SSOButton } from '@/components/molecules';
import { useSession } from '@/lib/session';
import { rutaInicialParaRol } from '@/lib/navigation';
import { mockUsers } from '@/mocks/users';

/**
 * S-01 Login. No hay email/contraseña genérico para usuarios de empresa
 * (según prompt de diseño) — solo SSO. Como no existe backend de auth real,
 * cada botón SSO "inicia sesión" con un usuario mock representativo del
 * proveedor, para poder demostrar el flujo end-to-end.
 * Integración real: reemplazar por OAuth Microsoft Entra ID / Google Identity + JWT.
 */
export function LoginCard() {
  const router = useRouter();
  const { login } = useSession();
  const [loadingProvider, setLoadingProvider] = useState<'microsoft' | 'google' | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleSSO(provider: 'microsoft' | 'google') {
    setError(null);
    setLoadingProvider(provider);

    const mockUser = mockUsers.find((u) => u.role === 'admin_empresa') ?? mockUsers[0];

    setTimeout(() => {
      if (!mockUser) {
        setError('No pudimos verificar tus credenciales. Intenta nuevamente.');
        setLoadingProvider(null);
        return;
      }
      login(mockUser.id);
      router.push(rutaInicialParaRol(mockUser.role));
    }, 600);
  }

  return (
    <div className="w-full max-w-sm rounded-card border border-slate-200 bg-white p-8 shadow-sm">
      <h1 className="text-xl font-semibold text-slate-900">Ambienta</h1>
      <p className="mt-1 text-sm text-slate-500">
        Cumplimiento ambiental, sin el caos. Ingresa con tu cuenta de empresa.
      </p>

      <div className="mt-6 flex flex-col gap-3">
        <SSOButton
          provider="microsoft"
          onClick={() => handleSSO('microsoft')}
          isLoading={loadingProvider === 'microsoft'}
        />
        <SSOButton
          provider="google"
          onClick={() => handleSSO('google')}
          isLoading={loadingProvider === 'google'}
        />
      </div>

      {error && (
        <p role="alert" className="mt-4 text-sm font-medium text-red-600">
          {error}
        </p>
      )}

      <p className="mt-6 text-center text-xs text-slate-400">
        ¿Eres cliente invitado?{' '}
        <a href="/acceso-invitado" className="font-medium text-brand-600 hover:underline">
          Ingresa con RUT
        </a>
      </p>
    </div>
  );
}
