import { SignIn } from '@clerk/nextjs';
import { DevRoleSwitcher, LoginCard } from '@/components/organisms';
import { CLERK_HABILITADO } from '@/lib/clerk-config';

/**
 * S-01. Con Clerk configurado, el login real; sin él, el de desarrollo.
 *
 * `LoginCard` es el mock de los botones SSO: se muestra solo en el camino sin
 * Clerk. Dejarlo junto a `<SignIn />` daría dos formularios de ingreso en la
 * misma pantalla, uno de ellos falso.
 */
export default function LoginPage() {
  if (!CLERK_HABILITADO) {
    return (
      <>
        <LoginCard />
        {/* Herramienta de desarrollo: se elimina del bundle de producción. */}
        <DevRoleSwitcher />
      </>
    );
  }

  return (
    <SignIn
      forceRedirectUrl="/dashboard"
      appearance={{ elements: { rootBox: 'mx-auto' } }}
    />
  );
}
