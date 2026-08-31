'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { SupportTicketsView } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useSupportTickets } from '@/lib/support-tickets-store';
import { useTenants } from '@/lib/tenants-store';

/** S-38 Soporte/Tickets internos (exclusivo Superadmin, ver AppSidebar). */
export default function SoportePage() {
  const router = useRouter();
  const { user, cargando } = useSession();
  const { tenants } = useTenants();
  const { tickets, errorDeCarga } = useSupportTickets();

  useEffect(() => {
    if (!cargando && user === null) router.replace('/login');
  }, [cargando, user, router]);

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
      {errorDeCarga && (
        <p
          role="alert"
          className="rounded-card border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          No se pudieron cargar los tickets: {errorDeCarga}. Lo que se ve está
          vacío porque no se pudo preguntar, no porque no haya nada.
        </p>
      )}
      <SupportTicketsView
        tickets={tickets}
        tenantNombre={(tenantId) => tenants.find((t) => t.id === tenantId)?.nombre ?? 'Sin empresa (invitado)'}
        currentUserId={user.id}
      />
    </div>
  );
}
