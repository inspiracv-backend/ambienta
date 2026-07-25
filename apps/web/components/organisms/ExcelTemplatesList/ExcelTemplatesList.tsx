import { Download, FileSpreadsheet } from 'lucide-react';
import type { ExcelTemplatesListProps } from './ExcelTemplatesList.types';

/**
 * S-33 Super-repositorio de Templates Excel (RF-22/RF-23). Se adjuntan
 * automáticamente en los recordatorios de email (RF-24) — sin envío real de
 * correo en esta iteración (depende de Resend/Brevo, fuera de alcance).
 */
export function ExcelTemplatesList({ templates }: ExcelTemplatesListProps) {
  return (
    <div className="flex flex-col gap-4">
      <p className="rounded-lg bg-brand-50 px-4 py-3 text-sm text-brand-700">
        Estos templates se adjuntan automáticamente en los recordatorios por email de cada declaración.
      </p>
      <ul className="flex flex-col gap-2">
        {templates.map((t) => (
          <li key={t.id} className="flex items-center justify-between gap-3 rounded-card border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-3">
              <FileSpreadsheet className="h-6 w-6 shrink-0 text-brand-600" aria-hidden />
              <div>
                <p className="text-sm font-medium text-slate-800">{t.nombre}</p>
                <p className="text-xs text-slate-500">
                  {t.sistema} · v{t.version} · {t.pestanas.join(' + ')}
                </p>
              </div>
            </div>
            <a
              href={t.archivoUrl}
              onClick={(e) => e.preventDefault()}
              title="Archivo de ejemplo (mock, sin descarga real en esta iteración)"
              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <Download className="h-4 w-4" aria-hidden />
              Descargar
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
