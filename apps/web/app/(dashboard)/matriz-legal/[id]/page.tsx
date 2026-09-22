'use client';

import { Breadcrumbs } from '@/components/molecules';
import { FichaNoDisponible, HistorialTimeline, NormDetailView } from '@/components/organisms';
import { useLegalMatrix } from '@/lib/legal-matrix-store';
import { useSession } from '@/lib/session';
import { usePersonasAsignables } from '@/lib/crm-etapas-store';

export default function NormDetailPage({ params }: { params: { id: string } }) {
  const { norms, loading: cargandoNormas } = useLegalMatrix();
  const { user } = useSession();
  // Personas de la base (`/users/`), no `mockUsers`: el responsable es una
  // clave foránea y un id de ejemplo hacía que la API rechazara la escritura.
  const { personas } = usePersonasAsignables();
  const norm = norms.find((n) => n.id === params.id);

  if (!norm) return <FichaNoDisponible cargando={cargandoNormas} que="esta norma" volverA="/matriz-legal" volverEtiqueta="Volver a la matriz legal" />;
  if (!user) return null;

  const responsableOptions = personas;

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
