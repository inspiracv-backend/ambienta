import type { Audit, LegalNorm, NonConformity, Obligation, Plant } from '@ambienta/shared';
import {
  computeNormComplianceOrNull,
  countArticulosEnIncumplimiento,
  countArticulosSinEvaluar,
} from '@/lib/legal-matrix';
import { AUDIT_ESTADO_LABEL, NC_ESTADO_LABEL, CRITICIDAD_LABEL } from '@/lib/audit-status';

export type TipoReporte = 'cumplimiento' | 'no-conformidades' | 'matriz-legal';

/** En que formato sale el reporte. **PDF por defecto** (ver `FORMATO_POR_DEFECTO`). */
export type FormatoReporte = 'pdf' | 'csv';

/**
 * El formato con el que se abre la pantalla.
 *
 * **PDF, y no CSV.** Quien pide un reporte de cumplimiento casi siempre lo pide
 * para *entregarlo* — a un fiscalizador, a un certificador, a un cliente. Eso
 * es un documento con la identificacion de la empresa, la fecha y quien lo
 * emitio. Una planilla es para procesar los datos, que es el caso menos
 * frecuente y el que sabe pedirlo quien lo necesita.
 *
 * El CSV **no se quita**: sigue a un clic, en el mismo selector.
 */
export const FORMATO_POR_DEFECTO: FormatoReporte = 'pdf';

/**
 * Un reporte, en la forma que sirve para los dos formatos.
 *
 * `headers` y `rows` son la fuente unica; el `csv` se deriva de ellos y el PDF
 * los pinta. **Construirlos por separado seria tener dos reportes con el mismo
 * nombre**, y el dia que alguien agregue una columna a uno solo, la planilla y
 * el documento entregado a un auditor dirian cosas distintas sobre la misma
 * empresa. Ya paso en este repo con el porcentaje de cumplimiento.
 */
export interface Reporte {
  titulo: string;
  headers: string[];
  rows: string[][];
  csv: string;
  empty: boolean;
  /** Aclaraciones que van al pie del documento. Vacio no imprime nada. */
  notas: string[];
}

/**
 * Como se escribe un porcentaje que puede no existir.
 *
 * **"Sin evaluar" y no "0%".** Un cero se lee como incumplimiento total, y en
 * un documento que se le entrega a un fiscalizador esa diferencia es la que hay
 * entre "no cumplimos" y "todavia no lo revisamos". Es el mismo arreglo que ya
 * tiene la pantalla de la matriz legal (#205).
 */
function porcentaje(valor: number | null): string {
  return valor === null ? 'Sin evaluar' : `${Math.round(valor * 100)}%`;
}

function armar(
  titulo: string,
  headers: string[],
  rows: string[][],
  empty: boolean,
  notas: string[] = [],
): Reporte {
  return { titulo, headers, rows, csv: toCsv(headers, rows), empty, notas };
}

function csvEscape(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function toCsv(headers: string[], rows: string[][]): string {
  return [headers, ...rows].map((row) => row.map(csvEscape).join(',')).join('\n');
}

function formatFecha(iso: string): string {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

function inRange(iso: string, desde: string, hasta: string): boolean {
  if (!desde && !hasta) return true;
  const t = new Date(iso).getTime();
  if (desde && t < new Date(desde).getTime()) return false;
  if (hasta && t > new Date(hasta).getTime() + 86_400_000 - 1) return false;
  return true;
}

/**
 * RF-50: reporte de Cumplimiento. Reutiliza la misma regla de "% de
 * cumplimiento" que Sección D (`computeNormCompliance`) y el mismo criterio
 * de incumplimiento que `dashboard-metrics.ts`, para no duplicar lógica de
 * negocio en cada exportación.
 */
export function buildCumplimientoReport(
  plants: Plant[],
  obligations: Obligation[],
  norms: LegalNorm[],
  desde: string,
  hasta: string,
): Reporte {
  const obligacionesEnRango = obligations.filter((o) => inRange(o.proximoVencimiento, desde, hasta));
  let hayNormasSinEvaluar = false;

  const rows = plants.map((plant) => {
    const plantObligations = obligacionesEnRango.filter((o) => o.plantId === plant.id);
    const vigentes = plantObligations.filter((o) => o.estado === 'vigente').length;
    const pctObligaciones = plantObligations.length > 0 ? vigentes / plantObligations.length : 0;

    // **Solo promedia las normas que tienen algo que medir.** Antes sumaba
    // `computeNormCompliance`, que devuelve 0 cuando nadie evaluo nada: una
    // planta con cuatro normas y una sola evaluada al 100 % salia en 25 %, como
    // si incumpliera tres. En el documento que se entrega, eso es una confesion
    // falsa.
    const plantNorms = norms.filter((n) => n.plantIds.includes(plant.id));
    const medibles = plantNorms
      .map(computeNormComplianceOrNull)
      .filter((p): p is number => p !== null);
    if (medibles.length < plantNorms.length) hayNormasSinEvaluar = true;
    const pctNormas =
      medibles.length > 0 ? medibles.reduce((s, p) => s + p, 0) / medibles.length : null;

    return [
      plant.nombre,
      porcentaje(pctNormas),
      `${Math.round(pctObligaciones * 100)}%`,
      String(plantObligations.length),
      String(plantObligations.filter((o) => o.estado === 'vencida' || o.estado === 'sin_evidencia').length),
    ];
  });

  return armar(
    'Reporte de Cumplimiento',
    ['Planta', '% Cumplimiento Matriz Legal', '% Obligaciones vigentes', 'Obligaciones en rango', 'Incumplimientos'],
    rows,
    obligacionesEnRango.length === 0 && norms.every((n) => n.articulos.length === 0),
    hayNormasSinEvaluar
      ? [
          'El % de cumplimiento promedia solo las normas con articulos evaluados. ' +
            'Las normas sin evaluar no cuentan como incumplidas: todavia no se han revisado.',
        ]
      : [],
  );
}

/** RF-50: reporte de No Conformidades, filtrado por fecha de detección. */
export function buildNoConformidadesReport(
  plants: Plant[],
  nonConformities: NonConformity[],
  desde: string,
  hasta: string,
): Reporte {
  const filtered = nonConformities.filter((nc) => inRange(nc.fechaDeteccion, desde, hasta));
  const rows = filtered.map((nc) => {
    const plant = plants.find((p) => p.id === nc.plantId);
    return [
      plant?.nombre ?? nc.plantId,
      nc.hallazgo,
      CRITICIDAD_LABEL[nc.criticidad],
      NC_ESTADO_LABEL[nc.estado],
      formatFecha(nc.fechaDeteccion),
      nc.cierre ? formatFecha(nc.cierre.fecha) : 'Sin cierre',
    ];
  });

  return armar(
    'Reporte de No Conformidades',
    ['Planta', 'Hallazgo', 'Criticidad', 'Estado', 'Fecha detección', 'Fecha cierre'],
    rows,
    filtered.length === 0,
  );
}

/**
 * RF-50: reporte de Matriz Legal. Sin rango de fechas — la Matriz Legal es
 * estructural/anual (RF-09), no tiene una fecha propia por la que filtrar.
 */
export function buildMatrizLegalReport(norms: LegalNorm[], plants: Plant[]): Reporte {
  const rows = norms.map((norm) => [
    norm.nombre,
    norm.fuente,
    norm.plantIds.map((id) => plants.find((p) => p.id === id)?.nombre ?? id).join(' / ') || 'Sin asignar',
    // **Aca estaba el "0 %" del ticket #205.** Con el articulado real de la BCN,
    // una norma recien importada llega entera sin evaluar y el informe la
    // declaraba incumplida ante quien lo lee.
    porcentaje(computeNormComplianceOrNull(norm)),
    String(countArticulosEnIncumplimiento(norm)),
    String(countArticulosSinEvaluar(norm)),
  ]);

  return armar(
    'Reporte de Matriz Legal',
    ['Norma', 'Fuente', 'Plantas', '% Cumplimiento', 'Artículos en incumplimiento', 'Artículos sin evaluar'],
    rows,
    norms.length === 0,
    // La columna nueva no es decoracion: sin ella, "Sin evaluar" no dice cuanto
    // falta, y un 100 % sobre un articulo de doscientos se lee igual que un
    // 100 % sobre los doscientos.
    ['El % de cumplimiento se calcula sobre los articulos ya evaluados. La ultima columna dice cuantos faltan.'],
  );
}

/**
 * RF-50/S-40: contenido consolidado de la "carpeta de auditoría". Se genera
 * como texto plano real (no un mock) — el único punto simulado es la barra
 * de progreso en `AuditFolderExport` (ver gap en seccion-m-reportes.md).
 */
export function buildAuditFolderContent(audit: Audit, plant: Plant | undefined, nonConformities: NonConformity[]): string {
  const relatedNcs = nonConformities.filter((nc) => nc.auditId === audit.id);
  const lines = [
    `CARPETA DE AUDITORÍA — ${plant?.nombre ?? audit.plantId}`,
    `Tipo: ${audit.tipo === 'interna' ? 'Interna' : 'Externa'}`,
    `Fecha: ${formatFecha(audit.fecha)}`,
    `Estado: ${AUDIT_ESTADO_LABEL[audit.estado]}`,
    `Procesos auditados: ${audit.procesos.join(', ') || 'Sin especificar'}`,
    `Normativa asociada: ${audit.normativaIds.join(', ') || 'Sin normativa asociada'}`,
    '',
    `NO CONFORMIDADES ASOCIADAS (${relatedNcs.length})`,
    '-'.repeat(40),
  ];

  if (relatedNcs.length === 0) {
    lines.push('Sin no conformidades registradas para esta auditoría.');
  } else {
    for (const nc of relatedNcs) {
      lines.push(
        `- [${CRITICIDAD_LABEL[nc.criticidad]}] ${nc.hallazgo}`,
        `  Estado: ${NC_ESTADO_LABEL[nc.estado]} — Detectada: ${formatFecha(nc.fechaDeteccion)}`,
        nc.cierre ? `  Cierre: ${formatFecha(nc.cierre.fecha)} (firmada)` : '  Sin cierre',
        '',
      );
    }
  }

  return lines.join('\n');
}

/** Descarga real vía Blob — no hay backend que aloje el archivo en esta iteración. */
/**
 * El marcador de orden de bytes que Excel necesita para leer UTF-8.
 *
 * **Sin esto, Excel en Windows asume la codificación local (ANSI)** y los
 * acentos salen rotos: "Emisión" se ve como "EmisiÃ³n", "Fecha detección" como
 * "Fecha detecciÃ³n". Los encabezados de estos reportes llevan acentos y los
 * títulos de las normas de la BCN vienen en mayúsculas con tilde, así que el
 * archivo entero se ve mal.
 *
 * El `charset=utf-8` del tipo MIME no alcanza: Excel no lo mira, mira los
 * primeros bytes del archivo.
 */
const BOM_UTF8 = '\uFEFF';

export function downloadTextFile(filename: string, content: string, mime: string) {
  // El BOM solo va en los archivos que Excel va a abrir. Metérselo a un `.txt`
  // o a un JSON lo ensuciaría: quien lo lea con otra herramienta vería tres
  // bytes basura al principio.
  const esCsv = filename.toLowerCase().endsWith('.csv');
  const blob = new Blob([esCsv ? BOM_UTF8 + content : content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
