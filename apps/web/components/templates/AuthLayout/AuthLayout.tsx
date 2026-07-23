import type { ReactNode } from 'react';

/** Layout centrado con tarjeta, fondo claro, mucho aire (S-01/S-02/S-03). Sin lógica de negocio ni fetching. */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      {children}
    </main>
  );
}
