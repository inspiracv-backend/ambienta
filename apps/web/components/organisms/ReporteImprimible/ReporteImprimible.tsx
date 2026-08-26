'use client';

import type { Tenant, User } from '@ambienta/shared';
import type { Reporte } from '@/lib/reports';
import { ReportePdf } from '@/components/organisms/ReportePdf';

/**
 * Cualquier reporte, pintado como documento entregable.
 *
 * **Toma el mismo `Reporte` del que sale el CSV.** No arma sus propias filas ni
 * decide sus propias columnas: si lo hiciera, agregar una columna a la planilla
 * dejaria el documento entregado a un auditor diciendo otra cosa sobre la misma
 * empresa — y nadie compara los dos archivos hasta que alguien de afuera lo
 * hace.
 *
 * Se imprime con el motor del navegador (`window.print()`) y no con una
 * libreria. Ver `ReportePdf` para el razonamiento completo; en resumen: el PDF
 * sale con texto seleccionable, enlaces vivos y el tamano de papel de quien lo
 * emite, reutilizando el HTML de la aplicacion. Lo que se cede es el control
 * fino de los saltos de pagina.
 */
export function ReporteImprimible({
  tenant,
  usuario,
  reporte,
  subtitulo,
}: {
  tenant: Tenant;
  usuario: User;
  reporte: Reporte;
  subtitulo?: string;
}) {
  return (
    <ReportePdf
      tenant={tenant}
      titulo={reporte.titulo}
      subtitulo={subtitulo}
      emitidoPor={usuario.nombre}
    >
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-slate-300 text-left">
            {reporte.headers.map((h) => (
              <th key={h} scope="col" className="py-2 pr-3 font-semibold text-slate-700">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {reporte.rows.map((fila, i) => (
            // El indice como clave: las filas de un reporte no se reordenan ni
            // se editan — se pintan una vez y se imprimen.
            <tr key={i} className="border-b border-slate-100 align-top">
              {fila.map((celda, j) => (
                <td
                  key={j}
                  className={
                    // Los numeros y porcentajes con cifras alineadas; "Sin
                    // evaluar" es texto y va como texto.
                    /^\d|%$/.test(celda) ? 'py-1.5 pr-3 tabular-nums' : 'py-1.5 pr-3'
                  }
                >
                  {celda}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {reporte.notas.length > 0 && (
        <div className="mt-4 border-t border-slate-200 pt-3">
          {reporte.notas.map((nota) => (
            <p key={nota} className="text-[10px] leading-relaxed text-slate-500">
              {nota}
            </p>
          ))}
        </div>
      )}
    </ReportePdf>
  );
}
