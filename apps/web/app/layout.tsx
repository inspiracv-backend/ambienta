import type { Metadata } from 'next';
import './globals.css';
import { SessionProvider } from '@/lib/session';

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
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
