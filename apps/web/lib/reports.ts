import type { Audit, LegalNorm, NonConformity, Obligation, Plant } from '@ambienta/shared';
import { computeNormCompliance, countArticulosEnIncumplimiento } from '@/lib/legal-matrix';
import { AUDIT_ESTADO_LABEL, NC_ESTADO_LABEL, CRITICIDAD_LABEL } from '@/lib/audit-status';

export type TipoReporte = 'cumplimiento' | 'no-conformidades' | 'matriz-legal';

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
): { csv: string; empty: boolean } {
  const obligacionesEnRango = obligations.filter((o) => inRange(o.proximoVencimiento, desde, hasta));
  const rows = plants.map((plant) => {
    const plantObligations = obligacionesEnRango.filter((o) => o.plantId === plant.id);
    const vigentes = plantObligations.filter((o) => o.estado === 'vigente').length;
    const pctObligaciones = plantObligations.length > 0 ? vigentes / plantObligations.length : 0;

    const plantNorms = norms.filter((n) => n.plantIds.includes(plant.id));
    const pctNormas =
      plantNorms.length > 0 ? plantNorms.reduce((sum, n) => sum + computeNormCompliance(n), 0) / plantNorms.length : 0;

    return [
      plant.nombre,
      `${Math.round(pctNormas * 100)}%`,
      `${Math.round(pctObligaciones * 100)}%`,
      String(plantObligations.length),
      String(plantObligations.filter((o) => o.estado === 'vencida' || o.estado === 'sin_evidencia').length),
    ];
  });

  return {
    csv: toCsv(
      ['Planta', '% Cumplimiento Matriz Legal', '% Obligaciones vigentes', 'Obligaciones en rango', 'Incumplimientos'],
      rows,
    ),
    empty: obligacionesEnRango.length === 0 && norms.every((n) => n.articulos.length === 0),
  };
}

/** RF-50: reporte de No Conformidades, filtrado por fecha de detección. */
export function buildNoConformidadesReport(
  plants: Plant[],
  nonConformities: NonConformity[],
  desde: string,
  hasta: string,
): { csv: string; empty: boolean } {
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

  return {
    csv: toCsv(['Planta', 'Hallazgo', 'Criticidad', 'Estado', 'Fecha detección', 'Fecha cierre'], rows),
    empty: filtered.length === 0,
  };
}

/**
 * RF-50: reporte de Matriz Legal. Sin rango de fechas — la Matriz Legal es
 * estructural/anual (RF-09), no tiene una fecha propia por la que filtrar.
 */
export function buildMatrizLegalReport(norms: LegalNorm[], plants: Plant[]): { csv: string; empty: boolean } {
  const rows = norms.map((norm) => [
    norm.nombre,
    norm.fuente,
    norm.plantIds.map((id) => plants.find((p) => p.id === id)?.nombre ?? id).join(' / ') || 'Sin asignar',
    `${Math.round(computeNormCompliance(norm) * 100)}%`,
    String(countArticulosEnIncumplimiento(norm)),
  ]);

  return {
    csv: toCsv(['Norma', 'Fuente', 'Plantas', '% Cumplimiento', 'Artículos en incumplimiento'], rows),
    empty: norms.length === 0,
  };
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
export function downloadTextFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
