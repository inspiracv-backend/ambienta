'use client';

import { ClerkProvider } from '@clerk/nextjs';
import { esES } from '@clerk/localizations';
import { CLERK_HABILITADO } from '@/lib/clerk-config';
import { ClerkApiBridge } from './ClerkApiBridge';

/**
 * Envuelve la app en el proveedor de identidad, pero solo si hay uno.
 *
 * `ClerkProvider` sin llave lanza `Missing publishableKey` y la aplicación no
 * monta. Ponerlo incondicional dejaría sin arrancar a cualquiera que clone el
 * repo sin cuenta de Clerk — que es justo el caso que el modo de desarrollo
 * tiene que cubrir.
 *
 * Es un componente de cliente porque `ClerkProvider` lo es; el layout raíz es
 * de servidor y no puede tener el condicional dentro.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  if (!CLERK_HABILITADO) return <>{children}</>;

  return (
    <ClerkProvider
      localization={esES}
      signInUrl="/login"
      signUpUrl="/signup"
      afterSignOutUrl="/login"
    >
      <ClerkApiBridge />
      {children}
    </ClerkProvider>
  );
}
