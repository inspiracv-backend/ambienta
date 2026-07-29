'use client';

import { notFound } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { HistorialTimeline, NormDetailView } from '@/components/organisms';
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

      {/* RF-32 y RNF-25: la historia de una norma es la de sus artículos —
          cuándo cada uno pasó a cumplir y cuándo dejó de hacerlo—, así que se
          combinan en una sola línea de tiempo en vez de obligar a abrir cada
          artículo por separado. */}
      <HistorialTimeline
        entidadTipo="norma"
        entidadId={norm.id}
        entidadesRelacionadas={norm.articulos.map((a) => ({ tipo: 'articulo' as const, id: a.id }))}
        mostrarEntidad
        titulo="Historial de cumplimiento"
        descripcionVacio="Cuando se evalúe un artículo quedará aquí registrado quién lo hizo, cuándo y con qué fundamento."
      />
    </div>
  );
}
