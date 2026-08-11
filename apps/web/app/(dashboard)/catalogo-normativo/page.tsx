'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Settings2 } from 'lucide-react';
import { Spinner } from '@/components/atoms';
import { CatalogNormsTable } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useLegalMatrix } from '@/lib/legal-matrix-store';
import { useTenants } from '@/lib/tenants-store';

/** S-25 Catálogo Normativo (3 capas). Fetching real: reemplazar por GET /catalog + agente BCN cuando exista spec aprobada (RF-42/RF-45). */
export default function CatalogoNormativoPage() {
  const router = useRouter();
  const { user } = useSession();
  const { tenants } = useTenants();
  const { norms, setNormPlants } = useLegalMatrix();

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

  const tenant = tenants.find((t) => t.id === user.tenantId);
  const tenantPlantIds = (tenant?.plants ?? []).map((p) => p.id);
  const visibleNorms = norms.filter((n) => n.tenantId === null || n.tenantId === user.tenantId);

  function handleMarcarAplicable(normId: string) {
    const norm = norms.find((n) => n.id === normId);
    if (!norm) return;
    const nextPlantIds = Array.from(new Set([...norm.plantIds, ...tenantPlantIds]));
    setNormPlants(normId, nextPlantIds);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Catálogo Normativo</h1>
          <p className="text-sm text-slate-500">{tenant?.nombre}</p>
        </div>
        {user.role === 'admin_empresa' && (
          <Link
            href="/catalogo-normativo/asignar"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <Settings2 className="h-4 w-4" aria-hidden />
            Definir normas por planta
          </Link>
        )}
      </div>

      <CatalogNormsTable
        norms={visibleNorms}
        tenantPlantIds={tenantPlantIds}
        isSuperadmin={user.role === 'superadmin'}
        isAdminEmpresa={user.role === 'admin_empresa'}
        onMarcarAplicable={handleMarcarAplicable}
      />
    </div>
  );
}
