'use client';

import { useMemo, useState } from 'react';
import { FileText, Inbox } from 'lucide-react';
import {
  ETIQUETA_TIPO_DOCUMENTO,
  TIPOS_DOCUMENTO_CONTROLADO,
  esControlado,
} from '@ambienta/shared';
import { StatusBadge } from '@/components/atoms';
import { FilterBar } from '@/components/molecules';
import {
  estadoDocumentoSemaforo,
  etiquetaEstadoDocumento,
} from '@/lib/documento-status';
import { cn } from '@/lib/utils';
import type { DocumentosListaProps } from './DocumentosView.types';

/**
 * El listado de documentos controlados (RF-102, RF-103).
 *
 * El **código** va primero y en monoespaciada: es lo que se cita en una
 * auditoría —"muéstrenme el PR-07"— y lo que la persona busca con la vista.
 * El título es lo que confirma que es el correcto, no lo que lo identifica.
 */
export function DocumentosLista({
  documentos,
  seleccionadoId,
  onSeleccionar,
}: DocumentosListaProps) {
  const [tipoFiltro, setTipoFiltro] = useState('todos');
  const [estadoFiltro, setEstadoFiltro] = useState('todos');
  const [texto, setTexto] = useState('');

  const filtrados = useMemo(() => {
    const buscado = texto.trim().toLowerCase();
    return documentos.filter((d) => {
      if (tipoFiltro === 'controlados' && !esControlado(d.tipo)) return false;
      if (tipoFiltro !== 'todos' && tipoFiltro !== 'controlados' && d.tipo !== tipoFiltro) {
        return false;
      }
      if (estadoFiltro !== 'todos' && d.estado !== estadoFiltro) return false;
      if (
        buscado &&
        !`${d.codigo ?? ''} ${d.titulo}`.toLowerCase().includes(buscado)
      ) {
        return false;
      }
      return true;
    });
  }, [documentos, tipoFiltro, estadoFiltro, texto]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <FilterBar
          filters={[
            {
              id: 'filtro-tipo-doc',
              label: 'Tipo',
              value: tipoFiltro,
              onChange: setTipoFiltro,
              options: [
                { value: 'todos', label: 'Todos los tipos' },
                { value: 'controlados', label: 'Sólo documentación controlada' },
                ...TIPOS_DOCUMENTO_CONTROLADO.map((t) => ({
                  value: t,
                  label: ETIQUETA_TIPO_DOCUMENTO[t] ?? t,
                })),
              ],
            },
            {
              id: 'filtro-estado-doc',
              label: 'Estado',
              value: estadoFiltro,
              onChange: setEstadoFiltro,
              options: [
                { value: 'todos', label: 'Todos los estados' },
                { value: 'vigente', label: 'Vigente' },
                { value: 'en_revision', label: 'En revisión' },
                { value: 'borrador', label: 'Sin nada vigente' },
                { value: 'obsoleto', label: 'Obsoleto' },
              ],
            },
          ]}
        />
        <div className="flex flex-col gap-1">
          <label htmlFor="buscar-doc" className="text-xs font-medium text-slate-600">
            Buscar
          </label>
          <input
            id="buscar-doc"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Código o título"
            className="h-11 w-56 rounded-lg border border-slate-300 px-3 text-sm"
          />
        </div>
      </div>

      {filtrados.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
          <Inbox className="h-6 w-6 text-slate-400" aria-hidden />
          {documentos.length === 0 ? (
            <>
              <p className="font-medium text-slate-700">Todavía no hay documentos</p>
              <p>
                Crea el primero y súbele un archivo. Nada de lo que veas acá es de
                ejemplo: si está en la lista, está en la empresa.
              </p>
            </>
          ) : (
            <p>Ningún documento coincide con estos filtros.</p>
          )}
        </div>
      ) : (
        <ul className="flex flex-col gap-2" aria-label="Documentos">
          {filtrados.map((doc) => (
            <li key={doc.id}>
              <button
                type="button"
                onClick={() => onSeleccionar(doc.id)}
                aria-current={doc.id === seleccionadoId ? 'true' : undefined}
                className={cn(
                  'flex w-full items-start gap-3 rounded-card border p-3 text-left transition',
                  doc.id === seleccionadoId
                    ? 'border-brand-500 bg-brand-50'
                    : 'border-slate-200 bg-white hover:bg-slate-50',
                )}
              >
                <FileText className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    {doc.codigo ? (
                      <span className="font-mono text-sm font-semibold text-slate-800">
                        {doc.codigo}
                      </span>
                    ) : (
                      <span className="text-sm italic text-slate-500">Sin código</span>
                    )}
                    <StatusBadge
                      status={estadoDocumentoSemaforo(doc.estado)}
                      label={etiquetaEstadoDocumento(doc.estado)}
                    />
                  </span>
                  <span className="block truncate text-sm text-slate-700">{doc.titulo}</span>
                  <span className="block text-xs text-slate-500">
                    {ETIQUETA_TIPO_DOCUMENTO[doc.tipo] ?? doc.tipo}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
