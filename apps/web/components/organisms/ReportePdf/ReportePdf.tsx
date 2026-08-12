'use client';

import { Building2 } from 'lucide-react';
import type { Tenant } from '@ambienta/shared';
import { nombreDePais } from '@ambienta/shared';
import type { ReactNode } from 'react';

/**
 * Documento imprimible con encabezado corporativo.
 *
 * **Por qué no se agregó una librería de PDF.** Generar el PDF en el cliente
 * (`@react-pdf/renderer`, `pdfmake`) obliga a mantener un segundo sistema de
 * maquetación en paralelo al de la aplicación, y ninguna está aprobada por un
 * ADR. La impresión nativa del navegador produce un PDF con selección de
 * texto, hipervínculos y el tamaño de papel del usuario, reutilizando el
 * mismo HTML — a cambio de no controlar los saltos de página al detalle.
 * Para un informe de auditoría es un intercambio razonable; si más adelante
 * se necesita control tipográfico fino, esta pantalla es el punto donde
 * enchufar la librería.
 *
 * El encabezado lleva el **logo del auditado** (el del tenant, no el de
 * Ambienta): un informe sin la marca de la empresa no parece un documento
 * suyo ante un fiscalizador.
 */
export function ReportePdf({
  tenant,
  titulo,
  subtitulo,
  emitidoPor,
  children,
}: {
  tenant: Tenant;
  titulo: string;
  subtitulo?: string;
  emitidoPor: string;
  children: ReactNode;
}) {
  const ahora = new Date();

  return (
    <article className="reporte-imprimible rounded-card border border-slate-200 bg-white p-8">
      {/* ── Encabezado ─────────────────────────────────────────────────── */}
      <header className="flex items-start justify-between gap-6 border-b-2 border-slate-800 pb-4">
        <div className="flex items-start gap-3">
          {tenant.logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={tenant.logoUrl} alt={tenant.nombre} className="h-14 w-14 object-contain" />
          ) : (
            <span className="flex h-14 w-14 items-center justify-center rounded border border-dashed border-slate-300 text-slate-300">
              <Building2 className="h-6 w-6" aria-hidden />
            </span>
          )}
          <div>
            <p className="text-base font-bold text-slate-900">{tenant.nombre}</p>
            <p className="text-xs text-slate-600">
              {tenant.identificacion.tipo} {tenant.identificacion.numero} · {nombreDePais(tenant.pais)}
            </p>
            {tenant.direccion && <p className="text-xs text-slate-500">{tenant.direccion}</p>}
          </div>
        </div>

        <div className="text-right text-xs text-slate-500">
          <p className="font-semibold uppercase tracking-wide text-slate-700">{titulo}</p>
          {subtitulo && <p>{subtitulo}</p>}
          <p className="mt-1">
            Emitido: <time dateTime={ahora.toISOString()}>{ahora.toLocaleDateString('es-CL')}</time>
          </p>
          <p>Por: {emitidoPor}</p>
        </div>
      </header>

      <div className="mt-6">{children}</div>

      {/* ── Pie ────────────────────────────────────────────────────────── */}
      <footer className="mt-8 border-t border-slate-200 pt-3 text-[10px] leading-relaxed text-slate-400">
        <p>
          Documento generado por Ambienta el {ahora.toLocaleString('es-CL')}. La información refleja el estado del
          sistema en ese momento.
        </p>
        {!tenant.logoUrl && (
          // Nota que solo se ve mientras falte el logo: es un recordatorio
          // accionable, no un error.
          <p className="mt-1 font-medium text-slate-500 print:hidden">
            Sugerencia: carga el logo de la empresa en Perfil Empresa para que aparezca en el encabezado.
          </p>
        )}
      </footer>
    </article>
  );
}
