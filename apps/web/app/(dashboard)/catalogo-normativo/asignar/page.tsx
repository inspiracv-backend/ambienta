'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { AssignNormsToPlant } from '@/components/organisms';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';
import { useLegalMatrix } from '@/lib/legal-matrix-store';
import { useTenants } from '@/lib/tenants-store';

/** S-26 Definir Normas Aplicables por Planta. */
export default function AsignarNormasPage() {
  const router = useRouter();
  const { user, cargando } = useSession();
  const { tenants } = useTenants();
  const { norms } = useLegalMatrix();

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

  const tenant = tenants.find((t) => t.id === user.tenantId);
  const visibleNorms = norms.filter((n) => n.tenantId === null || n.tenantId === user.tenantId);

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Catálogo Normativo', href: '/catalogo-normativo' }, { label: 'Definir normas por planta' }]} />
      <h1 className="text-2xl font-semibold text-slate-900">Definir normas aplicables por planta</h1>
      <AssignNormsToPlant plants={tenant?.plants ?? []} norms={visibleNorms} />
    </div>
  );
}
