'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { SALIDAS_REGLAMENTARIAS } from '@ambienta/shared';
import { mensajeDeError } from '@/lib/api-client';
import { cargarPendientesDeLaEmpresa, type CompromisoApi } from '@/lib/compromisos';
import { fecha } from '@/lib/fechas';
import { useSession } from '@/lib/session';

/**
 * Lo que el sistema de gestión todavía debe: las salidas que una verificación
 * de eficacia dejó comprometidas y nadie ejecutó ni descartó (ISO 9001 §10.2.1).
 *
 * **Por qué existe esta lista.** Hasta el 4-oct las salidas vivían dentro del
 * JSON de la etapa de seguimiento: alguien marcaba "SI", cerraba el registro, y
 * no había forma de preguntar qué quedó pendiente. Es el hallazgo que levanta un
 * auditor al revisar la eficacia del propio sistema de gestión.
 *
 * Los tres estados se ven distinto a propósito: "comprobando" no es "no hay
 * ninguna", y "no se pudo preguntar" tampoco.
 */
export function SalidasPendientes() {
  const { user } = useSession();
  const tenantId = user?.tenantId ?? null;
  const [filas, setFilas] = useState<CompromisoApi[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tenantId) return;
    let vigente = true;
    setFilas(null);
    setError(null);
    cargarPendientesDeLaEmpresa(tenantId)
      .then((f) => {
        if (vigente) setFilas(f ?? []);
      })
      .catch((e: unknown) => {
        if (vigente) setError(mensajeDeError(e));
      });
    return () => {
      vigente = false;
    };
  }, [tenantId]);

  const etiqueta = (kind: string) =>
    SALIDAS_REGLAMENTARIAS.find((s) => s.value === kind)?.label ?? kind;

  return (
    <section aria-labelledby="salidas-pendientes" className="rounded-card border border-slate-200 bg-white p-6">
      <h2 id="salidas-pendientes" className="text-sm font-semibold text-slate-900">
        Salidas comprometidas pendientes
      </h2>
      <p className="mt-1 text-xs text-slate-500">
        Lo que una verificación de eficacia dejó comprometido y todavía nadie ejecutó ni descartó.
      </p>

      {error ? (
        <p role="alert" className="mt-3 text-sm text-semaforo-no-cumple">
          No se pudieron cargar: {error}
        </p>
      ) : filas === null ? (
        <p className="mt-3 text-sm text-slate-500">Comprobando…</p>
      ) : filas.length === 0 ? (
        <p className="mt-3 text-sm text-semaforo-cumple">
          Ninguna pendiente: lo comprometido está ejecutado o descartado con justificación.
        </p>
      ) : (
        <ul className="mt-3 flex flex-col gap-2 text-sm">
          {filas.map((c) => (
            <li key={c.id} className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-medium text-slate-800">{etiqueta(c.kind)}</span>
              <Link href={`/no-conformidades/${c.nonconformity_id}`} className="text-brand-600 hover:underline">
                {c.nonconformity_code ?? 'Ver registro'}
              </Link>
              <span className="text-slate-500">
                {c.responsable_nombre ?? 'Sin responsable'}
                {' · '}
                {c.due_date ? fecha(c.due_date) : 'sin fecha'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
