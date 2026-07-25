# Sección I — Gestores / Sub-tenancy (S-27 a S-30)

Fuente: "Prompts de Diseño — Ambienta v1.5" (Notion) + "Análisis Funcional v1.5" (Notion), ambos actualizados 2026-07-23.

## Elementos visuales identificados (Prompts de Diseño v1.5)

- **S-27 Listado de Clientes (Sub-tenants)**: listado de clientes del gestor con datos básicos y estado.
- **S-28 Detalle de Cliente**: datos del cliente, contactos y personas autorizadas. Campos customizables por tenant.
- **S-29 Contratos del Cliente**: listado y detalle de contratos. Soporte de campos dinámicos/customizables. Opción de subir PDF de contrato para que la IA proponga/extraiga campos clave (cuando esté disponible).
- **S-30 Declaraciones del Sub-tenant**: vista de las obligaciones/declaraciones del cliente final (reutiliza lógica de Obligaciones).

## Requisitos funcionales correspondientes (Notion v1.5)

- RF-56: soporte para clientes tipo gestor (Veolia, Resistance, etc.) que administran residuos/servicios de sus propios clientes.
- RF-57: los gestores operan con sub-tenancy: pueden ver y gestionar declaraciones y residuos de sus clientes finales.
- RF-58: el módulo de gestores permite registrar datos del cliente (sub-tenant), contactos y personas autorizadas, contrato.
- RF-58b: campos customizables por tenant (libertad de crear campos adicionales).
- RF-58c: idealmente, subir PDF de contrato y que la IA proponga/extraiga los campos relevantes.

## Gaps o inconsistencias detectadas

- RF-58c (extracción de campos por IA desde PDF) depende de `apps/ai-service` (esqueleto sin implementar) — **fuera de alcance**, mismo criterio que RF-11/RF-45 en Secciones D y H. El alta de contrato solo permite completar campos manualmente.
- Decisión pendiente #4 del Análisis Funcional v1.5 ("Cómo modelar campos libres por tenant") se resuelve para esta iteración con un `Record<string, string>` simple (par clave-valor dinámico) en vez de evaluar una librería tipo CRM — es la opción más simple que satisface RF-58b sin sobre-diseñar antes de que el equipo decida formalmente.
- S-30 "reutiliza lógica de Obligaciones" pero **no reutiliza el organismo `CreateObligationModal`** tal cual, porque ese modal no contempla un `subTenantId` — se añade `subTenantId` opcional a `Obligation` (no rompe las Secciones E/F, que no lo usan) y se construye una vista de solo-listado para S-30 en esta iteración; la creación de una obligación para un sub-tenant específico queda como extensión futura del modal existente, no como uno nuevo duplicado.
- El rol **Gestor** es el único que ve esta sección (RF-56/57) — validado en el sidebar (`gestorOnly`) ya preparado desde la Fundación.

## Componentes Atomic Design necesarios

- Átomos: reutiliza `StatusBadge` (activo/inactivo → cumple/no_cumple).
- Moléculas: reutiliza `FormField`, `Breadcrumbs`.
- Organismos: `SubTenantsListTable` (S-27), `SubTenantDetailView` (S-28, contactos), `ContractsListView` (S-29, campos dinámicos), `SubTenantDeclarationsView` (S-30, reutiliza `Obligation`/`StatusBadge`, no el modal de creación).

## Datos de ejemplo necesarios (mock data)

- Nuevo `mocks/gestores.ts`: 2 clientes (sub-tenants) del tenant Gestor (`tenant-2`, Veolia), cada uno con 2 contactos (uno marcado autorizado) y 1 contrato con campos dinámicos de ejemplo.
- 2 obligaciones existentes de `mocks/obligations.ts` (tenant-2) se les agrega `subTenantId` para poblar S-30 sin inventar un modelo paralelo.

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — estado activo/inactivo del sub-tenant, badge de contacto autorizado.
- [x] H2 Correspondencia con el mundo real — "Cliente", "Contacto autorizado", "Contrato" tal como los usa un gestor de residuos, no jerga de software.
- [x] H4 Consistencia — mismo `StatusBadge`/patrón de tabla `overflow-x-auto` que el resto de la plataforma; S-30 reutiliza el modelo `Obligation` sin duplicarlo.
- [x] H5 Prevención de errores — campos dinámicos de contrato validan que la clave no esté vacía ni duplicada antes de agregar.
- [x] H6 Reconocer antes que recordar — breadcrumb Gestores > [cliente] > Contratos/Declaraciones.
- [x] H10 Ayuda y documentación — estado vacío de contratos/declaraciones con guía de próximo paso.
