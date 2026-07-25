'use client';

import { notFound } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { ContractsListView } from '@/components/organisms';
import { useGestores } from '@/lib/gestores-store';

export default function ContratosPage({ params }: { params: { id: string } }) {
  const { subTenants } = useGestores();
  const subTenant = subTenants.find((s) => s.id === params.id);

  if (!subTenant) return notFound();

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Gestores', href: '/gestores' }, { label: subTenant.nombre, href: `/gestores/${subTenant.id}` }, { label: 'Contratos' }]} />
      <ContractsListView subTenantId={subTenant.id} subTenantNombre={subTenant.nombre} />
    </div>
  );
}
