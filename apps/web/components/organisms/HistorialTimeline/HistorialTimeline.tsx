'use client';

import {
  ArrowRight,
  CheckCircle2,
  CirclePlus,
  FileDown,
  History,
  MessageSquare,
  Pencil,
  Power,
  RotateCcw,
  ShieldCheck,
  Trash2,
  UserPlus,
} from 'lucide-react';
import type { AccionAuditable, AuditLogEntry, EntidadAuditable } from '@ambienta/shared';
import { ACCION_LABEL } from '@ambienta/shared';
import { EmptyState } from '@/components/molecules';
import { ROLE_LABEL } from '@/lib/roles';
import { useAuditLog, type RefEntidad } from '@/lib/audit-log-store';
import type { Role } from '@ambienta/shared';

const ICONO_ACCION: Record<AccionAuditable, typeof Pencil> = {
  creado: CirclePlus,
  actualizado: Pencil,
  estado_cambiado: ArrowRight,
  evaluado: ShieldCheck,
  asignado: UserPlus,
  cerrado: CheckCircle2,
  reabierto: RotateCcw,
  suspendido: Power,
  reactivado: Power,
  eliminado: Trash2,
  exportado: FileDown,
  comentado: MessageSquare,
};

/** Fecha absoluta + relativa: la absoluta sirve para auditar, la relativa para leer. */
function formatearFecha(iso: string): { absoluta: string; relativa: string } {
  const fecha = new Date(iso);
  const absoluta = fecha.toLocaleString('es-CL', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  const minutos = Math.round((Date.now() - fecha.getTime()) / 60000);
  let relativa: string;
  if (minutos < 1) relativa = 'recién';
  else if (minutos < 60) relativa = `hace ${minutos} min`;
  else if (minutos < 1440) relativa = `hace ${Math.floor(minutos / 60)} h`;
  else relativa = `hace ${Math.floor(minutos / 1440)} d`;

  return { absoluta, relativa };
}

interface HistorialTimelineProps {
  entidadTipo: EntidadAuditable;
  entidadId: string;
  titulo?: string;
  /** Texto del estado vacío, adaptado a la entidad. */
  descripcionVacio?: string;
  /**
   * Entidades hijas cuyo historial se muestra junto al de la principal.
   *
   * Una norma sin sus artículos no tiene historia propia: lo que interesa
   * auditar es cuándo cada artículo pasó a cumplir o dejó de hacerlo.
   */
  entidadesRelacionadas?: RefEntidad[];
  /** Muestra sobre qué entidad ocurrió cada evento; útil al combinar varias. */
  mostrarEntidad?: boolean;
}

/**
 * Línea de tiempo de una entidad (RF-32, RNF-08, RNF-25).
 *
 * Se monta en cualquier vista de detalle pasando el tipo y el id; lee del
 * `AuditLogProvider`, así que ninguna pantalla necesita mantener su propio
 * historial. Antes solo el ticket de soporte tenía algo parecido — un arreglo
 * `correcciones` propio — y el resto del sistema no registraba nada.
 *
 * Del más reciente al más antiguo: en una auditoría la primera pregunta suele
 * ser "qué pasó al final", y quien necesita el origen puede bajar.
 */
export function HistorialTimeline({
  entidadTipo,
  entidadId,
  titulo = 'Historial',
  descripcionVacio,
  entidadesRelacionadas,
  mostrarEntidad = false,
}: HistorialTimelineProps) {
  const { historialDe, historialDeVarias } = useAuditLog();
  const eventos = entidadesRelacionadas?.length
    ? historialDeVarias([{ tipo: entidadTipo, id: entidadId }, ...entidadesRelacionadas])
    : historialDe(entidadTipo, entidadId);

  return (
    <section aria-labelledby={`historial-${entidadId}`} className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <History className="h-4 w-4 text-slate-400" aria-hidden />
        <h2 id={`historial-${entidadId}`} className="text-sm font-semibold text-slate-900">
          {titulo}
        </h2>
        {eventos.length > 0 && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
            {eventos.length}
          </span>
        )}
      </div>

      {eventos.length === 0 ? (
        <EmptyState
          icono={History}
          titulo="Sin movimientos registrados"
          descripcion={descripcionVacio ?? 'Cada cambio que se haga aquí quedará registrado con su autor, fecha y motivo.'}
        />
      ) : (
        <ol className="relative flex flex-col gap-0 rounded-card border border-slate-200 bg-white p-4">
          {eventos.map((evento, i) => (
            <EventoItem key={evento.id} evento={evento} esUltimo={i === eventos.length - 1} mostrarEntidad={mostrarEntidad} />
          ))}
        </ol>
      )}
    </section>
  );
}

function EventoItem({ evento, esUltimo, mostrarEntidad }: { evento: AuditLogEntry; esUltimo: boolean; mostrarEntidad?: boolean }) {
  const Icono = ICONO_ACCION[evento.accion];
  const { absoluta, relativa } = formatearFecha(evento.fecha);

  return (
    <li className="relative flex gap-3 pb-4 last:pb-0">
      {/* Línea vertical que conecta los eventos; no se dibuja bajo el último. */}
      {!esUltimo && <span className="absolute left-[15px] top-8 h-[calc(100%-1rem)] w-px bg-slate-200" aria-hidden />}

      <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <Icono className="h-4 w-4" aria-hidden />
      </span>

      <div className="min-w-0 flex-1 pt-1">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <p className="text-sm text-slate-800">
            <span className="font-medium">{evento.actorNombre}</span>{' '}
            <span className="text-slate-600">{evento.resumen.toLowerCase()}</span>
          </p>
          <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
            {ACCION_LABEL[evento.accion]}
          </span>
        </div>

        {mostrarEntidad && (
          <p className="mt-0.5 text-xs font-medium text-slate-600">{evento.entidadLabel}</p>
        )}

        <p className="mt-0.5 text-xs text-slate-400">
          {ROLE_LABEL[evento.actorRol as Role] ?? evento.actorRol} ·{' '}
          <time dateTime={evento.fecha} title={absoluta}>
            {absoluta} ({relativa})
          </time>
        </p>

        {evento.cambios.length > 0 && (
          <ul className="mt-2 flex flex-col gap-1">
            {evento.cambios.map((cambio, i) => (
              <li key={`${cambio.campo}-${i}`} className="flex flex-wrap items-center gap-1.5 text-xs">
                <span className="font-medium text-slate-600">{cambio.campo}:</span>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-500 line-through decoration-slate-400">
                  {cambio.antes ?? 'vacío'}
                </span>
                <ArrowRight className="h-3 w-3 text-slate-400" aria-hidden />
                <span className="rounded bg-semaforo-cumple-bg px-1.5 py-0.5 font-medium text-semaforo-cumple">
                  {cambio.despues ?? 'vacío'}
                </span>
              </li>
            ))}
          </ul>
        )}

        {/* RF-32: el "por qué" es parte del requisito, no un extra. */}
        {evento.motivo && (
          <p className="mt-2 border-l-2 border-slate-200 pl-2 text-xs italic text-slate-600">{evento.motivo}</p>
        )}

        {evento.aprobadoPorNombre && (
          <p className="mt-1.5 flex items-center gap-1 text-xs font-medium text-semaforo-cumple">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
            Aprobado por {evento.aprobadoPorNombre}
          </p>
        )}
      </div>
    </li>
  );
}
