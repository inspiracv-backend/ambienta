'use client';

import type { ReactNode } from 'react';
import { useClerk, useUser } from '@clerk/nextjs';
import { SinEmpresaScreen } from '@/components/organisms/SinEmpresaScreen';
import { marcarSesionSinEmpresa, useSesionSinEmpresa } from '@/lib/sesion-sin-empresa';

/**
 * Muestra la pantalla de "cuenta sin empresa" en vez de la aplicación cuando la
 * API lo dijo. **Solo existe con Clerk**: sin proveedor no hay sesión que pueda
 * quedar sin empresa, y el modo de desarrollo no cambia en nada.
 */
export function SinEmpresaGate({ children }: { children: ReactNode }) {
  const sinEmpresa = useSesionSinEmpresa();
  const { signOut } = useClerk();
  const { user } = useUser();

  if (!sinEmpresa) return <>{children}</>;

  return (
    <SinEmpresaScreen
      correo={user?.primaryEmailAddress?.emailAddress ?? null}
      onCerrarSesion={async () => {
        await signOut();
        // Después de cerrar: la próxima cuenta que entre empieza sin la marca.
        marcarSesionSinEmpresa(false);
      }}
    />
  );
}
