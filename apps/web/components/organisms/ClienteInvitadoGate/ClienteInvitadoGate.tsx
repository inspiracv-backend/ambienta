'use client';

import { useEffect, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';

/**
 * RF-05: el rol Cliente/Invitado es semi-público con acceso limitado
 * (solo tickets) — nunca debe llegar al contenido de negocio del tenant
 * (Matriz Legal, Obligaciones, etc.), aunque nada se lo impidiera antes a
 * nivel de ruta. Organismo cross-cutting (mismo criterio que
 * `PerfilEmpresaGate`, para no meter lógica de negocio en `DashboardLayout`).
 * El RBAC real (que bloquearía esto también en la API) no existe todavía
 * — este gate es solo la capa de UX del frontend.
 */
export function ClienteInvitadoGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { user } = useSession();

  const esClienteInvitado = user?.role === 'cliente_invitado';

  useEffect(() => {
    if (esClienteInvitado) router.replace('/crear-ticket');
  }, [esClienteInvitado, router]);

  if (esClienteInvitado) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner label="Redirigiendo a tus solicitudes" />
      </div>
    );
  }

  return <>{children}</>;
}
