import {
  AccesoInvitadoAviso,
  DevRoleSwitcher,
  LoginCard,
  PestanasDeIngreso,
} from '@/components/organisms';
import { CLERK_HABILITADO } from '@/lib/clerk-config';

/**
 * S-01. Con Clerk configurado, el login real; sin él, el de desarrollo.
 *
 * `LoginCard` es el mock de los botones SSO: se muestra solo en el camino sin
 * Clerk. Dejarlo junto a `<SignIn />` daría dos formularios de ingreso en la
 * misma pantalla, uno de ellos falso.
 *
 * El aviso de invitado va **en los dos caminos**: es el acceso de otro rol
 * (RF-02), no una variante del ingreso con cuenta. Venía dentro de `LoginCard`
 * y al montar `<SignIn />` en su lugar quedó sin entrada visible.
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
    <div className="mx-auto w-full max-w-[25rem]">
      <PestanasDeIngreso />
      <AccesoInvitadoAviso />
    </div>
  );
}
