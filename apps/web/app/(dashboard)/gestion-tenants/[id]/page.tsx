'use client';

import { Breadcrumbs } from '@/components/molecules';
import { FichaNoDisponible, HistorialTimeline, TenantConfigView } from '@/components/organisms';
import { useTenants } from '@/lib/tenants-store';
import { useUsers } from '@/lib/users-store';
import { CLERK_HABILITADO } from '@/lib/clerk-config';

export default function TenantConfigPage({ params }: { params: { id: string } }) {
  const { tenants, loading: cargandoEmpresas } = useTenants();
  const { users, loading } = useUsers();
  const tenant = tenants.find((t) => t.id === params.id);

  if (!tenant) return <FichaNoDisponible cargando={cargandoEmpresas} que="esta empresa" volverA="/gestion-tenants" volverEtiqueta="Volver a la gestión de empresas" />;

  // **Solo se cuenta cuando se puede saber.** Antes salía de `mockUsers`, y
  // con empresas reales daba 0: el aviso de suspender decía «Los 0 usuarios
  // perderán acceso» justo antes de dejarlos a todos fuera. Con Clerk, RLS no
  // deja al Admin Global listar las personas de otra empresa, así que no hay
  // número que dar; sin Clerk el store las carga de todas.
  const userCount = CLERK_HABILITADO || loading ? null : users.filter((u) => u.tenantId === tenant.id).length;

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Gestión de Tenants', href: '/gestion-tenants' }, { label: tenant.nombre }]} />
      <TenantConfigView tenant={tenant} userCount={userCount} />

      {/* Historial de las decisiones de plataforma sobre esta empresa: alta,
          cambios de limite, modulos y suspensiones. Es lo que hay que poder
          mostrarle al cliente si reclama por un cambio en su servicio. */}
      <HistorialTimeline
        entidadTipo="tenant"
        entidadId={tenant.id}
        titulo="Historial de la cuenta"
        descripcionVacio="Los cambios de plan, limites y modulos quedaran aqui con su autor y fecha."
      />
    </div>
  );
}
