import Link from 'next/link';
import { SignUp } from '@clerk/nextjs';
import { CLERK_HABILITADO } from '@/lib/clerk-config';

/**
 * Registro. Existe porque Clerk lo enlaza desde el login, pero **no es el
 * camino de alta previsto**: RF-03 dice que al usuario lo registra el Admin
 * Empresa, no la persona por su cuenta.
 *
 * Si el equipo deshabilita el signup público en Clerk (decisión abierta #4 de
 * la propuesta), esta pantalla queda inalcanzable y no molesta. Mientras tanto
 * el aviso deja claro que hace falta que alguien lo asocie a una empresa.
 */
export default function SignUpPage() {
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

  return (
    <div className="flex flex-col items-center gap-4">
      <SignUp forceRedirectUrl="/dashboard" />
      <p className="max-w-sm text-center text-xs text-slate-500">
        Crear la cuenta no da acceso por sí solo: un administrador de tu empresa
        debe asociarte a ella antes de que puedas ver sus datos.
      </p>
    </div>
  );
}
