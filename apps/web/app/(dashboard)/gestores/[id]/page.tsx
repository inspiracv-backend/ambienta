'use client';

import { Breadcrumbs } from '@/components/molecules';
import { FichaNoDisponible, SubTenantDetailView } from '@/components/organisms';
import { useGestores } from '@/lib/gestores-store';

export default function SubTenantDetailPage({ params }: { params: { id: string } }) {
  const { subTenants, loading: cargandoClientes } = useGestores();
  const subTenant = subTenants.find((s) => s.id === params.id);

  if (!subTenant) return <FichaNoDisponible cargando={cargandoClientes} que="este cliente" volverA="/gestores" volverEtiqueta="Volver a gestores" />;

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Gestores', href: '/gestores' }, { label: subTenant.nombre }]} />
      <SubTenantDetailView subTenant={subTenant} />
    </div>
  );
}
