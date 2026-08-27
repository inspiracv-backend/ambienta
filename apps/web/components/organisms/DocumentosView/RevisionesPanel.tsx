'use client';

import { useEffect, useRef, useState } from 'react';
import {
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  ShieldCheck,
  UploadCloud,
} from 'lucide-react';
import {
  ETIQUETA_TIPO_DOCUMENTO,
  esControlado,
  sirveComoEvidencia,
  tamanoLegible,
  transicionesDesde,
  type EstadoRevision,
  type RevisionDocumental,
} from '@ambienta/shared';
import { Button, StatusBadge } from '@/components/atoms';
import {
  estadoRevisionSemaforo,
  etiquetaEstadoRevision,
} from '@/lib/documento-status';
import { ACCION_HACIA, ETIQUETA_ACCION } from '@/lib/documentos';
import { useDocumentos } from '@/lib/documentos-store';
import { fecha } from '@/lib/fechas';
import type { RevisionesPanelProps } from './DocumentosView.types';

const TEXTO_DEL_PASO: Record<string, string> = {
  'pidiendo-permiso': 'Pidiendo permiso de subida…',
  subiendo: 'Subiendo el archivo…',
  confirmando: 'Confirmando con el servidor…',
};

/**
 * Las revisiones de un documento, con su ciclo de vida (RF-104 a RF-106).
 *
 * ## Lo que esta pantalla tiene que dejar claro de un vistazo
 *
 * **Cuál sirve como evidencia.** Es la pregunta que se hace alguien cuando
 * llega una fiscalización, y la respuesta no es "la última": es la que está
 * **vigente**. Una revisión aprobada todavía no rige — rige la anterior — y
 * confundirlas significa mostrarle a un fiscalizador un documento que no
 * corresponde. Por eso la vigente lleva un distintivo propio además del
 * semáforo.
 *
 * ## Los botones sólo ofrecen transiciones que existen
 *
 * Salen de `transicionesDesde()`, que es el espejo de `TRANSICIONES` en la API.
 * Si las dos listas se separan, manda la de la API: la persona vería un 409, lo
 * que es molesto pero no peligroso. Al revés —ofrecer menos de lo permitido—
 * sería una función escondida.
 */
export function RevisionesPanel({ documento, revisiones, cargando }: RevisionesPanelProps) {
  const { subir, subiendo, mover, descargar } = useDocumentos();
  const inputRef = useRef<HTMLInputElement>(null);
  const [pidiendoMotivo, setPidiendoMotivo] = useState<string | null>(null);
  const [motivo, setMotivo] = useState('');

  // Al cambiar de documento, el formulario de motivo abierto ya no aplica.
  useEffect(() => {
    setPidiendoMotivo(null);
    setMotivo('');
  }, [documento.id]);

  const controlado = esControlado(documento.tipo);
  const subiendoAca = subiendo?.documentoId === documento.id ? subiendo : null;

  async function alElegirArchivo(archivos: FileList | null) {
    const archivo = archivos?.[0];
    if (!archivo) return;
    await subir(documento.id, archivo);
    if (inputRef.current) inputRef.current.value = '';
  }

  async function confirmarObsolescencia(revisionId: string) {
    if (!motivo.trim()) return;
    const ok = await mover(documento.id, revisionId, 'obsolete', { motivo: motivo.trim() });
    if (ok) {
      setPidiendoMotivo(null);
      setMotivo('');
    }
  }

  return (
    <section className="flex flex-col gap-4" aria-labelledby="titulo-revisiones">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="titulo-revisiones" className="text-lg font-semibold text-slate-900">
            {documento.titulo}
          </h2>
          <p className="text-sm text-slate-500">
            {documento.codigo ? (
              <span className="font-mono text-slate-700">{documento.codigo}</span>
            ) : (
              <span className="italic">Sin código asignado</span>
            )}
            {' · '}
            {ETIQUETA_TIPO_DOCUMENTO[documento.tipo] ?? documento.tipo}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="file"
            className="sr-only"
            id={`subir-${documento.id}`}
            onChange={(e) => alElegirArchivo(e.target.files)}
          />
          <Button
            onClick={() => inputRef.current?.click()}
            isLoading={!!subiendoAca}
            icon={<UploadCloud className="h-4 w-4" aria-hidden />}
          >
            Subir revisión
          </Button>
        </div>
      </header>

      {!controlado && (
        <p className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-600">
          Este tipo de archivo <strong>no lleva ciclo de vida</strong>: se guarda y se
          descarga, pero no se aprueba ni se pone en vigencia. Aprobar un comprobante
          que devolvió un portal del Estado no tendría sentido.
        </p>
      )}

      {subiendoAca && (
        <p
          role="status"
          className="flex items-center gap-2 rounded-lg bg-brand-50 px-4 py-3 text-sm text-brand-700"
        >
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          <span>
            {TEXTO_DEL_PASO[subiendoAca.paso] ?? 'Subiendo…'}{' '}
            <span className="text-brand-600">{subiendoAca.nombreArchivo}</span>
          </span>
          {subiendoAca.paso !== 'confirmando' && (
            // El archivo viaja directo al bucket; si la pestaña se cierra entre
            // la subida y la confirmación, queda un objeto sin fila que lo
            // represente. Se avisa en vez de darlo por resuelto.
            <span className="ml-auto text-xs text-brand-600">
              No cierres esta pestaña hasta que termine.
            </span>
          )}
        </p>
      )}

      {cargando ? (
        <p className="flex items-center gap-2 py-8 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Cargando revisiones…
        </p>
      ) : !revisiones || revisiones.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
          <FileText className="h-6 w-6 text-slate-400" aria-hidden />
          <p className="font-medium text-slate-700">Este documento no tiene archivos todavía</p>
          <p>
            Sube la primera revisión. Nace como borrador y no sirve como evidencia hasta
            que esté vigente.
          </p>
        </div>
      ) : (
        <ol className="flex flex-col gap-3">
          {revisiones.map((rev) => (
            <li
              key={rev.id}
              className="rounded-card border border-slate-200 bg-white p-4"
              data-testid={`revision-${rev.numero}`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-slate-800">Revisión {rev.numero}</span>
                    <StatusBadge
                      status={estadoRevisionSemaforo(rev.estado)}
                      label={etiquetaEstadoRevision(rev.estado)}
                    />
                    {sirveComoEvidencia(rev.estado) && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-semaforo-cumple-bg px-2.5 py-1 text-xs font-medium text-semaforo-cumple">
                        <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
                        Sirve como evidencia
                      </span>
                    )}
                  </p>
                  <p className="truncate text-sm text-slate-500">
                    {rev.nombreArchivo} · {tamanoLegible(rev.tamanoBytes)} · subida el{' '}
                    {fecha(rev.creadaEn)}
                  </p>
                  {rev.aprobadaEn && (
                    <p className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">
                      <CheckCircle2 className="h-3.5 w-3.5 text-semaforo-cumple" aria-hidden />
                      Aprobada el {fecha(rev.aprobadaEn)}
                    </p>
                  )}
                  {rev.rigeDesde && (
                    <p className="text-xs text-slate-500">
                      Rige desde {fecha(rev.rigeDesde)}
                      {rev.rigeHasta ? ` hasta ${fecha(rev.rigeHasta)}` : ''}
                    </p>
                  )}
                  {rev.motivoObsolescencia && (
                    <p className="mt-1 text-xs text-slate-500">
                      <span className="font-medium">Retirada:</span> {rev.motivoObsolescencia}
                    </p>
                  )}
                </div>

                <div className="flex flex-wrap items-center justify-end gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => descargar(documento.id, rev.id)}
                    icon={<Download className="h-4 w-4" aria-hidden />}
                  >
                    Descargar
                  </Button>

                  {controlado &&
                    transicionesDesde(rev.estado).map((destino: EstadoRevision) => {
                      const accion = ACCION_HACIA[destino];
                      if (destino === 'obsoleto') {
                        return (
                          <Button
                            key={destino}
                            variant="secondary"
                            size="sm"
                            onClick={() => {
                              setPidiendoMotivo(rev.id);
                              setMotivo('');
                            }}
                          >
                            {ETIQUETA_ACCION.obsolete}
                          </Button>
                        );
                      }
                      return (
                        <Button
                          key={destino}
                          size="sm"
                          variant={destino === 'vigente' ? 'primary' : 'secondary'}
                          onClick={() => mover(documento.id, rev.id, accion)}
                        >
                          {ETIQUETA_ACCION[accion]}
                        </Button>
                      );
                    })}
                </div>
              </div>

              {pidiendoMotivo === rev.id && (
                <div className="mt-3 rounded-lg bg-slate-50 p-3">
                  <label
                    htmlFor={`motivo-${rev.id}`}
                    className="block text-sm font-medium text-slate-700"
                  >
                    ¿Por qué deja de regir?
                  </label>
                  <p className="mb-2 text-xs text-slate-500">
                    Es obligatorio. Un documento retirado sin explicación obliga a quien lo
                    encuentre a adivinar si todavía sirve, y en la duda se usa.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <input
                      id={`motivo-${rev.id}`}
                      value={motivo}
                      onChange={(e) => setMotivo(e.target.value)}
                      placeholder="Ej.: cambió la normativa aplicable"
                      className="h-10 min-w-[16rem] flex-1 rounded-lg border border-slate-300 px-3 text-sm"
                    />
                    <Button
                      size="sm"
                      disabled={!motivo.trim()}
                      onClick={() => confirmarObsolescencia(rev.id)}
                    >
                      {/*
                        "Confirmar retiro" y no "Marcar obsoleta" otra vez: el
                        botón que abre este formulario ya se llama así, y dos
                        botones con el mismo nombre en la misma fila suenan
                        idénticos en un lector de pantalla. Se vio al manejar
                        la pantalla, no leyendo el código.
                      */}
                      Confirmar retiro
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => setPidiendoMotivo(null)}
                    >
                      Cancelar
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
