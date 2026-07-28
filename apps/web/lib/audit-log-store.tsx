'use client';

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import type { AccionAuditable, AuditLogEntry, CambioCampo, EntidadAuditable } from '@ambienta/shared';
import { useSession } from '@/lib/session';
import { mockAuditLog } from '@/mocks/audit-log';

/**
 * Registro de auditoría del sistema (RF-32, RNF-08, RNF-25).
 *
 * Append-only por diseño: el contexto no expone ninguna forma de editar ni
 * borrar un evento. Eso lo hace inmutable *desde la aplicación*, pero no es
 * la garantía que pide RNF-08 — en memoria cualquiera puede alterar el estado
 * desde las devtools, y al recargar se pierde todo. La garantía real es una
 * tabla append-only en PostgreSQL sin permisos de UPDATE/DELETE para el rol
 * de aplicación (propuesta OpenSpec `sistema-actores-roles-rbac`).
 *
 * **Por qué el provider no conoce la sesión:** `SessionProvider` deriva el
 * usuario de `UsersProvider`, así que si este store dependiera de la sesión
 * quedaría por debajo de ambos y `UsersProvider` no podría registrar sus
 * propios eventos — un ciclo. La solución es separar responsabilidades: el
 * provider solo guarda entradas ya formadas, y `useRegistrarAuditoria()`
 * —que sí vive dentro de la sesión— es quien les pone el actor.
 */

/** Lo que registra cada llamador. El actor y la fecha los pone el hook. */
export interface EventoAuditable {
  entidadTipo: EntidadAuditable;
  entidadId: string;
  entidadLabel: string;
  accion: AccionAuditable;
  resumen: string;
  /** `null` para eventos de plataforma; si se omite, se usa el tenant del actor. */
  tenantId?: string | null;
  cambios?: CambioCampo[];
  motivo?: string;
  aprobadoPorId?: string;
  aprobadoPorNombre?: string;
}

interface AuditLogContextValue {
  entries: AuditLogEntry[];
  /** Append-only: no existe editar ni borrar. */
  agregarEntrada: (entry: AuditLogEntry) => void;
  /** Historial de una entidad, del más reciente al más antiguo. */
  historialDe: (entidadTipo: EntidadAuditable, entidadId: string) => AuditLogEntry[];
}

const AuditLogContext = createContext<AuditLogContextValue | null>(null);

export function AuditLogProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<AuditLogEntry[]>(mockAuditLog);

  const agregarEntrada = useCallback((entry: AuditLogEntry) => {
    setEntries((prev) => [...prev, entry]);
  }, []);

  const historialDe = useCallback(
    (entidadTipo: EntidadAuditable, entidadId: string) =>
      entries
        // Se conserva el índice para desempatar: dos acciones seguidas pueden
        // caer en el mismo milisegundo y `Date.now()` no las distingue. Sin
        // desempate el historial podría mostrarlas invertidas, que en un audit
        // log es un error de hecho. El orden de inserción es la secuencia real.
        .map((e, indice) => ({ e, indice }))
        .filter(({ e }) => e.entidadTipo === entidadTipo && e.entidadId === entidadId)
        .sort((a, b) => {
          const porFecha = new Date(b.e.fecha).getTime() - new Date(a.e.fecha).getTime();
          return porFecha !== 0 ? porFecha : b.indice - a.indice;
        })
        .map(({ e }) => e),
    [entries],
  );

  const value = useMemo(() => ({ entries, agregarEntrada, historialDe }), [entries, agregarEntrada, historialDe]);

  return <AuditLogContext.Provider value={value}>{children}</AuditLogContext.Provider>;
}

export function useAuditLog() {
  const ctx = useContext(AuditLogContext);
  if (!ctx) throw new Error('useAuditLog debe usarse dentro de <AuditLogProvider>');
  return ctx;
}

/**
 * Registra un evento firmándolo con el usuario de la sesión.
 *
 * Solo se puede usar por debajo de `SessionProvider`. Los stores que viven
 * dentro de la sesión lo llaman directamente; `UsersProvider`, que está por
 * encima, lo hace desde sus pantallas (ver comentario en `users-store.tsx`).
 */
export function useRegistrarAuditoria() {
  const { agregarEntrada } = useAuditLog();
  const { user } = useSession();

  return useCallback(
    (evento: EventoAuditable) => {
      // Sin sesión no hay actor que registrar. Es preferible no anotar nada a
      // anotar "actor desconocido": un log que miente es peor que uno con un
      // hueco, y en el backend este caso no existe (todo pasa por un JWT).
      if (!user) return;

      agregarEntrada({
        id: `audit-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        tenantId: evento.tenantId !== undefined ? evento.tenantId : user.tenantId,
        entidadTipo: evento.entidadTipo,
        entidadId: evento.entidadId,
        entidadLabel: evento.entidadLabel,
        accion: evento.accion,
        resumen: evento.resumen,
        cambios: evento.cambios ?? [],
        // Foto del actor, no referencia: si después cambia de nombre o se
        // desactiva, el historial debe seguir diciendo quién actuó entonces.
        actorId: user.id,
        actorNombre: user.nombre,
        actorRol: user.role,
        fecha: new Date().toISOString(),
        ...(evento.motivo ? { motivo: evento.motivo } : {}),
        ...(evento.aprobadoPorId ? { aprobadoPorId: evento.aprobadoPorId } : {}),
        ...(evento.aprobadoPorNombre ? { aprobadoPorNombre: evento.aprobadoPorNombre } : {}),
      });
    },
    [agregarEntrada, user],
  );
}

/**
 * Construye la lista de cambios comparando dos versiones de un objeto.
 *
 * Registrar solo los campos que efectivamente cambiaron es lo que hace el log
 * legible: guardar el objeto completo en cada edición obliga a quien audita a
 * comparar dos volcados JSON para encontrar la diferencia.
 */
export function diffCampos<T extends Record<string, unknown>>(
  antes: T,
  despues: T,
  etiquetas: Partial<Record<keyof T, string>> = {},
  formatear: Partial<Record<keyof T, (v: unknown) => string | null>> = {},
): CambioCampo[] {
  const cambios: CambioCampo[] = [];

  for (const clave of Object.keys(despues) as Array<keyof T>) {
    const valorAntes = antes[clave];
    const valorDespues = despues[clave];
    if (Object.is(valorAntes, valorDespues)) continue;

    // Comparación estructural para arreglos y objetos: `Object.is` los
    // reporta como distintos aunque su contenido sea igual.
    if (JSON.stringify(valorAntes) === JSON.stringify(valorDespues)) continue;

    const fmt =
      formatear[clave] ?? ((v: unknown) => (v === null || v === undefined || v === '' ? null : String(v)));

    cambios.push({
      campo: etiquetas[clave] ?? String(clave),
      antes: fmt(valorAntes),
      despues: fmt(valorDespues),
    });
  }

  return cambios;
}
