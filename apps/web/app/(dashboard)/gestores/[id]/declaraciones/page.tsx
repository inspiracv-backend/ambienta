'use client';

import { Breadcrumbs } from '@/components/molecules';
import { FichaNoDisponible, SubTenantDeclarationsView } from '@/components/organisms';
import { useGestores } from '@/lib/gestores-store';
import { useObligations } from '@/lib/obligations-store';

export default function DeclaracionesPage({ params }: { params: { id: string } }) {
  const { subTenants, loading: cargandoClientes } = useGestores();
  const { obligations } = useObligations();
  const subTenant = subTenants.find((s) => s.id === params.id);

  if (!subTenant) return <FichaNoDisponible cargando={cargandoClientes} que="este cliente" volverA="/gestores" volverEtiqueta="Volver a gestores" />;

  const subObligations = obligations.filter((o) => o.subTenantId === subTenant.id);

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Gestores', href: '/gestores' }, { label: subTenant.nombre, href: `/gestores/${subTenant.id}` }, { label: 'Declaraciones' }]} />
      <SubTenantDeclarationsView obligations={subObligations} subTenantNombre={subTenant.nombre} />
    </div>
  );
}
