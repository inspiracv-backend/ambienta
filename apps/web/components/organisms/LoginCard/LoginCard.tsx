'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertCircle, ShieldCheck } from 'lucide-react';
import { BrandMark } from '@/components/atoms';
import { SSOButton } from '@/components/molecules';
import { AccesoInvitadoAviso } from '@/components/organisms/AccesoInvitadoAviso';
import { useSession } from '@/lib/session';
import { rutaInicialParaRol } from '@/lib/navigation';
import { mockUsers } from '@/mocks/users';

type Proveedor = 'microsoft' | 'google';

/**
 * S-01 Login.
 *
 * No hay email/contraseña genérico para usuarios de empresa (prompt de
 * diseño): solo SSO. Como no existe backend de auth real, cada botón inicia
 * sesión con un usuario mock representativo para poder demostrar el flujo
 * end-to-end. Integración real: OAuth Microsoft Entra ID / Google Identity +
 * JWT vía apps/api.
 *
 * Decisiones del rediseño (antes eran dos botones sueltos sin contexto):
 *
 * - **Se dice qué es Ambienta.** Quien llega por un link enviado por su jefatura
 *   no necesariamente sabe a qué sistema está entrando; sin contexto el login
 *   parece phishing.
 * - **Los dos caminos están separados visualmente.** El acceso de empresa y el
 *   de Cliente Invitado son flujos distintos para personas distintas (A1/A2 vs
 *   A3). Antes el segundo era una línea de 12px al pie que se leía como nota
 *   al margen, cuando en realidad es la puerta de entrada de todo un rol.
 * - **El invitado sabe si le corresponde antes de hacer clic**, en vez de
 *   descubrirlo entrando (H6: reconocer mejor que recordar).
 */
export function LoginCard() {
  const router = useRouter();
  const { login } = useSession();
  const [cargando, setCargando] = useState<Proveedor | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleSSO(provider: Proveedor) {
    setError(null);
    setCargando(provider);

    const mockUser = mockUsers.find((u) => u.role === 'admin_empresa') ?? mockUsers[0];

    setTimeout(() => {
      if (!mockUser) {
        setError('No pudimos verificar tus credenciales. Intenta nuevamente en unos segundos.');
        setCargando(null);
        return;
      }
      login(mockUser.id);
      router.push(rutaInicialParaRol(mockUser.role));
    }, 600);
  }

  return (
    <div className="w-full max-w-sm">
      <div className="flex flex-col items-center text-center">
        <BrandMark className="h-11 w-11" />
        <h1 className="mt-4 text-2xl font-semibold tracking-tight text-slate-900">Ambienta</h1>
        <p className="mt-1.5 text-sm leading-relaxed text-slate-500">
          Gestiona vencimientos, obligaciones y evidencias de cumplimiento ambiental en un solo lugar.
        </p>
      </div>

      <div className="mt-8 rounded-card border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Ingresa con tu cuenta de empresa</h2>
        <p className="mt-1 text-xs text-slate-500">Usa la misma cuenta con la que accedes al correo corporativo.</p>

        <div className="mt-4 flex flex-col gap-2.5">
          <SSOButton
            provider="microsoft"
            recomendado
            onClick={() => handleSSO('microsoft')}
            isLoading={cargando === 'microsoft'}
            disabled={cargando !== null}
          />
          <SSOButton
            provider="google"
            onClick={() => handleSSO('google')}
            isLoading={cargando === 'google'}
            disabled={cargando !== null}
          />
        </div>

        {error && (
          <p role="alert" className="mt-4 flex items-start gap-2 rounded-lg bg-semaforo-no-cumple-bg p-3 text-sm text-semaforo-no-cumple">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <span>{error}</span>
          </p>
        )}

        <p className="mt-4 flex items-start gap-1.5 text-xs text-slate-400">
          <ShieldCheck className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>No almacenamos tu contraseña: la autenticación la realiza tu proveedor.</span>
        </p>
      </div>

      <AccesoInvitadoAviso />
    </div>
  );
}
