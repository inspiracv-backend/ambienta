import type { ReactNode } from 'react';
import { DashboardLayout } from '@/components/templates';
import { PerfilEmpresaGate, ClienteInvitadoGate, TenantScopeGate } from '@/components/organisms';
import { ObligationsProvider } from '@/lib/obligations-store';
import { PlanAccionProvider } from '@/lib/plan-accion-store';
import { AuditsProvider } from '@/lib/audits-store';
import { LegalMatrixProvider } from '@/lib/legal-matrix-store';
import { GestoresProvider } from '@/lib/gestores-store';
import { NotificationsProvider } from '@/lib/notifications-store';
import { TenantsProvider } from '@/lib/tenants-store';
import { DepartamentosProvider } from '@/lib/departamentos-store';

/**
 * Obligations y PlanAccion se comparten entre /obligaciones y /calendario
 * (mismo "ticket único", RF-26 a RF-28) y entre /matriz-legal y /calendario
 * (Generar Plan de Acción, RF-30). Audits vive al mismo nivel porque
 * No Conformidades también genera Planes de Acción (RF-53). LegalMatrix se
 * comparte entre /matriz-legal y /catalogo-normativo (misma entidad
 * LegalNorm, Sección H). Gestores vive aquí porque S-30 reutiliza Obligation
 * (Sección I). Notifications vive aquí porque el contador de no leídas se
 * muestra en AppHeader (Sección J). Tenants y Departamentos viven aquí para
 * la Gestión de Tenants del Superadmin (Sección L) y para el Perfil Empresa
 * del Admin Empresa (RF-10 a RF-12, v1.7) — PerfilEmpresaGate necesita
 * ambos para decidir si redirige a /perfil-empresa antes de mostrar
 * cualquier otra pantalla. ClienteInvitadoGate envuelve todo lo demás
 * porque el Cliente Invitado (RF-05, acceso limitado a tickets) no debe
 * llegar a ninguna pantalla de negocio del tenant, independientemente del
 * estado de Perfil Empresa.
 *
 * Orden de los gates (de fuera hacia dentro): primero se saca al Cliente
 * Invitado del área de negocio, después TenantScopeGate separa el ámbito de
 * plataforma del ámbito de tenant (el Superadmin no entra a los módulos de un
 * tenant, ni los roles de tenant a la administración de la plataforma), y solo
 * entonces PerfilEmpresaGate exige el perfil al Admin Empresa — que ya se sabe
 * que está en el ámbito correcto.
 */
export default function DashboardRouteLayout({ children }: { children: ReactNode }) {
  return (
    <LegalMatrixProvider>
      <ObligationsProvider>
        <AuditsProvider>
          <PlanAccionProvider>
            <GestoresProvider>
              <NotificationsProvider>
                <TenantsProvider>
                  <DepartamentosProvider>
                    <ClienteInvitadoGate>
                      <TenantScopeGate>
                        <PerfilEmpresaGate>
                          <DashboardLayout>{children}</DashboardLayout>
                        </PerfilEmpresaGate>
                      </TenantScopeGate>
                    </ClienteInvitadoGate>
                  </DepartamentosProvider>
                </TenantsProvider>
              </NotificationsProvider>
            </GestoresProvider>
          </PlanAccionProvider>
        </AuditsProvider>
      </ObligationsProvider>
    </LegalMatrixProvider>
  );
}
