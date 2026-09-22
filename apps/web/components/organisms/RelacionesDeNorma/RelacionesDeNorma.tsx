'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, mensajeDeError } from '@/lib/api-client';
import type { RelacionDeNorma, RelacionesDeNormaProps } from './RelacionesDeNorma.types';

/**
 * Cómo se lee cada relación desde esta norma. La concordancia es simétrica.
 * `deroga` y `referencia` los admite la base aunque la BCN no los publique.
 */
const ETIQUETA: Record<string, { saliente: string; entrante: string }> = {
  modifica: { saliente: 'Modifica a', entrante: 'Modificada por' },
  reglamenta: { saliente: 'Reglamenta a', entrante: 'Reglamentada por' },
  refundido: { saliente: 'Refunde a', entrante: 'Refundida por' },
  rectifica: { saliente: 'Rectifica a', entrante: 'Rectificada por' },
  concordancia: { saliente: 'Concuerda con', entrante: 'Concuerda con' },
  deroga: { saliente: 'Deroga a', entrante: 'Derogada por' },
  referencia: { saliente: 'Hace referencia a', entrante: 'Referida por' },
};

const TIPO_CORTO: Record<string, string> = {
  ley: 'Ley',
  decreto_supremo: 'D.S.',
  decreto: 'Decreto',
  resolucion: 'Res.',
};

function nombreCorto(r: RelacionDeNorma): string {
  const tipo = r.norm_type ? TIPO_CORTO[r.norm_type] ?? r.norm_type : '';
  const anio = r.publication_date ? ` (${r.publication_date.slice(0, 4)})` : '';
  return `${tipo} ${r.norm_number ?? ''}`.trim() + anio;
}

/**
 * Qué normas modifican, reglamentan o concuerdan con esta, según la BCN
 * (`GET /catalog/norms/{id}/relations`). Hasta el 21-sep la tabla existía y
 * nadie la escribía: evaluar una norma sin saber que otra la modificó es
 * evaluar un texto que quizás ya cambió.
 *
 * Solo entre normas del catálogo. Las que apuntan a una norma que no se importó
 * quedan en la bitácora de la sincronización, no acá.
 */
export function RelacionesDeNorma({ normId, tenantId }: RelacionesDeNormaProps) {
  const [filas, setFilas] = useState<RelacionDeNorma[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vigente = true;
    setFilas(null);
    setError(null);
    api
      .get<RelacionDeNorma[]>(`/catalog/norms/${normId}/relations`, { tenantId })
      .then((f) => {
        if (vigente) setFilas(f ?? []);
      })
      .catch((e: unknown) => {
        if (vigente) setError(mensajeDeError(e));
      });
    return () => {
      vigente = false;
    };
  }, [normId, tenantId]);

  return (
    <section aria-labelledby="relaciones-de-la-norma" className="rounded-card border border-slate-200 bg-white p-6">
      <h2 id="relaciones-de-la-norma" className="text-sm font-semibold text-slate-900">
        Relaciones con otras normas
      </h2>
      {error ? (
        <p role="alert" className="mt-2 text-sm text-semaforo-no-cumple">
          No se pudieron cargar las relaciones: {error}
        </p>
      ) : filas === null ? (
        <p className="mt-2 text-sm text-slate-500">Cargando…</p>
      ) : filas.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">
          La BCN no registra relaciones de esta norma con otras del catálogo.
        </p>
      ) : (
        <ul className="mt-3 flex flex-col gap-2 text-sm">
          {filas.map((r) => (
            <li key={`${r.relation_type}-${r.sentido}-${r.norm_id}`} className="flex flex-wrap gap-x-2">
              <span className="font-medium text-slate-700">
                {ETIQUETA[r.relation_type]?.[r.sentido] ?? r.relation_type}
              </span>
              <Link href={`/matriz-legal/${r.norm_id}`} className="text-brand-600 hover:underline">
                {nombreCorto(r)}
              </Link>
              <span className="min-w-0 truncate text-slate-500" title={r.title}>
                {r.title}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
