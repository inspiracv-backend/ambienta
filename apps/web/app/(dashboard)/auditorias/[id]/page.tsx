'use client';

import { useEffect, useState } from 'react';
import { notFound } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { AuditDetailView, HistorialTimeline, InformeDeAuditoriaPanel } from '@/components/organisms';
import { useAudits } from '@/lib/audits-store';
import { useTenants } from '@/lib/tenants-store';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';

export default function AuditDetailPage({ params }: { params: { id: string } }) {
  const { tenants } = useTenants();
  const { audits, nonConformities } = useAudits();
  const audit = audits.find((a) => a.id === params.id);
  const { user } = useSession();
  // Las preguntas de la auditoría: los hallazgos se cuelgan de una pregunta
  // (`audit_item_id`), no de la auditoría. Antes se filtraba por `nc.auditId`,
  // que el listado nunca trae, y la ficha decía «Sin hallazgos» siempre.
  const [preguntas, setPreguntas] = useState<Set<string> | null>(null);
  const [errorHallazgos, setErrorHallazgos] = useState<string | null>(null);
  useEffect(() => {
    if (!user?.tenantId) return;
    api
      .get<{ id: string }[]>(`/audits/${params.id}/items`, { tenantId: user.tenantId })
      .then((items) => setPreguntas(new Set(items.map((i) => String(i.id)))))
      .catch((e) => setErrorHallazgos(mensajeDeError(e)));
  }, [params.id, user?.tenantId]);

  if (!audit) return notFound();

  const plant = tenants.flatMap((t) => t.plants).find((p) => p.id === audit.plantId);
  // Sin normativas de ejemplo: la auditoría no trae cuáles son, y mostrar las de
  // `mocks/` —o «Sin normativas vinculadas»— sería afirmar algo que no se sabe.
  const normativas = null;
  const hallazgos = preguntas === null ? null : nonConformities.filter((nc) => nc.auditItemId && preguntas.has(nc.auditItemId));

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Auditorías', href: '/auditorias' }, { label: plant?.nombre ?? audit.plantId }]} />
      <AuditDetailView audit={audit} plant={plant} normativas={normativas} hallazgos={hallazgos} errorHallazgos={errorHallazgos} />

      {/* RF-101: lo que se entrega al cerrar la auditoría. */}
      <InformeDeAuditoriaPanel auditId={audit.id} />

      {/* Se combinan los eventos de la auditoria con los de sus hallazgos:
          lo que se audita despues es la secuencia completa, no la auditoria
          por un lado y cada hallazgo por otro. */}
      <HistorialTimeline
        entidadTipo="auditoria"
        entidadId={audit.id}
        entidadesRelacionadas={(hallazgos ?? []).map((h) => ({ tipo: 'no_conformidad' as const, id: h.id }))}
        mostrarEntidad
        titulo="Historial de la auditoria"
        descripcionVacio="Los hallazgos que se registren y su tratamiento quedaran aqui con su autor y fecha."
      />
    </div>
  );
}
