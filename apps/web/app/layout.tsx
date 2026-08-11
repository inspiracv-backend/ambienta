import type { Metadata } from 'next';
import './globals.css';
import { AuditLogProvider } from '@/lib/audit-log-store';
import { SessionProvider } from '@/lib/session';
import { SupportTicketsProvider } from '@/lib/support-tickets-store';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import { AuthProvider, ToastViewport } from '@/components/organisms';

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
 *
 * AuditLogProvider va en el nivel más externo, por encima incluso de
 * UsersProvider: es un almacén append-only que no conoce la sesión, así que
 * cualquier store puede escribir en él sin importar el orden. Quien pone el
 * actor es `useRegistrarAuditoria()`, que sí vive dentro de la sesión. Si el
 * provider dependiera de `useSession`, UsersProvider —que está por encima de
 * SessionProvider— no podría registrar sus propios eventos.
 *
 * Está en el layout raíz y no en (dashboard) porque los eventos también nacen
 * en (auth): un Cliente Invitado creando un ticket es un hecho auditable.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body>
        {/* AuthProvider va por fuera de todo: la identidad antecede a la
            sesión y a cualquier store que dependa de ella. Si Clerk no está
            configurado se comporta como si no existiera. */}
        <AuthProvider>
          <ToastProvider>
            <AuditLogProvider>
              <UsersProvider>
                <SessionProvider>
                  <SupportTicketsProvider>{children}</SupportTicketsProvider>
                </SessionProvider>
              </UsersProvider>
            </AuditLogProvider>
            <ToastViewport />
          </ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
