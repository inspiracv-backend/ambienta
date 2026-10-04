'use client';

import { visibleEnAlcance } from '@/lib/alcance';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Plus } from 'lucide-react';
import { Button, Spinner } from '@/components/atoms';
import { AuditsListTable, NuevaAuditoriaModal } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useAudits } from '@/lib/audits-store';
import { useTenants } from '@/lib/tenants-store';

/** S-20 Listado de Auditorías. */
export default function AuditoriasPage() {
  const router = useRouter();
  const { user, cargando } = useSession();
  const { tenants } = useTenants();
  const { audits, errorDeCarga, agregarAuditoria } = useAudits();
  const [creando, setCreando] = useState(false);

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

  const visibleAudits = audits.filter(
    (a) => a.tenantId === user.tenantId && visibleEnAlcance(a.plantId, scopedPlants),
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Auditorías</h1>
          <p className="text-sm text-slate-500">{tenant?.nombre}</p>
        </div>
        {/* Hasta el 19-sep no habia forma de crear una auditoria desde la
            pantalla: la API existia y nadie la llamaba. */}
        {user.tenantId && (
          <Button icon={<Plus className="h-4 w-4" aria-hidden />} onClick={() => setCreando(true)}>
            Nueva auditoría
          </Button>
        )}
      </div>
      {user.tenantId && (
        <NuevaAuditoriaModal
          open={creando}
          onOpenChange={setCreando}
          tenantId={user.tenantId}
          plantas={scopedPlants.map((p) => ({ id: p.id, nombre: p.nombre }))}
          onCreada={(raw) => {
            const nueva = agregarAuditoria(raw);
            if (nueva) router.push(`/auditorias/${nueva.id}`);
          }}
        />
      )}
      {errorDeCarga && (
        <p
          role="alert"
          className="rounded-card border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          No se pudieron cargar las auditorías: {errorDeCarga}. Lo que se ve está
          vacío porque no se pudo preguntar, no porque no haya nada.
        </p>
      )}
      <AuditsListTable audits={visibleAudits} plants={scopedPlants} />
    </div>
  );
}
