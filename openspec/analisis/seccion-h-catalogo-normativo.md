# Sección H — Catálogo Normativo (S-25, S-26)

Fuente: "Prompts de Diseño — Ambienta v1.5" (Notion) + "Análisis Funcional v1.5" (Notion), ambos actualizados 2026-07-23.

## Elementos visuales identificados (Prompts de Diseño v1.5)

- **S-25 Catálogo Normativo (3 capas)**: diferenciación clara entre normas públicas (BCN), ISO internas y RCA del tenant (públicas y privadas). Barra de búsqueda + filtros por tipo y estado de sincronización. Tabla con badges de estado del embedding/sincronización. Vista Superadmin: panel de salud del agente BCN + botón "Forzar sincronización". Vista Admin Empresa: botón "Marcar como aplicable a mi planta".
- **S-26 Definir Normas Aplicables por Planta**: selector de planta. Panel izquierdo: buscador del catálogo con selección múltiple. Panel derecho: normas ya asignadas a la planta (quitar). Contador y botón "Guardar asignación". Dos columnas en desktop, apilado en mobile.

## Requisitos funcionales correspondientes (Notion v1.5)

- RF-42: catálogo con tres capas (BCN, ISO, RCA).
- RF-43: diferenciación clara entre obligaciones regulatorias y compromisos voluntarios.
- RF-44: agregar/actualizar normativas del tenant (RCA/ISO).
- RF-45: agente conectado al servicio web de LeyChile (BCN) para mantener el catálogo público actualizado y generar embeddings (RAG).
- RF-46: RCAs como documentos del tenant; ISO se alimenta igual aunque sea de origen privado/comercial.

## Gaps o inconsistencias detectadas

- RF-45 (agente BCN + embeddings/RAG) depende de `apps/ai-service`, que hoy es solo un esqueleto TypeScript (ver `docs/arquitectura/auditoria-stack-frontend.md`) — sin spec de API aprobada. El "panel de salud del agente BCN" y el botón "Forzar sincronización" de S-25 se implementan **visualmente deshabilitados** con la convención estándar "Próximamente", mostrando el estado de sincronización ya existente en el dato (mock) pero sin poder disparar una sincronización real.
- Esta sección **no introduce un modelo de datos nuevo**: reutiliza `LegalNorm` de la Sección D (Matriz Legal), que ya tiene `fuente: 'BCN' | 'ISO' | 'RCA'` y `plantIds`. Se agrega únicamente un campo opcional `sincronizacion` (estado + fecha) relevante solo para normas `fuente: 'BCN'`, ya que ISO/RCA son documentos subidos manualmente por el tenant, no sincronizados desde un agente externo.
- Dado que Catálogo Normativo y Matriz Legal comparten el mismo dato (`LegalNorm`), se eleva `LegalMatrixProvider` de estar anidado en `/matriz-legal` a vivir en el layout de `(dashboard)` — mismo criterio ya aplicado a `ObligationsProvider`/`AuditsProvider`/`PlanAccionProvider` en las Secciones F y G, para que una asignación hecha en S-26 se refleje inmediatamente en el listado de Matriz Legal (S-08) sin duplicar estado.
- "Marcar como aplicable a mi planta" (S-25) y "Definir Normas Aplicables por Planta" (S-26) son, en la práctica, la misma operación (agregar `plantIds` a una norma) vista desde dos entradas distintas — se implementan sobre el mismo método del store (`setNormPlants`) para no duplicar lógica (H4).

## Componentes Atomic Design necesarios

- Átomos: reutiliza `StatusBadge` (nuevo mapeo para estado de sincronización — ver decisión abajo).
- Moléculas: reutiliza `FormField`, `FilterBar`.
- Organismos: `CatalogNormsTable` (S-25, incluye panel Superadmin de salud del agente), `AssignNormsToPlant` (S-26, selector de dos columnas).
- Templates: ninguno nuevo.

## Decisión: estado de sincronización

Se agrega `sincronizacion?: { estado: 'sincronizado' | 'desactualizado' | 'error'; fecha: string }` a `LegalNorm` (solo poblado para `fuente === 'BCN'`). Se mapea a `SemaforoStatus` existente (sincronizado→cumple, desactualizado→parcial, error→no_cumple) sin agregar nuevos valores al átomo `StatusBadge` (H4), igual criterio que el mapeo de estados de Auditorías/NC en la Sección G.

## Datos de ejemplo necesarios (mock data)

- Ampliado `mocks/catalog.ts`: las normas `fuente: 'BCN'` (norm-1, norm-4) reciben `sincronizacion` de ejemplo (una sincronizada, una desactualizada) para representar el caso de catálogo público que necesita "Forzar sincronización".

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — badge de sincronización siempre ícono+color+texto; panel de salud del agente deshabilitado con explicación, no oculto ni roto.
- [x] H2 Correspondencia con el mundo real — "BCN", "ISO", "RCA" sin sinónimos inventados, igual que en Matriz Legal.
- [x] H4 Consistencia — mismo `LegalNorm`/`StatusBadge` que Matriz Legal; "marcar aplicable" y "asignar a planta" comparten la misma función del store.
- [x] H5 Prevención de errores — S-26 no permite guardar sin al menos revisar la selección; contador visible antes de guardar.
- [x] H6 Reconocer antes que recordar — buscador y filtros persistentes y visibles (H6), selector de planta siempre visible en S-26.
- [x] H8 Estética minimalista — panel Superadmin solo visible para ese rol, no satura la vista de Admin Empresa/Usuario Interno.
