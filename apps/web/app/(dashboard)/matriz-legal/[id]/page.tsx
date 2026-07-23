'use client';

import { notFound } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { NormDetailView } from '@/components/organisms';
import { useLegalMatrix } from '@/lib/legal-matrix-store';
import { useSession } from '@/lib/session';
import { mockUsers } from '@/mocks/users';

export default function NormDetailPage({ params }: { params: { id: string } }) {
  const { norms } = useLegalMatrix();
  const { user } = useSession();
  const norm = norms.find((n) => n.id === params.id);

  if (!norm) return notFound();
  if (!user) return null;

  const responsableOptions = mockUsers
    .filter((u) => u.tenantId === norm.tenantId || norm.tenantId === null)
    .map((u) => ({ id: u.id, nombre: u.nombre }));

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Matriz Legal', href: '/matriz-legal' }, { label: norm.nombre }]} />
      <NormDetailView norm={norm} activeTenantId={user.tenantId ?? ''} responsableOptions={responsableOptions} />
    </div>
  );
}
