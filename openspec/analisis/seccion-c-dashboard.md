# Sección C — Dashboard del Tenant (S-06, S-07)

Fuente: "Prompts de Diseño — Ambienta v1.5" (Notion) + "Análisis Funcional v1.5" (Notion), ambos actualizados 2026-07-23.

## Elementos visuales identificados (Prompts de Diseño v1.5)

- **S-06 Dashboard Principal**: card hero con próximo vencimiento crítico (nombre, días restantes, semáforo ícono+color+texto); resumen de % de cumplimiento global (semáforo grande) con acceso a configuración del cálculo; contadores (artículos en incumplimiento, No Conformidades abiertas, Planes de Acción activos); lista compacta de próximos 5 vencimientos; acceso rápido al Chatbot; variante con vencimiento crítico en rojo y mayor peso visual.
- **S-07 Dashboard Multi-Instalación**: selector de alcance ("Todas las plantas" o selección múltiple); tabla/grid (planta, % cumplimiento con semáforo completo, N° incumplimientos, N° NC activas, próximo vencimiento crítico); ordenamiento por columna (peor cumplimiento primero); click en fila → dashboard filtrado; variante Superadmin compara tenants (solo métricas agregadas); denso tipo tabla ejecutiva en desktop, colapsa a tarjetas en mobile.

## Requisitos funcionales correspondientes (Notion v1.5)

- RF-47: Dashboard consolidado (semáforo, próximos vencimientos críticos, NC activas, resumen por instalación, alertas prioritarias).
- RF-48: Panel multi-cliente/multi-instalación con visibilidad consolidada (según permisos).
- RF-49: vista de artículos/tareas en incumplimiento con acceso directo a evidencias, historial, planes de acción.
- RF-51: botón de configuración del % de cumplimiento (qué entra en el cálculo).
- Nota del funcional: "El Dashboard no es un módulo independiente; opera siempre dentro del contexto del tenant y se alimenta de Matriz Legal, Obligaciones, Calendario y No Conformidades."

## Gaps o inconsistencias detectadas

- RF-49 ("acceso directo a evidencias, historial y planes de acción" desde el dashboard) no tiene representación explícita en el prompt visual S-06 más allá de la lista de próximos 5 vencimientos. **Resuelto en la iteración de Sección E**: cada item de `DeadlinesList` ahora enlaza a `/obligaciones/[id]` (el detalle de evidencias/historial vive ahí).
- El botón de configuración del % de cumplimiento (RF-51 / S-11) pertenece formalmente a la Sección D (Matriz Legal), pero S-06 lo menciona como accesible desde el Dashboard. **Resuelto en la iteración de Sección D**: el ícono ahora enlaza a `/matriz-legal` (la configuración real es por norma, ahí vive S-11) en vez de estar deshabilitado.
- La variante "Superadmin compara tenants" de S-07 requiere datos agregados cross-tenant que hoy no tienen mock propio — se cubre con los 2 tenants de `mocks/tenants.ts`.
- El tercer contador de S-06 ("Planes de Acción activos") depende de una entidad `PlanDeAccion` que aún no existe en `packages/shared` (pertenece a S-19, Sección F, no implementada). En vez de inventar datos para una entidad inexistente, se reemplaza ese contador por **"Obligaciones por vencer (≤30 días)"**, que sí tiene respaldo real en `mocks/obligations.ts`. **A resolver cuando se implemente la Sección F**: introducir `PlanDeAccion` en `packages/shared` y restaurar el contador original.

## Componentes Atomic Design necesarios

- Átomos: `StatusBadge`/semáforo (ícono+color+texto — reutilizado en todas las pantallas futuras, por eso se construye ahora como átomo base y no como parte de un organismo), `Icon`, `Avatar` (para header de usuario).
- Moléculas: `MetricCounter` (contador con etiqueta), `DeadlineListItem` (item de la lista de próximos vencimientos).
- Organismos: `DashboardHeroCard`, `DeadlinesList`, `MultiPlantTable` (con colapso a tarjetas en mobile — mismo organismo `DataTable` reutilizable a futuro por Matriz Legal/Catálogo/Usuarios, per heurística H4).
- Templates: `DashboardLayout` (header persistente con tenant/rol activo + sidebar de navegación global, ver sección "Navegación global sugerida" del Esquema de Pantallas).

## Datos de ejemplo necesarios (mock data)

- `mocks/obligations.ts`: obligaciones con estados vigente / por vencer (≤30 días) / vencida / sin evidencia, cruzando el mismo tenant que se usará en Auth.
- `mocks/tenants.ts`: al menos 1 tenant con 1 sola planta (caso simple) y 1 tenant con múltiples plantas (para probar S-07).
- Casos límite: tenant sin vencimientos próximos (empty state), planta con 0% de cumplimiento (semáforo rojo), planta con evaluación incompleta (N/E — sin representación de semáforo, mostrar como "pendiente de evaluar").

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — header persistente con tenant/rol; skeleton de carga en hero card y tabla multi-planta; contadores visibles sin navegar.
- [x] H2 Correspondencia con el mundo real — nomenclatura exacta de RETC/Ley REP/SINADER/SIDREP/DAE en la lista de vencimientos; semáforo verde/amarillo/rojo.
- [x] H4 Consistencia — mismo átomo `StatusBadge` en hero card, contadores y tabla multi-planta.
- [x] H6 Reconocer antes que recordar — breadcrumb no aplica (es la pantalla raíz), pero el selector de planta persiste visible.
- [x] H7 Flexibilidad y eficiencia — vista simplificada para Admin Empresa (sin densidad operativa) vs vista densa para Usuario Interno/Encargado operativo, ambas sobre el mismo Dashboard Principal con distinta densidad de información mostrada.
- [x] H8 Estética minimalista — Dashboard prioriza vencimientos próximos y NC abiertas, no satura con métricas secundarias.
- [ ] H9 Recuperación de errores — aplica si falla la carga de datos (empty/error state de la tabla), se implementa con mensaje humano.
