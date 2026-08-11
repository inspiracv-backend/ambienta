'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CalendarDays, GanttChartSquare, Kanban } from 'lucide-react';
import { Spinner } from '@/components/atoms';
import { cn } from '@/lib/utils';
import {
  CalendarMonthView,
  GanttView,
  KanbanBoard,
  TaskDetailModal,
  type TicketRef,
} from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useObligations } from '@/lib/obligations-store';
import { useTenants } from '@/lib/tenants-store';
import { mockUsers } from '@/mocks/users';

type ViewMode = 'calendario' | 'gantt' | 'kanban';

const VIEWS: { value: ViewMode; label: string; icon: typeof CalendarDays }[] = [
  { value: 'calendario', label: 'Calendario', icon: CalendarDays },
  { value: 'gantt', label: 'Gantt', icon: GanttChartSquare },
  { value: 'kanban', label: 'Kanban', icon: Kanban },
];

/**
 * S-16/S-17/S-18. Misma entidad que Obligaciones (RF-17, "ticket único") —
 * al hacer clic en cualquier vista se abre el mismo `TaskDetailModal` de la
 * Sección E, sin duplicar el modelo de datos ni el componente.
 */
export default function CalendarioPage() {
  const router = useRouter();
  const { user } = useSession();
  const { tenants } = useTenants();
  const { obligations } = useObligations();
  const [view, setView] = useState<ViewMode>('calendario');
  const [selected, setSelected] = useState<TicketRef | null>(null);

  useEffect(() => {
    if (user === null && !window.localStorage.getItem('ambienta.mockUserId')) router.replace('/login');
  }, [user, router]);

  const tenant = tenants.find((t) => t.id === user?.tenantId);
  const isVistaSimplificada = user?.role === 'admin_empresa';

  const scopedPlants = useMemo(() => {
    if (!user) return [];
    return !isVistaSimplificada && user.plantIds.length > 0
      ? (tenant?.plants ?? []).filter((p) => user.plantIds.includes(p.id))
      : tenant?.plants ?? [];
  }, [user, isVistaSimplificada, tenant]);

  const tickets: TicketRef[] = useMemo(() => {
    if (!user) return [];
    return obligations
      .filter((o) => o.tenantId === user.tenantId && scopedPlants.some((p) => p.id === o.plantId))
      .flatMap((obligation) => obligation.tasks.map((task) => ({ obligation, task })));
  }, [obligations, user, scopedPlants]);

  if (!user) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando sesión" />
      </div>
    );
  }

  const responsableOptions = mockUsers.filter((u) => u.tenantId === user.tenantId).map((u) => ({ id: u.id, nombre: u.nombre }));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Calendario / Gantt</h1>
          <p className="text-sm text-slate-500">{tenant?.nombre}</p>
        </div>
        <div role="tablist" aria-label="Cambiar vista" className="inline-flex rounded-lg border border-slate-200 bg-white p-1">
          {VIEWS.map((v) => (
            <button
              key={v.value}
              role="tab"
              aria-selected={view === v.value}
              onClick={() => setView(v.value)}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium',
                view === v.value ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-50',
              )}
            >
              <v.icon className="h-4 w-4" aria-hidden />
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {view === 'calendario' && <CalendarMonthView tickets={tickets} onSelectTicket={setSelected} />}
      {view === 'gantt' && <GanttView tickets={tickets} onSelectTicket={setSelected} />}
      {view === 'kanban' && <KanbanBoard tickets={tickets} onSelectTicket={setSelected} />}

      <TaskDetailModal
        task={selected?.task ?? null}
        obligationId={selected?.obligation.id ?? ''}
        obligationNombre={selected?.obligation.nombre ?? ''}
        tenantId={user.tenantId ?? ''}
        responsableOptions={responsableOptions}
        onOpenChange={(open) => !open && setSelected(null)}
      />
    </div>
  );
}
