'use client';

import type { Tenant } from '@ambienta/shared';
import { ReportePdf } from '@/components/organisms/ReportePdf';
import {
  CLASIFICACION_LABEL,
  porcentaje,
  type InformeDeAuditoria,
} from '@/lib/informe-auditoria';

/**
 * El informe de auditoría como documento entregable (RF-101, F5).
 *
 * **Pinta lo mismo que el panel, no un resumen propio.** Toma el `informe` que
 * devuelve la API: si el documento armara sus propias cifras, lo que se entrega
 * a un certificador y lo que muestra el sistema podrían decir cosas distintas
 * sobre la misma auditoría, y nadie compara los dos hasta que alguien de afuera
 * lo hace.
 *
 * Se imprime con el motor del navegador (`window.print()`), igual que los
 * reportes: texto seleccionable y el papel de quien lo emite, sin sumar una
 * librería. Ver `ReportePdf`.
 *
 * Los ceros que no son ceros se respetan: `Sin evaluar` cuando no se evaluó
 * nada, y la tasa de cierre dice **por qué** no aplica en vez de un 0 % que se
 * lee como una acusación.
 */
export function InformeDeAuditoriaPdf({
  tenant,
  informe,
  emitidoPor,
}: {
  tenant: Tenant;
  informe: InformeDeAuditoria;
  emitidoPor: string;
}) {
  const r = informe.resumen;
  const cifras: { label: string; valor: string }[] = [
    { label: 'Conformidad', valor: porcentaje(r.conformidad) },
    { label: 'Procesos auditados', valor: String(r.procesos_auditados) },
    { label: 'No conformidades', valor: String(r.no_conformidades) },
    { label: 'Observaciones', valor: String(r.observaciones) },
    { label: 'Oportunidades de mejora', valor: String(r.oportunidades_de_mejora) },
  ];

  return (
    <ReportePdf
      tenant={tenant}
      titulo={`Informe de auditoría — ${informe.titulo}`}
      subtitulo={informe.codigo}
      emitidoPor={emitidoPor}
    >
      <section>
        <h2 className="text-sm font-semibold text-slate-800">Resumen ejecutivo</h2>
        <dl className="mt-2 grid grid-cols-5 gap-3 text-xs">
          {cifras.map((c) => (
            <div key={c.label} className="evitar-corte border border-slate-200 p-2">
              <dt className="text-slate-500">{c.label}</dt>
              <dd className="mt-1 text-base font-semibold tabular-nums text-slate-900">{c.valor}</dd>
            </div>
          ))}
        </dl>
        {r.items_sin_proceso > 0 && (
          <p className="mt-2 text-xs text-slate-600">
            {r.items_sin_proceso} pregunta(s) son requisitos generales del sistema de gestión y no
            cuentan en ningún proceso.
          </p>
        )}
        <p className="mt-3 text-xs text-slate-700">
          <span className="font-semibold">Tasa de cierre del ciclo anterior: </span>
          {informe.tasa_de_cierre_del_ciclo_anterior !== null
            ? porcentaje(informe.tasa_de_cierre_del_ciclo_anterior)
            : `No aplica — ${informe.motivo_sin_tasa ?? 'sin ciclo anterior comparable'}`}
        </p>
      </section>

      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-800">Resultados por proceso</h2>
        {informe.matriz.length === 0 ? (
          <p className="mt-2 text-xs text-slate-600">
            Ninguna pregunta de esta auditoría está asociada a un proceso.
          </p>
        ) : (
          <table className="mt-2 w-full text-xs">
            <thead>
              <tr className="border-b border-slate-300 text-left">
                <th scope="col" className="py-2 pr-3 font-semibold text-slate-700">Proceso</th>
                <th scope="col" className="py-2 pr-3 font-semibold text-slate-700">Cláusulas</th>
                <th scope="col" className="py-2 pr-3 font-semibold text-slate-700">Revisado</th>
                <th scope="col" className="py-2 pr-3 font-semibold text-slate-700">Resultado</th>
                <th scope="col" className="py-2 font-semibold text-slate-700">Conclusión y evidencia</th>
              </tr>
            </thead>
            <tbody>
              {informe.matriz.map((fila) => (
                <tr key={fila.proceso_id} className="border-b border-slate-100 align-top">
                  <td className="py-2 pr-3 font-medium text-slate-800">{fila.proceso_nombre}</td>
                  <td className="py-2 pr-3 text-slate-600">
                    {fila.clausulas_auditadas.join(', ') || '—'}
                  </td>
                  <td className="py-2 pr-3 tabular-nums text-slate-600">
                    {fila.items} ({fila.items_conformes} conformes, {fila.items_no_conformes} no conformes)
                  </td>
                  <td className="py-2 pr-3 text-slate-700">
                    {CLASIFICACION_LABEL[fila.clasificacion] ?? fila.clasificacion}
                  </td>
                  <td className="py-2 text-slate-600">
                    {fila.conclusion ?? 'Sin conclusión registrada.'}
                    {fila.evidencia_revisada && (
                      <span className="block text-slate-500">
                        Evidencia: {fila.evidencia_revisada}
                      </span>
                    )}
                    {fila.hallazgos.length > 0 && (
                      <span className="block text-slate-500">
                        Hallazgos: {fila.hallazgos.join(' · ')}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </ReportePdf>
  );
}
