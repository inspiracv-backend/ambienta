import type { EtapaCrm, Pipeline, TratoCrm } from '@/lib/crm';

export interface PipelineKanbanProps {
  pipeline: Pipeline;
  /**
   * Devuelve qué más pasó además del cambio de columna. La pantalla lo dice;
   * si no, arrastrar a "Perdido" cierra el trato en silencio y la persona lo
   * descubre cuando ya no aparece en sus pendientes.
   */
  onMover: (
    trato: TratoCrm,
    destino: EtapaCrm,
    motivo?: string,
  ) => Promise<{ ok: boolean; efectos: string[]; error?: string }>;
  /** Abre la ficha del trato. Opcional: el tablero sirve para mirar y mover. */
  onAbrirTrato?: (trato: TratoCrm) => void;
}
