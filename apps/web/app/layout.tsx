import type { Metadata } from 'next';
import './globals.css';
import { SessionProvider } from '@/lib/session';
import { SupportTicketsProvider } from '@/lib/support-tickets-store';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import { ToastViewport } from '@/components/organisms';

export const metadata: Metadata = {
  title: 'Ambienta — Cumplimiento ambiental',
  description: 'Sistema multi-tenant de cumplimiento ambiental para empresas industriales en Chile',
};

/**
 * UsersProvider vive aquí, antes que SessionProvider, porque SessionProvider
 * ahora deriva `user` en vivo desde `useUsers()` (Sección N, S-41/S-42) en
 * vez de mantener su propia copia — así editar el perfil o el rol de un
 * usuario se refleja de inmediato en toda la app sin duplicar el dato.
 *
 * ToastProvider envuelve todo para que cualquier pantalla pueda confirmar el
 * resultado de una acción (H1), incluidas las de (auth) que están fuera del
 * layout de dashboard.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body>
        <ToastProvider>
          <UsersProvider>
            <SessionProvider>
              <SupportTicketsProvider>{children}</SupportTicketsProvider>
            </SessionProvider>
          </UsersProvider>
          <ToastViewport />
        </ToastProvider>
      </body>
    </html>
  );
}
