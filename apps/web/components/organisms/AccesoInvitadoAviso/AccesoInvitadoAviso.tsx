import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

/**
 * El camino del Cliente Invitado (A3, RF-02): es otro rol, no una nota al pie.
 *
 * Se extrajo de `LoginCard` porque tiene que aparecer en las dos pantallas de
 * ingreso —la de Clerk y la de desarrollo— y `LoginCard` solo se muestra en la
 * segunda. Al montar `<SignIn />` en su lugar, este bloque desaparecio y el
 * acceso de invitado quedo sin ninguna entrada visible: seguia funcionando en
 * `/acceso-invitado`, pero habia que saberse la URL.
 *
 * RF-02 dice que el invitado **no necesita cuenta**, asi que este camino no
 * pasa por Clerk ni debe hacerlo.
 */
export function AccesoInvitadoAviso() {
  return (
    <div className="mt-4 rounded-card border border-slate-200 bg-slate-50/70 p-4">
      <h2 className="text-sm font-semibold text-slate-800">¿Vienes a hacer una solicitud?</h2>
      <p className="mt-1 text-xs leading-relaxed text-slate-500">
        Si eres cliente o contratista y solo necesitas enviar un requerimiento, no hace falta que tengas cuenta.
      </p>
      <Link
        href="/acceso-invitado"
        className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
      >
        Acceder como invitado
        <ArrowRight className="h-4 w-4" aria-hidden />
      </Link>
    </div>
  );
}
