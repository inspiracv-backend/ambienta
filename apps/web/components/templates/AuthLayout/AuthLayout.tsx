import type { ReactNode } from 'react';

/**
 * Layout centrado con tarjeta, fondo claro, mucho aire (S-01/S-02/S-03). Sin
 * lógica de negocio ni fetching.
 *
 * El centrado usa `m-auto` sobre el contenedor interno en vez de
 * `items-center` en el flex externo: cuando el contenido supera el alto de la
 * ventana, `items-center` recorta la parte de arriba y no se puede desplazar
 * hasta ella, mientras que `m-auto` la deja accesible.
 */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen justify-center bg-slate-50 px-4 py-8">
      <div className="m-auto flex flex-col items-center">{children}</div>
    </main>
  );
}
