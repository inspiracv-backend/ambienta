# Sección D — Matriz Legal (S-08 a S-12)

Fuente: "Prompts de Diseño — Ambienta v1.5" (Notion) + "Análisis Funcional v1.5" (Notion), ambos actualizados 2026-07-23.

## Elementos visuales identificados (Prompts de Diseño v1.5)

- **S-08 Listado de Matriz Legal**: filtros por planta, estado de cumplimiento y tipo de norma (pública BCN / ISO / RCA). Lista/tabla de normas con nombre, % de cumplimiento, cantidad de artículos en incumplimiento, responsable. Semáforo por norma (ícono+color+texto). Estado vacío elegante. Acción "agregar norma desde catálogo o cargar RCA/ISO".
- **S-09 Detalle de Norma + Evaluación por Artículo**: encabezado con % de cumplimiento y enlace externo a fuente oficial (LeyChile/SEIA). Tabla de artículos: Artículo, Descripción corta, Estado (SI/NO/NA), Forma de Cumplimiento, Responsable, Evidencias, Historial. Acciones por artículo: Evaluar, Adjuntar evidencia, Generar Plan de Acción, Ver historial.
- **S-10 Evaluar Artículo (modal)**: selector de estado (SI/NO/NA) con botones grandes, campo "Forma de Cumplimiento" (obligatorio si SI/NO), selector de responsable, zona de evidencias ("Enlazar desde Google Drive/OneDrive" + lista de archivos vinculados), botón "Generar Plan de Acción" visible cuando estado=NO, acceso al historial de cambios.
- **S-11 Configuración del % de Cumplimiento**: modal/pantalla con checkboxes de qué artículos/normas entran en el cálculo + vista previa del % resultante.
- **S-12 Gestión de RCAs e ISO del Tenant**: lista de RCAs/ISO cargadas (diferenciadas visualmente), botón "Subir RCA/ISO" (PDF), vista de artículos/considerandos marcados como aplicables, indicación pública/privada/pre-2015.

## Requisitos funcionales correspondientes (Notion v1.5)

- RF-08: Matriz Legal por tenant/planta con normas aplicables (regulatorias y voluntarias) y sus artículos.
- RF-09: actualización anual o ante cambio de marco normativo; también desde nuevas obligaciones (relación bidireccional con Sección E).
- RF-10: soporte diferenciado normas públicas (BCN) / ISO internas / RCA del tenant.
- RF-11: carga de PDF/HTML para RCA + extracción asistida por IA (opcional); RCAs públicas y privadas, pre y post 2015.
- RF-12: enlace externo a fuente oficial (LeyChile/SEIA) sin embeber el texto completo.
- RF-13: configuración de qué artículos/normas entran en el % de cumplimiento global.

## Gaps o inconsistencias detectadas

- RF-11 menciona "extracción asistida de artículos aplicables mediante IA" como opcional — no hay spec de OpenSpec aprobada para esa integración. **Se deja explícitamente fuera de esta iteración**: el botón "Subir RCA/ISO" solo agrega el registro con artículos vacíos/a completar manualmente; el comentario de integración real queda en el código.
- El historial de cambios (RF-21, "quién cambió, cuándo, por qué, quién aprobó") no tiene una pantalla propia en el Esquema de Pantallas — se resuelve como un panel/acordeón dentro de S-09/S-10, no como ruta separada.
- La relación bidireccional Matriz Legal ↔ Obligaciones (RF-09, RF-14) no se implementa en esta iteración porque Obligaciones (Sección E) tampoco está implementada — el botón "Generar obligación desde este artículo" se muestra deshabilitado con la misma convención "Próximamente" usada en Sección C, evitando romper H1.
- S-11 (Configuración del % de cumplimiento) ya se mencionó como deshabilitado en el Dashboard (Sección C) apuntando "disponible cuando esté Matriz Legal" — **resuelto en esta iteración**: el ícono del Dashboard ahora enlaza a `/matriz-legal`.
- `LegalMatrixTable` y la tabla de artículos de `NormDetailView` usan `overflow-x-auto` en vez del patrón tabla/tarjetas de `MultiPlantTable` (Sección C) — responsive funcional (no se corta contenido) pero no es la experiencia óptima en mobile. **A resolver cuando se generalice el organismo `DataTable`** (H4, ver nota en Componentes Atomic Design más abajo).

## Componentes Atomic Design necesarios

- Átomos: reutiliza `StatusBadge` (extendido a estados SI/NO/NA vía el mapeo ya existente cumple/no_cumple/na), `Button`, `Input`, `Icon`.
- Moléculas: reutiliza `FormField`; nueva `FilterBar` (selects de planta/estado/tipo, persistentes — H6), `ArticleRow` (fila de artículo con estado+acciones).
- Organismos: `LegalMatrixTable` (lista de normas — primer caso real del `DataTable` genérico anticipado en Sección C), `ArticleEvaluationModal` (S-10, sobre Radix Dialog), `ComplianceConfigModal` (S-11), `NormDetailHeader` (S-09), `TenantNormsManager` (S-12).
- Templates: ninguno nuevo — reutiliza `DashboardLayout`.

## Datos de ejemplo necesarios (mock data)

- Ya cubierto por `mocks/catalog.ts` (Paso 3 original): normas BCN + RCA del tenant, con artículos en estados SI/NO/N_E.
- Se amplía `mocks/catalog.ts` con más artículos por norma y con normas ISO para representar las 3 capas (RF-42) — necesario para S-08/S-25 (Catálogo, aunque S-25 es Sección H, no se implementa aún).
- Casos límite: norma con 100% cumplimiento, norma con artículo N/E (pendiente evaluar) sin representación de semáforo tradicional, RCA privada pre-2015.

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — semáforo por norma y por artículo, loading/empty states en el listado.
- [x] H2 Correspondencia con el mundo real — "RCA", "ISO", "BCN", "N/A", "N/E" tal como los usa el funcional, no traducidos.
- [x] H3 Control y libertad — modal de evaluación con cancelar sin perder cambios de otros artículos.
- [x] H4 Consistencia — `LegalMatrixTable` es la primera instancia real del patrón `DataTable` (mismo criterio de ordenamiento/filtros que se reutilizará en Catálogo/Usuarios).
- [x] H5 Prevención de errores — "Forma de Cumplimiento" obligatoria si el estado es SI/NO, validado antes de guardar.
- [x] H6 Reconocer antes que recordar — filtros persistentes y visibles, no escondidos en menú.
- [x] H9 Recuperación de errores — mensaje humano si falla el guardado de una evaluación (simulado).
- [x] H10 Ayuda y documentación — tooltip sobre "RCA"/"BCN"/"ISO" en su primer uso; estado vacío con guía de próximo paso.
