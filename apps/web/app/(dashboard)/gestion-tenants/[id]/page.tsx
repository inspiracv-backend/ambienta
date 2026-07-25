'use client';

import { notFound } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { TenantConfigView } from '@/components/organisms';
import { useTenants } from '@/lib/tenants-store';
import { mockUsers } from '@/mocks/users';

export default function TenantConfigPage({ params }: { params: { id: string } }) {
  const { tenants } = useTenants();
  const tenant = tenants.find((t) => t.id === params.id);

  if (!tenant) return notFound();

  const userCount = mockUsers.filter((u) => u.tenantId === tenant.id).length;

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Gestión de Tenants', href: '/gestion-tenants' }, { label: tenant.nombre }]} />
      <TenantConfigView tenant={tenant} userCount={userCount} />
    </div>
  );
}
