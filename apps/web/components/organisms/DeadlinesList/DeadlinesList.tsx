import { Inbox } from 'lucide-react';
import { DeadlineListItem } from '@/components/molecules';
import type { DeadlinesListProps } from './DeadlinesList.types';

/** S-06: lista compacta de los próximos 5 vencimientos. Empty state con guía (H10). */
export function DeadlinesList({ obligations }: DeadlinesListProps) {
  const proximos = [...obligations]
    .sort((a, b) => new Date(a.proximoVencimiento).getTime() - new Date(b.proximoVencimiento).getTime())
    .slice(0, 5);

  if (proximos.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
        <Inbox className="h-6 w-6 text-slate-400" aria-hidden />
        No hay vencimientos próximos. Las obligaciones que crees en Matriz Legal aparecerán aquí.
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {proximos.map((obligation) => (
        <DeadlineListItem key={obligation.id} obligation={obligation} />
      ))}
    </ul>
  );
}
