'use client';

import { useState } from 'react';
import { notFound } from 'next/navigation';
import { FEATURE_FLAGS } from '@ambienta/shared';
import { Breadcrumbs } from '@/components/molecules';
import {
  CierreNoConformidadPanel,
  EtapasMejoraPanel,
  HistorialTimeline,
  NonConformityDetailView,
} from '@/components/organisms';
import { useAudits } from '@/lib/audits-store';
import { useTenants } from '@/lib/tenants-store';
import { mockUsers } from '@/mocks/users';

export default function NonConformityDetailPage({ params }: { params: { id: string } }) {
  const { tenants } = useTenants();
  const { nonConformities } = useAudits();
  // Resultado de la Etapa de Seguimiento. Vive acá y no en cada componente
  // porque lo produce el panel de etapas y lo consume el bloque de Cierre.
  const [eficacia, setEficacia] = useState<boolean | null>(null);
  const nc = nonConformities.find((n) => n.id === params.id);

  if (!nc) return notFound();

  const plant = tenants.flatMap((t) => t.plants).find((p) => p.id === nc.plantId);
  const responsableOptions = mockUsers.filter((u) => u.tenantId === nc.tenantId).map((u) => ({ id: u.id, nombre: u.nombre }));

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'No Conformidades', href: '/no-conformidades' }, { label: nc.hallazgo }]} />
      <NonConformityDetailView
        nonConformity={nc}
        plant={plant}
        responsableOptions={responsableOptions}
      />

      {/* Etapas del tratamiento (flag `registroMejora`). Al abrir un registro se
          ve el flujo completo, no una etapa suelta — es la diferencia principal
          contra tener cinco pantallas inconexas.

          La eficacia sube hasta acá y baja al bloque de Cierre: el cierre con
          firma es uno solo, y §10.2.1 d) exige verificarla antes. */}
      {FEATURE_FLAGS.registroMejora && (
        <EtapasMejoraPanel
          ncId={nc.id}
          responsableOptions={responsableOptions}
          flujoCorto={nc.tipoRegistro === 'riesgo' || nc.tipoRegistro === 'oportunidad'}
          onEficaciaChange={setEficacia}
        />
      )}

      {/* El cierre va al final: es el último acto del tratamiento y sólo tiene
          sentido después de haber recorrido las etapas. */}
      <CierreNoConformidadPanel
        nonConformity={nc}
        responsableOptions={responsableOptions}
        eficaciaVerificada={eficacia}
      />

      {/* RF-32 y RNF-08: el tratamiento de una no conformidad es lo que se
          revisa en una auditoria — cuando se detecto, quien analizo la causa y
          quien la cerro. Tenerlo solo en el historial global obliga a filtrar
          para reconstruir el caso. */}
      <HistorialTimeline
        entidadTipo="no_conformidad"
        entidadId={nc.id}
        titulo="Historial del hallazgo"
        descripcionVacio="Cada cambio de estado, analisis de causa y el cierre quedaran aqui con su autor y fecha."
      />
    </div>
  );
}
