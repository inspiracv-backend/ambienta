'use client';

import { useId, useState } from 'react';
import { FileSpreadsheet } from 'lucide-react';
import { Button } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import {
  buildCumplimientoReport,
  buildMatrizLegalReport,
  buildNoConformidadesReport,
  downloadTextFile,
  type TipoReporte,
} from '@/lib/reports';
import type { ReportGeneratorProps } from './ReportGenerator.types';

const TIPOS: { value: TipoReporte; label: string }[] = [
  { value: 'cumplimiento', label: 'Cumplimiento' },
  { value: 'no-conformidades', label: 'No Conformidades' },
  { value: 'matriz-legal', label: 'Matriz Legal' },
];

/**
 * S-39 Reportes. Exporta un CSV real (se abre directamente en Excel) calculado
 * a partir de los datos ya cargados en los stores — sin backend ni PDF real
 * en esta iteración (ver gap RF-50 en seccion-m-reportes.md).
 */
export function ReportGenerator({ plants, obligations, norms, nonConformities }: ReportGeneratorProps) {
  const formId = useId();
  const [tipo, setTipo] = useState<TipoReporte>('cumplimiento');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const usaRangoFechas = tipo !== 'matriz-legal';

  function handleGenerar() {
    setSuccess('');
    if (usaRangoFechas && desde && hasta && hasta < desde) {
      setError('La fecha "hasta" no puede ser anterior a la fecha "desde".');
      return;
    }
    setError('');

    const rango = usaRangoFechas ? { desde, hasta } : { desde: '', hasta: '' };
    const result =
      tipo === 'cumplimiento'
        ? buildCumplimientoReport(plants, obligations, norms, rango.desde, rango.hasta)
        : tipo === 'no-conformidades'
          ? buildNoConformidadesReport(plants, nonConformities, rango.desde, rango.hasta)
          : buildMatrizLegalReport(norms, plants);

    if (result.empty) {
      setError('No hay registros en el rango seleccionado.');
      return;
    }

    const fecha = new Date().toISOString().slice(0, 10);
    downloadTextFile(`reporte-${tipo}-${fecha}.csv`, result.csv, 'text/csv;charset=utf-8');
    setSuccess('Reporte exportado.');
  }

  return (
    <div className="flex flex-col gap-4 rounded-card border border-slate-200 bg-white p-5">
      <div>
        <h2 className="text-base font-semibold text-slate-900">Generar reporte</h2>
        <p className="text-sm text-slate-500">
          Exporta un archivo CSV (compatible con Excel) con los datos del rango seleccionado.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <FormField label="Tipo de reporte" htmlFor={`${formId}-tipo`}>
          <select
            id={`${formId}-tipo`}
            className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoReporte)}
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

      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-slate-400">
          Generación de PDF pendiente de una librería aprobada — por ahora se exporta en CSV.
        </p>
        <Button icon={<FileSpreadsheet className="h-4 w-4" aria-hidden />} onClick={handleGenerar}>
          Generar y exportar
        </Button>
      </div>
    </div>
  );
}
