'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Settings2 } from 'lucide-react';
import { Spinner } from '@/components/atoms';
import {
  AvisoNormasDesactualizadas,
  CheckNormativaAplicable,
  LegalMatrixTable,
} from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useLegalMatrix } from '@/lib/legal-matrix-store';
import { useTenants } from '@/lib/tenants-store';

/**
 * S-08 Listado de Matriz Legal. Fetching real: reemplazar por
 * GET /tenants/:id/legal-matrix cuando exista spec aprobada (RF-08).
 */
export default function MatrizLegalPage() {
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
  const isVistaSimplificada = user.role === 'admin_empresa';
  const scopedPlants =
    !isVistaSimplificada && user.plantIds.length > 0
      ? (tenant?.plants ?? []).filter((p) => user.plantIds.includes(p.id))
      : tenant?.plants ?? [];

  const visibleNorms = norms.filter(
    (n) => (n.tenantId === null || n.tenantId === user.tenantId) && n.plantIds.some((id) => scopedPlants.some((p) => p.id === id)),
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Matriz Legal</h1>
          <p className="text-sm text-slate-500">{tenant?.nombre}</p>
        </div>
        <Link
          href="/matriz-legal/gestion-normas"
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          <Settings2 className="h-4 w-4" aria-hidden />
          Gestionar RCAs / ISO
        </Link>
      </div>

      {/* Antes de la matriz: que normas cambiaron de version desde que se
          evaluaron. Va arriba porque cambia como se lee lo que hay debajo. */}
      <AvisoNormasDesactualizadas />

      <LegalMatrixTable norms={visibleNorms} plants={scopedPlants} />

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Normativa aplicable a la empresa</h2>
          <p className="text-sm text-slate-500">
            Lo que le corresponde segun su sector y tamano. Es una propuesta para revisar: nada de
            esto entra a la matriz hasta que alguien lo decida.
          </p>
        </div>
        <CheckNormativaAplicable />
      </section>
    </div>
  );
}
