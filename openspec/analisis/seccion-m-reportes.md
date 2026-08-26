# Sección M — Reportes y Exportación (S-39, S-40)

Fuente: "Prompts de Diseño — Ambienta v1.5" (Notion) + "Análisis Funcional v1.5" (Notion), ambos actualizados 2026-07-23.

## Elementos visuales identificados (Prompts de Diseño v1.5)

- **S-39 Reportes** (Actor: Admin Empresa): selector de tipo de reporte (Cumplimiento, No Conformidades, Matriz Legal, etc.), rango de fechas y botón de exportar (PDF / Excel).
- **S-40 Exportación de Carpeta de Auditoría** (Actor: Admin Empresa): flujo de generación de carpeta de auditoría con estado de progreso y link de descarga temporal.

## Requisitos funcionales correspondientes (Notion v1.5)

- RF-47: Dashboard consolidado (ya cubierto en Sección C) — los reportes reutilizan las mismas métricas.
- RF-49: Vista de artículos/tareas en incumplimiento con acceso directo a evidencias, historial y planes de acción (el reporte de Cumplimiento resume esto).
- **RF-50**: Generación de reportes y exportación de información (PDF / Excel).
- RF-51: Botón de configuración del % de cumplimiento (ya implementado en S-11, Sección D) — el reporte de Matriz Legal usa el mismo cálculo (`computeNormCompliance`).
- RNF-26: Datos y logs exportables fácilmente para auditorías externas.

## Gaps o inconsistencias detectadas

- ~~**Generación real de PDF** requiere una librería no instalada y sin ADR que la apruebe.~~ **Resuelto el 26-ago-2026 (#128), y sin agregar la dependencia.** El PDF sale del **motor de impresión del navegador** sobre el mismo HTML de la aplicación (`ReportePdf`): texto seleccionable, enlaces vivos, el papel de quien lo emite y el encabezado de la empresa auditada. Lo que se cede es el control fino de los saltos de página — para un informe tabular es un intercambio razonable, y `ReportePdf` queda como el único punto donde enchufar una librería el día que haga falta control tipográfico.
- **El formato por defecto es PDF, no CSV.** Un reporte de cumplimiento casi siempre se pide para *entregarlo* a un fiscalizador o un certificador; una planilla no se entrega, se procesa. El CSV sigue disponible en el mismo selector.
- **Los dos formatos salen del mismo `Reporte`** (`lib/reports.ts`): `headers` y `rows` se calculan una vez, el CSV se deriva y el PDF los pinta. Construirlos por separado serían dos reportes con el mismo nombre.
- **S-40 "estado de progreso"**: no existe hoy un proceso asíncrono real de empaquetado de carpetas (requeriría backend o una librería de zip cliente como JSZip, no instalada). Se simula visualmente el progreso (pasos: "Recopilando evidencias" → "Generando documento" → "Listo") mientras se arma, en paralelo, un archivo de texto **real** con el contenido consolidado de la auditoría (datos + no conformidades relacionadas) que sí se descarga de verdad al finalizar. Se documenta explícitamente como simplificación: el "progreso" es una animación, pero el archivo final no es un mock — contiene datos reales tomados de `AuditsProvider`.
- El "link de descarga temporal" de S-40 se resuelve como una descarga directa vía `Blob`/`URL.createObjectURL` (no hay backend que aloje un archivo con expiración) — se documenta como simplificación aceptada, coherente con el resto de la plataforma (sin backend real en esta iteración).
- El reporte de "No Conformidades" depende de datos de la Sección G (`NonConformity`), ya implementada — sin gap pendiente.
- El reporte de "Matriz Legal" depende de la Sección D (`LegalNorm`/`Articulo`), ya implementada — sin gap pendiente.
- No se modela una entidad `Report`/historial de reportes generados — el Esquema de Pantallas v1.5 no pide un historial persistente, solo generar y exportar en el momento (RF-50). Si en el futuro se pide un historial de reportes generados, se deja como extensión futura.

## Componentes Atomic Design necesarios

- Átomos: reutiliza `Button`, `StatusBadge`.
- Moléculas: reutiliza `FormField`, `FilterBar`.
- Organismos:
  - `ReportGenerator` (S-39): selector de tipo de reporte + rango de fechas + botón "Generar y exportar" → calcula datos reales desde los stores existentes (`useObligations`, `useLegalMatrix`, `useAudits`) y descarga un archivo `.csv`/`.txt` real.
  - `AuditFolderExport` (S-40): selector de auditoría + botón "Generar carpeta" → barra de progreso simulada (pasos) + descarga real de un `.txt` consolidado (datos de la auditoría + no conformidades asociadas).
- Templates: ninguno nuevo.

## Datos de ejemplo necesarios (mock data)

- No se requieren mocks nuevos: los reportes se calculan en el momento a partir de `mockObligations`, `mockLegalNorms` y `mockAudits`/`mockNonConformities` ya existentes (mismo patrón de "no duplicar datos" usado en `lib/dashboard-metrics.ts`).

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — barra/pasos de progreso visibles durante la generación de la carpeta de auditoría (S-40); confirmación visible tras exportar (S-39).
- [x] H4 Consistencia — mismos `FormField`/`FilterBar`/`Button` que el resto de la plataforma.
- [x] H5 Prevención de errores — no se permite exportar sin seleccionar tipo de reporte/auditoría; rango de fechas valida que "hasta" no sea anterior a "desde".
- [x] H6 Reconocer antes que recordar — nombres de archivo descriptivos generados automáticamente (ej. `reporte-cumplimiento-2026-07-25.csv`).
- [x] H8 Diseño minimalista — un solo formulario por pantalla, sin campos que no correspondan al tipo de reporte elegido.
- [x] H9 Recuperación de errores — mensaje claro si el rango de fechas no tiene datos ("No hay registros en el rango seleccionado").
- [x] H10 Ayuda y documentación — cada formato dice para qué sirve en el propio selector («documento para entregar» / «planilla para procesar»). **La nota anterior decía que el PDF quedaba pendiente de una librería y se volvió falsa** sin que nadie la revisara: el documento imprimible ya existía. Una advertencia que envejece mal desalienta usar lo que sí funciona.
