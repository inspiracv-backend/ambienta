'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { AccionAuditable, AuditLogEntry, CambioCampo, EntidadAuditable } from '@ambienta/shared';
import { useSession } from '@/lib/session';
import { api } from '@/lib/api-client';

export interface EventoAuditable {
  entidadTipo: EntidadAuditable;
  entidadId: string;
  entidadLabel: string;
  accion: AccionAuditable;
  resumen: string;
  tenantId?: string | null;
  cambios?: CambioCampo[];
  motivo?: string;
  aprobadoPorId?: string;
  aprobadoPorNombre?: string;
}

export interface RefEntidad {
  tipo: EntidadAuditable;
  id: string;
}

interface AuditLogContextValue {
  entries: AuditLogEntry[];
  loading: boolean;
  agregarEntrada: (entry: AuditLogEntry) => void;
  historialDe: (entidadTipo: EntidadAuditable, entidadId: string) => AuditLogEntry[];
  historialDeVarias: (refs: RefEntidad[]) => AuditLogEntry[];
}

const AuditLogContext = createContext<AuditLogContextValue | null>(null);

export function AuditLogProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // **Este store no le pregunta nada a la API, y conviene decirlo.**
    //
    // `entries` solo se llena con `agregarEntrada`, o sea con lo que ocurre en
    // **esta** sesion del navegador: al recargar, el historial queda vacio.
    // `GET /audit-log/` existe desde hace tiempo y nadie lo llama — el mismo
    // patron de `bcn.sincronizar()` y `control_documental.py`.
    //
    // Hasta #208 eso se tapaba arrancando con `mockAuditLog`, o sea mostrando
    // un **registro de auditoria inventado**. En cualquier modulo eso es malo;
    // en este es lo peor posible, porque el valor entero del audit log es que
    // se pueda confiar en el ante una fiscalizacion.
    //
    // Vacio dice la verdad. Conectarlo es trabajo aparte: hay que mapear la
    // forma de la API a `AuditLogEntry`.
    setLoading(false);
  }, []);

  const agregarEntrada = useCallback((entry: AuditLogEntry) => {
    setEntries((prev) => [...prev, entry]);
  }, []);

  const historialDe = useCallback(
    (entidadTipo: EntidadAuditable, entidadId: string) =>
      entries
        .map((e, indice) => ({ e, indice }))
        .filter(({ e }) => e.entidadTipo === entidadTipo && e.entidadId === entidadId)
        .sort((a, b) => {
          const porFecha = new Date(b.e.fecha).getTime() - new Date(a.e.fecha).getTime();
          return porFecha !== 0 ? porFecha : b.indice - a.indice;
        })
        .map(({ e }) => e),
    [entries],
  );

  const historialDeVarias = useCallback(
    (refs: RefEntidad[]) => {
      const claves = new Set(refs.map((r) => `${r.tipo}:${r.id}`));
      return entries
        .map((e, indice) => ({ e, indice }))
        .filter(({ e }) => claves.has(`${e.entidadTipo}:${e.entidadId}`))
        .sort((a, b) => {
          const porFecha = new Date(b.e.fecha).getTime() - new Date(a.e.fecha).getTime();
          return porFecha !== 0 ? porFecha : b.indice - a.indice;
        })
        .map(({ e }) => e);
    },
    [entries],
  );

  const value = useMemo(
    () => ({ entries, loading, agregarEntrada, historialDe, historialDeVarias }),
    [entries, loading, agregarEntrada, historialDe, historialDeVarias],
  );

  return <AuditLogContext.Provider value={value}>{children}</AuditLogContext.Provider>;
}

export function useAuditLog() {
  const ctx = useContext(AuditLogContext);
  if (!ctx) throw new Error('useAuditLog debe usarse dentro de <AuditLogProvider>');
  return ctx;
}

export function useRegistrarAuditoria() {
  const { agregarEntrada } = useAuditLog();
  const { user } = useSession();

  return useCallback(
    (evento: EventoAuditable) => {
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
