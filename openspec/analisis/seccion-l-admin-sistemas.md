# Sección L — Admin de Sistemas / Superadmin (S-36 a S-38)

Fuente: "Prompts de Diseño — Ambienta v1.5" (Notion) + "Análisis Funcional v1.5" (Notion), ambos actualizados 2026-07-23.

## Elementos visuales identificados (Prompts de Diseño v1.5)

- **S-36 Gestión de Tenants**: tabla de empresas (nombre, estado, cantidad de usuarios, módulos habilitados). Acciones: habilitar/deshabilitar, editar límites.
- **S-37 Detalle/Configuración de Tenant**: límites de usuarios, módulos activos, información básica.
- **S-38 Soporte/Tickets internos**: listado de tickets de soporte, nuevos requerimientos, capacidad de corregir logs erróneos (con auditoría). Diferenciar claramente vista interna vs. lo que ve el cliente.

## Requisitos funcionales correspondientes (Notion v1.5)

- RF-59: Superadmin habilita/deshabilita tenants, define límites de usuarios y módulos activos.
- RF-60: gestión de planes de prueba y onboarding de nuevos clientes.
- RF-61: módulo de Soporte — listado de tickets, nuevos requerimientos, corrección de logs erróneos (con auditoría).
- RF-62: diferenciar claramente lo que ve el cliente vs. el equipo interno/Superadmin.

## Nota crítica de seguridad (CLAUDE.md, no negociable)

**Superadmin NO puede editar contenido de tenants** — solo gestión de plataforma (estado, límites, módulos activos). S-37 nunca expone edición de plantas, obligaciones, matriz legal ni ningún dato de negocio del tenant; eso es exclusivo de Admin Empresa/Usuario Interno dentro de su propio tenant. El RBAC real se valida siempre en la API — esta separación en el frontend es solo UX.

## Gaps o inconsistencias detectadas

- RF-60 (planes de prueba y onboarding de nuevos clientes) **no tiene pantalla propia** en el Esquema de Pantallas v1.5 (no hay S-xx para ello) — se deja fuera de esta iteración; el ítem "Planes de prueba" del sidebar permanece deshabilitado.
- El "ticket de soporte" de S-38 es una **entidad distinta** del "ticket único" de Obligaciones/Calendario (Sección F) — son conceptos homónimos pero no relacionados (uno es un plazo regulatorio, el otro una solicitud de ayuda). Se modela `SupportTicket` como schema nuevo e independiente, sin ninguna relación con `Obligation`/`ObligationTask` (H2: mismo nombre "ticket" en el dominio de negocio, pero conceptos distintos — se evita la confusión documentándolo explícitamente).
- **Se cierra un cabo suelto de la Sección A**: el formulario "Crear Ticket" (S-03) solo generaba un número de ticket aleatorio sin persistir nada — no había ningún dato real detrás. En esta iteración se conecta `TicketForm` a un `SupportTicketsProvider` real (elevado a `app/layout.tsx`, porque un Cliente Invitado crea el ticket **fuera** del layout de `(dashboard)`) para que los tickets creados en S-03 aparezcan de verdad en el listado de Soporte (S-38) — cumpliendo RF-61 de punta a punta.
- "Corregir logs erróneos (con auditoría)" (RF-61) se implementa como un registro de correcciones acotado al propio ticket (`correcciones: {fecha, autorId, nota}[]`), no como el audit log completo transversal ya documentado como gap en las Secciones D/E/F/G.

## Componentes Atomic Design necesarios

- Átomos: reutiliza `StatusBadge` (estado de tenant y de ticket, mapeados al semáforo existente).
- Moléculas: reutiliza `FormField`, `Breadcrumbs`.
- Organismos: `TenantsManagementTable` (S-36), `TenantConfigView` (S-37 — solo campos de plataforma, nunca contenido de negocio), `SupportTicketsView` (S-38, listado + detalle con corrección auditada).
- Templates: ninguno nuevo.

## Datos de ejemplo necesarios (mock data)

- `Tenant` (Sección A/C, ya existente) se extiende con `estado`, `limiteUsuarios`, `modulosActivos`.
- Nuevo `mocks/support-tickets.ts`: al menos un ticket de ejemplo, más los que se generen en vivo desde S-03.

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — estado de tenant (activo/suspendido) y de ticket siempre con ícono+color+texto.
- [x] H2 Correspondencia con el mundo real — se evita la ambigüedad del término "ticket" (soporte vs. obligación) mediante etiquetas explícitas en cada pantalla.
- [x] H4 Consistencia — mismo `StatusBadge`/patrón de tabla que el resto de la plataforma.
- [x] H5 Prevención de errores — confirmación antes de deshabilitar un tenant (acción con impacto en usuarios reales).
- [x] H6 Reconocer antes que recordar — breadcrumb Gestión de Tenants > [empresa]; Soporte > [ticket].
- [x] H9 Recuperación de errores — mensajes humanos si falta un campo al corregir un ticket.
- [x] H10 Ayuda y documentación — diferenciación visual clara (badge/nota) entre lo que ve el cliente y lo que ve el equipo interno (RF-62).
