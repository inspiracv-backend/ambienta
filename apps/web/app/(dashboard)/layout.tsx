import type { ReactNode } from 'react';
import { DashboardLayout } from '@/components/templates';
import { ObligationsProvider } from '@/lib/obligations-store';
import { PlanAccionProvider } from '@/lib/plan-accion-store';
import { AuditsProvider } from '@/lib/audits-store';
import { LegalMatrixProvider } from '@/lib/legal-matrix-store';
import { GestoresProvider } from '@/lib/gestores-store';
import { NotificationsProvider } from '@/lib/notifications-store';

/**
 * Obligations y PlanAccion se comparten entre /obligaciones y /calendario
 * (mismo "ticket único", RF-17) y entre /matriz-legal y /calendario
 * (Generar Plan de Acción, RF-19). Audits vive al mismo nivel porque
 * No Conformidades también genera Planes de Acción (RF-41). LegalMatrix se
 * comparte entre /matriz-legal y /catalogo-normativo (misma entidad
 * LegalNorm, Sección H). Gestores vive aquí porque S-30 reutiliza Obligation
 * (Sección I). Notifications vive aquí porque el contador de no leídas se
 * muestra en AppHeader (Sección J).
 */
export default function DashboardRouteLayout({ children }: { children: ReactNode }) {
  return (
    <LegalMatrixProvider>
      <ObligationsProvider>
        <AuditsProvider>
          <PlanAccionProvider>
            <GestoresProvider>
              <NotificationsProvider>
                <DashboardLayout>{children}</DashboardLayout>
              </NotificationsProvider>
            </GestoresProvider>
          </PlanAccionProvider>
        </AuditsProvider>
      </ObligationsProvider>
    </LegalMatrixProvider>
  );
}
