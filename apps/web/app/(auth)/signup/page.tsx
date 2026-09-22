import Link from 'next/link';
import { SignUp } from '@clerk/nextjs';
import { CLERK_HABILITADO } from '@/lib/clerk-config';

/**
 * Registro. **Solo para aceptar una invitación** (RF-03, decisión 5 del 21-sep:
 * el alta la hace la empresa, no la persona).
 *
 * No se retira la página: la invitación de Clerk no fija `redirect_url`, así que
 * su enlace puede volver acá con `__clerk_ticket`, y sin el formulario la
 * persona invitada no podría crear su cuenta. Lo que se retira es el registro
 * **sin invitación**: hasta el 22-sep esta página montaba `<SignUp />` para
 * cualquiera, y con el registro público abierto en Clerk cualquiera con un
 * correo quedaba dentro del sistema.
 *
 * La barrera de verdad es el modo restringido de Clerk (se configura en su
 * panel, del lado de la cuenta). Esta pantalla hace que el sitio diga lo mismo.
 */
export default function SignUpPage({ searchParams }: { searchParams?: { __clerk_ticket?: string } }) {
  if (!CLERK_HABILITADO) {
    return (
      <div className="mx-auto max-w-md rounded-card border border-slate-200 bg-white p-6 text-center">
        <p className="text-sm text-slate-600">
          El registro necesita el proveedor de identidad configurado.
        </p>
        <Link href="/login" className="mt-3 inline-block text-sm text-brand-700 hover:underline">
          Volver al inicio de sesión
        </Link>
      </div>
    );
  }

  if (!searchParams?.__clerk_ticket) {
    return (
      <div className="mx-auto max-w-md rounded-card border border-slate-200 bg-white p-6 text-center">
        <h1 className="text-base font-semibold text-slate-900">El acceso lo habilita tu empresa</h1>
        <p className="mt-2 text-sm text-slate-600">
          En Ambienta no se crean cuentas por cuenta propia. Pídele a un administrador de tu
          empresa que te invite: te llegará un correo con el enlace para crear tu cuenta.
        </p>
        <Link href="/login" className="mt-4 inline-block text-sm text-brand-700 hover:underline">
          Volver al inicio de sesión
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4">
      <SignUp forceRedirectUrl="/dashboard" />
      <p className="max-w-sm text-center text-xs text-slate-500">
        Estás aceptando la invitación de tu empresa: al crear la cuenta entras con ella.
      </p>
    </div>
  );
}
