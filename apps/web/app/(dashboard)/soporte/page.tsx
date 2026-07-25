'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { SupportTicketsView } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useSupportTickets } from '@/lib/support-tickets-store';
import { mockTenants } from '@/mocks/tenants';

/** S-38 Soporte/Tickets internos (exclusivo Superadmin, ver AppSidebar). */
export default function SoportePage() {
  const router = useRouter();
  const { user } = useSession();
  const { tickets } = useSupportTickets();

  useEffect(() => {
    if (user === null && !window.localStorage.getItem('ambienta.mockUserId')) router.replace('/login');
  }, [user, router]);

  if (!user) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando sesión" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Soporte</h1>
        <p className="text-sm text-slate-500">Tickets internos — vista del equipo</p>
      </div>
      <SupportTicketsView
        tickets={tickets}
        tenantNombre={(tenantId) => mockTenants.find((t) => t.id === tenantId)?.nombre ?? 'Sin empresa (invitado)'}
        currentUserId={user.id}
      />
    </div>
  );
}
