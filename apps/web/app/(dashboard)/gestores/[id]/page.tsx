'use client';

import { notFound } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { SubTenantDetailView } from '@/components/organisms';
import { useGestores } from '@/lib/gestores-store';

export default function SubTenantDetailPage({ params }: { params: { id: string } }) {
  const { subTenants } = useGestores();
  const subTenant = subTenants.find((s) => s.id === params.id);

  if (!subTenant) return notFound();

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Gestores', href: '/gestores' }, { label: subTenant.nombre }]} />
      <SubTenantDetailView subTenant={subTenant} />
    </div>
  );
}
