'use client';

import { useId, useState } from 'react';
import { FileSpreadsheet, FileText, Printer } from 'lucide-react';
import { Button } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { ReporteImprimible } from '@/components/organisms/ReporteImprimible';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import {
  FORMATO_POR_DEFECTO,
  buildCumplimientoReport,
  buildMatrizLegalReport,
  buildNoConformidadesReport,
  downloadTextFile,
  type FormatoReporte,
  type Reporte,
  type TipoReporte,
} from '@/lib/reports';
import type { ReportGeneratorProps } from './ReportGenerator.types';

const TIPOS: { value: TipoReporte; label: string }[] = [
  { value: 'cumplimiento', label: 'Cumplimiento' },
  { value: 'no-conformidades', label: 'No Conformidades' },
  { value: 'matriz-legal', label: 'Matriz Legal' },
];

/**
 * Los dos formatos, con lo que cada uno sirve.
 *
 * El orden no es alfabetico ni casual: **el primero es el que sale por
 * defecto**, y quien no lea la descripcion se lleva el que casi siempre queria.
 */
const FORMATOS: { value: FormatoReporte; label: string; ayuda: string }[] = [
  { value: 'pdf', label: 'PDF', ayuda: 'Documento para entregar a un fiscalizador o certificador' },
  { value: 'csv', label: 'CSV / Excel', ayuda: 'Planilla para procesar los datos en otra herramienta' },
];

/**
 * S-39 Reportes (RF-50). **PDF por defecto, CSV a un clic.**
 *
 * ## Por que cambio el defecto
 *
 * Esta pantalla exportaba solo CSV y avisaba que *"la generacion de PDF queda
 * pendiente de una libreria aprobada"*. **Esa frase ya era falsa**: el informe
 * de cumplimiento imprimible existe desde hace tiempo y produce un PDF de
 * verdad — con texto seleccionable, enlaces vivos y el encabezado de la
 * empresa auditada— usando el motor del navegador. Lo que faltaba no era la
 * libreria: era que el selector de exportacion lo ofreciera, y que existiera
 * el documento para los otros dos tipos de reporte.
 *
 * Un reporte de cumplimiento casi siempre se pide para **entregarlo**. Una
 * planilla no se entrega: se procesa. Por eso el defecto es el documento y no
 * el archivo de datos.
 *
 * ## Los dos formatos salen del mismo `Reporte`
 *
 * `headers` y `rows` se calculan una vez; el CSV se deriva y el PDF los pinta.
 * Construirlos por separado seria tener dos reportes con el mismo nombre, y el
 * dia que alguien agregue una columna a uno solo, la planilla y el documento
 * entregado dirian cosas distintas sobre la misma empresa.
 */
export function ReportGenerator({
  plants,
  obligations,
  norms,
  nonConformities,
  tenant,
  usuario,
}: ReportGeneratorProps) {
  const formId = useId();
  const registrar = useRegistrarAuditoria();
  const [tipo, setTipo] = useState<TipoReporte>('cumplimiento');
  const [formato, setFormato] = useState<FormatoReporte>(FORMATO_POR_DEFECTO);
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [paraImprimir, setParaImprimir] = useState<Reporte | null>(null);

  const usaRangoFechas = tipo !== 'matriz-legal';
  const puedeImprimir = Boolean(tenant && usuario);

  function construir(): Reporte {
    const rango = usaRangoFechas ? { desde, hasta } : { desde: '', hasta: '' };
    if (tipo === 'cumplimiento') {
      return buildCumplimientoReport(plants, obligations, norms, rango.desde, rango.hasta);
    }
    if (tipo === 'no-conformidades') {
      return buildNoConformidadesReport(plants, nonConformities, rango.desde, rango.hasta);
    }
    return buildMatrizLegalReport(norms, plants);
  }

  function handleGenerar() {
    setSuccess('');
    setParaImprimir(null);
    if (usaRangoFechas && desde && hasta && hasta < desde) {
      setError('La fecha "hasta" no puede ser anterior a la fecha "desde".');
      return;
    }
    setError('');

    const reporte = construir();
    if (reporte.empty) {
      setError('No hay registros en el rango seleccionado.');
      return;
    }

    if (formato === 'csv') {
      const fecha = new Date().toISOString().slice(0, 10);
      downloadTextFile(`reporte-${tipo}-${fecha}.csv`, reporte.csv, 'text/csv;charset=utf-8');
      setSuccess('Planilla exportada.');
      return;
    }

    // El documento se muestra **antes** de imprimir en vez de disparar el
    // dialogo de una: quien lo va a entregar necesita verlo primero, y el
    // dialogo del navegador tapa la pantalla sin dejar revisarlo.
    setParaImprimir(reporte);
    setSuccess('Documento listo. Revisalo y usa "Imprimir / Guardar PDF".');
  }

  function handleImprimir() {
    if (!tenant || !paraImprimir) return;
    // Queda registrado: RNF-26 pide trazabilidad de lo que sale del sistema
    // para auditorias externas, y un documento entregado a un tercero es
    // exactamente eso.
    registrar({
      entidadTipo: 'tenant',
      entidadId: tenant.id,
      entidadLabel: tenant.nombre,
      tenantId: tenant.id,
      accion: 'exportado',
      resumen: `Emitio "${paraImprimir.titulo}" en PDF`,
      cambios: [{ campo: 'Filas', antes: null, despues: String(paraImprimir.rows.length) }],
    });
    window.print();
  }

  return (
    <>
      <div className="flex flex-col gap-4 rounded-card border border-slate-200 bg-white p-5 print:hidden">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Generar reporte</h2>
          <p className="text-sm text-slate-500">
            Un documento PDF para entregar, o una planilla para procesar los datos.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Tipo de reporte" htmlFor={`${formId}-tipo`}>
            <select
              id={`${formId}-tipo`}
              className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
              value={tipo}
              onChange={(e) => {
                setTipo(e.target.value as TipoReporte);
                setParaImprimir(null);
                setSuccess('');
              }}
            >
              {TIPOS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label="Desde" htmlFor={`${formId}-desde`}>
            <input
              id={`${formId}-desde`}
              type="date"
              disabled={!usaRangoFechas}
              className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm disabled:bg-slate-50 disabled:text-slate-400"
              value={desde}
              onChange={(e) => setDesde(e.target.value)}
            />
          </FormField>

          <FormField label="Hasta" htmlFor={`${formId}-hasta`}>
            <input
              id={`${formId}-hasta`}
              type="date"
              disabled={!usaRangoFechas}
              className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm disabled:bg-slate-50 disabled:text-slate-400"
              value={hasta}
              onChange={(e) => setHasta(e.target.value)}
            />
          </FormField>
        </div>

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-slate-700">Formato</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {FORMATOS.map((f) => (
              <button
                key={f.value}
                type="button"
                onClick={() => {
                  setFormato(f.value);
                  setParaImprimir(null);
                  setSuccess('');
                }}
                aria-pressed={formato === f.value}
                disabled={f.value === 'pdf' && !puedeImprimir}
                className={
                  formato === f.value
                    ? 'rounded-lg border-2 border-brand-600 bg-brand-50 px-3 py-2.5 text-left disabled:opacity-50'
                    : 'rounded-lg border border-slate-300 px-3 py-2.5 text-left hover:border-slate-400 hover:bg-slate-50 disabled:opacity-50'
                }
              >
                <span className="flex items-center gap-1.5">
                  {f.value === 'pdf' ? (
                    <FileText className="h-4 w-4 text-slate-500" aria-hidden />
                  ) : (
                    <FileSpreadsheet className="h-4 w-4 text-slate-500" aria-hidden />
                  )}
                  <span
                    className={
                      formato === f.value
                        ? 'text-sm font-semibold text-brand-700'
                        : 'text-sm font-medium text-slate-700'
                    }
                  >
                    {f.label}
                  </span>
                </span>
                <span className="mt-0.5 block text-xs leading-snug text-slate-500">{f.ayuda}</span>
              </button>
            ))}
          </div>
        </fieldset>

        {!usaRangoFechas && (
          <p className="text-xs text-slate-500">
            La Matriz Legal es estructural/anual — este reporte no filtra por fecha.
          </p>
        )}

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        {success && (
          <p role="status" className="text-sm text-brand-700">
            {success}
          </p>
        )}

        <div className="flex flex-wrap items-center justify-end gap-3">
          <Button
            icon={
              formato === 'pdf' ? (
                <FileText className="h-4 w-4" aria-hidden />
              ) : (
                <FileSpreadsheet className="h-4 w-4" aria-hidden />
              )
            }
            onClick={handleGenerar}
          >
            {formato === 'pdf' ? 'Generar documento' : 'Exportar planilla'}
          </Button>
          {paraImprimir && (
            <Button
              variant="secondary"
              icon={<Printer className="h-4 w-4" aria-hidden />}
              onClick={handleImprimir}
            >
              Imprimir / Guardar PDF
            </Button>
          )}
        </div>
      </div>

      {paraImprimir && tenant && usuario && (
        <ReporteImprimible
          tenant={tenant}
          usuario={usuario}
          reporte={paraImprimir}
          subtitulo={
            usaRangoFechas && (desde || hasta)
              ? `Periodo ${desde || 'inicio'} — ${hasta || 'hoy'}`
              : undefined
          }
        />
      )}
    </>
  );
}
