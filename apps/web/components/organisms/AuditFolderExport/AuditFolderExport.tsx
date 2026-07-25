'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { FolderDown, CheckCircle2 } from 'lucide-react';
import { Button, Spinner } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { buildAuditFolderContent } from '@/lib/reports';
import type { AuditFolderExportProps } from './AuditFolderExport.types';

type Progreso = 'idle' | 'recopilando' | 'generando' | 'listo';

const PASO_LABEL: Record<Exclude<Progreso, 'idle'>, string> = {
  recopilando: 'Recopilando evidencias y hallazgos…',
  generando: 'Generando documento consolidado…',
  listo: 'Carpeta lista.',
};

const ENLACE_EXPIRA_MS = 60_000;

/**
 * S-40 Exportación de Carpeta de Auditoría. La barra de progreso es una
 * animación (no hay empaquetado real de múltiples archivos sin backend/JSZip
 * — ver gap en seccion-m-reportes.md), pero el archivo final descargado
 * contiene datos reales de la auditoría y sus no conformidades asociadas.
 * El enlace de descarga expira a los 60s para reflejar "link temporal".
 */
export function AuditFolderExport({ audits, plants, nonConformities }: AuditFolderExportProps) {
  const formId = useId();
  const [auditId, setAuditId] = useState(audits[0]?.id ?? '');
  const [progreso, setProgreso] = useState<Progreso>('idle');
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [filename, setFilename] = useState('');
  const [error, setError] = useState('');
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    const activeTimers = timers.current;
    return () => {
      activeTimers.forEach(clearTimeout);
      if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleGenerar() {
    if (!auditId) {
      setError('Selecciona una auditoría.');
      return;
    }
    setError('');
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    setDownloadUrl(null);
    setProgreso('recopilando');

    timers.current.push(
      setTimeout(() => {
        setProgreso('generando');
        timers.current.push(
          setTimeout(() => {
            const audit = audits.find((a) => a.id === auditId)!;
            const plant = plants.find((p) => p.id === audit.plantId);
            const content = buildAuditFolderContent(audit, plant, nonConformities);
            const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const fecha = new Date().toISOString().slice(0, 10);
            setFilename(`carpeta-auditoria-${audit.plantId}-${fecha}.txt`);
            setDownloadUrl(url);
            setProgreso('listo');

            timers.current.push(
              setTimeout(() => {
                setDownloadUrl((current) => {
                  if (current) URL.revokeObjectURL(current);
                  return null;
                });
              }, ENLACE_EXPIRA_MS),
            );
          }, 700),
        );
      }, 700),
    );
  }

  return (
    <div className="flex flex-col gap-4 rounded-card border border-slate-200 bg-white p-5">
      <div>
        <h2 className="text-base font-semibold text-slate-900">Exportar carpeta de auditoría</h2>
        <p className="text-sm text-slate-500">Consolida los datos de la auditoría y sus no conformidades en un archivo descargable.</p>
      </div>

      <FormField label="Auditoría" htmlFor={`${formId}-audit`}>
        <select
          id={`${formId}-audit`}
          className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
          value={auditId}
          onChange={(e) => setAuditId(e.target.value)}
        >
          {audits.map((a) => {
            const plant = plants.find((p) => p.id === a.plantId);
            return (
              <option key={a.id} value={a.id}>
                {plant?.nombre ?? a.plantId} — {new Date(a.fecha).toLocaleDateString('es-CL')}
              </option>
            );
          })}
        </select>
      </FormField>

      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}

      {progreso !== 'idle' && (
        <div className="flex items-center gap-2 text-sm text-slate-600">
          {progreso === 'listo' ? (
            <CheckCircle2 className="h-4 w-4 text-brand-600" aria-hidden />
          ) : (
            <Spinner className="h-4 w-4" label={PASO_LABEL[progreso]} />
          )}
          <span aria-hidden={progreso !== 'listo'}>{PASO_LABEL[progreso]}</span>
        </div>
      )}

      {downloadUrl && (
        <div className="flex items-center justify-between rounded-lg bg-brand-50 px-4 py-3 text-sm">
          <span className="text-brand-800">Enlace de descarga disponible por 60 segundos.</span>
          <a
            href={downloadUrl}
            download={filename}
            className="font-medium text-brand-700 underline hover:text-brand-800"
          >
            Descargar {filename}
          </a>
        </div>
      )}

      <div className="flex justify-end">
        <Button
          icon={<FolderDown className="h-4 w-4" aria-hidden />}
          onClick={handleGenerar}
          isLoading={progreso === 'recopilando' || progreso === 'generando'}
        >
          Generar carpeta
        </Button>
      </div>
    </div>
  );
}
