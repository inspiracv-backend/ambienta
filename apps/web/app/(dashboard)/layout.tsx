import type { ReactNode } from 'react';
import { DashboardLayout } from '@/components/templates';
import { ObligationsProvider } from '@/lib/obligations-store';
import { PlanAccionProvider } from '@/lib/plan-accion-store';

/**
 * Obligations y PlanAccion se comparten entre /obligaciones y /calendario
 * (mismo "ticket único", RF-17) y entre /matriz-legal y /calendario
 * (Generar Plan de Acción, RF-19) — por eso viven a este nivel y no anidados
 * en una sola ruta.
 */
export default function DashboardRouteLayout({ children }: { children: ReactNode }) {
  return (
    <ObligationsProvider>
      <PlanAccionProvider>
        <DashboardLayout>{children}</DashboardLayout>
      </PlanAccionProvider>
    </ObligationsProvider>
  );
}
