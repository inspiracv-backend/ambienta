import type { Metadata } from 'next';
import './globals.css';
import { SessionProvider } from '@/lib/session';
import { SupportTicketsProvider } from '@/lib/support-tickets-store';

export const metadata: Metadata = {
  title: 'Ambienta — Cumplimiento ambiental',
  description: 'Sistema multi-tenant de cumplimiento ambiental para empresas industriales en Chile',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body>
        <SessionProvider>
          <SupportTicketsProvider>{children}</SupportTicketsProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
