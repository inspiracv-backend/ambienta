# Tasks: Sistema de Actores, Roles, Multi-tenancy y Audit Log

## Decisiones y supuestos documentados (a validar antes o durante la revisión de esta spec)

Por instrucción explícita del prompt de implementación adjunto ("no lo implementes en silencio con un supuesto arbitrario"), cada punto de las secciones 6 y 8 del análisis de actores queda resuelto aquí con un default concreto, no ignorado:

| # | Pregunta abierta (origen) | Default adoptado en esta spec | Fácil de cambiar? |
|---|---|---|---|
| 1 | Cardinalidad de Admin Empresa por tenant (análisis §2.2) | **N admins por tenant** — varios usuarios pueden tener `role='admin_empresa'` en el mismo `tenant_id`; no existe un "owner" singular marcado aparte | Sí — no hay constraint de unicidad; si se necesita un "dueño" designado, se agrega una columna `es_owner boolean` sin romper nada |
| 2 | ¿A4 (Gestor) es un rol de usuario o una capacidad de tenant? (análisis §2.2, §7.2) | **Capacidad de tenant**: `role='admin_empresa'` + `tenants.es_gestor=true`. Se adopta la recomendación explícita del análisis | Ya no requiere cambio — es la recomendación del propio documento fuente. **Nota:** el mock de `apps/web` sí tiene un valor `'gestor'` separado en su `RoleSchema` — queda como discrepancia a reconciliar cuando se implemente este backend (no se toca el frontend en esta propuesta) |
| 3 | Alcance de permisos de A5, cliente final del sub-tenant (análisis §3.2, §7.1) | **Mínimo viable**: lectura de sus propias Obligaciones + recepción de notificaciones, sin edición de Contrato — vía el set de permisos default del rol `cliente_final` | Sí — es solo el seed inicial de `user_permissions`, se amplía sin migración |
| 4 | ¿El Gestor tiene lectura o escritura sobre datos del sub-tenant? ¿Cómo convive con RLS/RNF-07? (análisis §2.5, §6.8) | **Ninguna de las dos de forma implícita**: se modela como `tenant_access_grants` explícito y auditable (scope acotado: `obligaciones:read`, `obligaciones:write`, `dashboard:read`), creado automáticamente con scope mínimo al crear el Contrato | Sí — agregar/quitar scopes es una fila nueva/revocada en `tenant_access_grants`, sin migración |
| 5 | ¿Expira la clave dinámica del Cliente Invitado? (análisis §2.4) | **30 días** desde la generación (`clave_dinamica_expira_en`) | Sí — es una constante de configuración, no estructural |
| 6 | Rol "Soporte" distinto de Superadmin (análisis §3.1, §7.3) | **No es un actor nuevo** — es un usuario `role='superadmin'` con el permiso `platform.support.tickets` pero sin `platform.tenants.manage` | Sí — es asignación de permisos, no estructura |
| 7 | Identidad de los agentes de IA en el audit log (análisis §3.4, §7.6) | `actor_type='system'` + `actor_system_key` con los 4 identificadores ya sugeridos por el análisis (`system.ambiagent`, `system.ingest_bcn`, `system.monitor_normativo`, `system.ambiagent_admin`) | Sí — agregar un 5º agente es una fila más en el `CHECK`/enum, no un rediseño |
| 8 | Usuario vía LTI (A6) — mapeo a roles existentes (análisis §3.6, §7.7) | **No se implementa el flujo LTI en esta propuesta.** Se reserva `auth_provider='lti'` en el enum como punto de extensión documentado; el mapeo de rol heredado (¿A2 con Departamento "Capacitación"? ver seed del análisis) queda como pregunta abierta para cuando se implemente LTI de verdad | N/A — es intencionalmente un no-implementado, no un default silencioso |
| 9 | A0 (Superadmin) sin `tenant_id` vs. "todo usuario pertenece a una Empresa" (inconsistencia detectada durante este diseño, no en el análisis original) | `tenant_id` nullable en `users`, con `CHECK` que solo lo permite NULL cuando `role='superadmin'` | Sí — es un constraint, no una decisión de producto |
| 10 | ORM (Drizzle vs. Prisma/TypeORM) — no forma parte del análisis de actores, decisión técnica mía | **Drizzle**, independiente de la disputa Fastify/NestJS de ADR-002 | Sí — el modelo de datos de `design.md` es agnóstico de ORM |

## Checklist de implementación (para cuando esta spec sea aprobada — NO ejecutado en esta sesión)

### Fundación

> **Lo de base ya existe, por otra vía.** El esquema no se construyó desde este
> cambio sino junto con el backend, así que las tareas de abajo describen un
> plan (Drizzle, `packages/db`) que no es el que se siguió. Lo que sí quedó
> hecho y cubre los requisitos de este cambio:
>
> - [x] `users`, `roles`, `permissions`, `role_permissions`, `user_roles` — en `db/01_schema.sql`
> - [x] `user_permissions` con su resolución documentada — `db/05_user_permissions.sql`
> - [x] RLS por empresa: una política por cada tabla con `tenant_id` (38 hoy)
> - [x] `audit_log` inmutable: `REVOKE UPDATE, DELETE` sobre el rol de aplicación
> - [x] `contracts` y `tenant_access_grants` — esquema sí, lógica no
> - [x] 39 permisos sembrados en `db/03_seed_catalogos.sql`
>
> **Lo que falta es la API**, no la base: resolver el permiso efectivo, aplicar
> el alcance acotado, y los flujos de gestor y cliente invitado.
- [ ] Crear `packages/db` (Drizzle + cliente de Postgres + config de migraciones)
- [ ] Levantar Postgres local (Docker Compose) — no existe hoy en el repo
- [ ] Migraciones iniciales: `tenants`, `plants`, `departamentos`, `users`, `permissions`, `user_permissions`
- [ ] Migraciones de sub-tenancy: `contratos`, `tenant_access_grants`
- [ ] Migración de `refresh_tokens`
- [x] Migración de `audit_log` + `REVOKE UPDATE, DELETE` sobre esa tabla para el rol de aplicación
- [ ] Políticas RLS por tabla (`tenant_id = current_setting(...)::uuid`, con la cláusula OR de `tenant_access_grants` donde aplique)

### Auth
- [ ] `LocalRutClaveStrategy` (real) + endpoint `/auth/local/login`
- [ ] `/auth/local/set-password` (RF-06)
- [ ] Stubs `MicrosoftStrategy`/`GoogleStrategy` con detección de env vars ausentes → 501 + warning de arranque
- [ ] Módulo JWT + `refresh_tokens` (rotación, revocación)
- [ ] `JwtAuthGuard` global + decorador `@Public()`
- [ ] `TenantScopeInterceptor` (SET LOCAL por request)

### Usuarios, permisos y Perfil Empresa
- [ ] CRUD de `users` + invitación (estado `invitado` → `activo` al primer login)
- [ ] Catálogo de `permissions` (seed) + endpoints de asignación/revocación individual
- [ ] `PermissionsGuard` + decorador `@RequierePermiso(...)`
- [ ] Endpoints de Perfil Empresa (`/perfil-empresa`, `/perfil-empresa/completar`)
- [ ] `PerfilEmpresaCompleteGuard` aplicado a las rutas de negocio que lo requieran

### Cliente Invitado
- [ ] `/invitados/generar-acceso` (RUT + clave dinámica, hash + expiración)
- [ ] `/invitados/tickets`
- [ ] `/admin/invitados/:id/registrar-permanente` (RF-03)

### Sub-tenancy (Gestor)
- [ ] `/contratos` (transacción: tenant + usuario A5 + contrato + grant inicial)
- [ ] `/tenant-access-grants` (consultar/otorgar/revocar)

### Audit log
- [ ] Servicio `AuditService.record(...)` inyectado donde corresponda (usado también por los módulos de negocio futuros)
- [x] Verificar que ningún rol de aplicación tenga `UPDATE`/`DELETE` sobre `audit_log` (test de infraestructura, no solo unitario)

### Seed data
- [ ] Cargar los usuarios de prueba de la sección 9 del análisis de actores como fixtures, incluyendo:
  - Tenant "Minera Alto Andes SpA" con Admin Empresa **sin** Perfil Empresa completo (para probar el guard bloqueante)
  - Tenant "Aguas del Maule Ltda." con Perfil Empresa completo, Usuario Interno con y sin `puede_aprobar_cierre`
  - Cadena Gestor→sub-tenant: "ResiFlow Gestión de Residuos SpA" → Contrato → sub-tenant "Panadería El Sol Ltda." → usuario A5 "Marcelo Peña"
  - Usuario A0b "Agente de Soporte" (permiso `platform.support.tickets` sin `platform.tenants.manage`) para verificar RF-84
  - Los 4 `actor_system_key` de agentes de IA, con al menos un registro de ejemplo en `audit_log` por cada uno

### Pruebas
- [ ] Test de aislamiento RLS: un usuario del tenant A no puede leer filas del tenant B ni por API ni por SQL directo con `app.current_tenant_id` distinto
- [ ] Test del CHECK `usuario_interno` → `departamento_id` obligatorio
- [ ] Test del guard de Perfil Empresa bloqueando rutas de negocio hasta completar el perfil
- [x] Test de que `audit_log` rechaza `UPDATE`/`DELETE` a nivel de base de datos, no solo de aplicación
- [ ] Test del flujo completo Cliente Invitado → ticket → registrar permanente (RF-01 a RF-03)
- [ ] Test de `tenant_access_grants`: el Gestor no puede leer/escribir el sub-tenant sin un grant activo, y deja de poder hacerlo tras revocarlo

## Explícitamente fuera de esta propuesta (ver `proposal.md`)

- Implementación real de OAuth Microsoft/Google (esperando credenciales del usuario)
- Flujo LTI 1.3 completo (A6)
- Resolución formal de ADR-002
- Cualquier módulo de negocio (Matriz Legal, Obligaciones, etc.)
- Reconciliación del mock de `apps/web` (su `RoleSchema` con `'gestor'` como valor propio) con el modelo de este backend

## Revisión

- [ ] Revisión de esta spec por el usuario/equipo técnico antes de iniciar el checklist de implementación (regla no negociable de CLAUDE.md — spec aprobada antes de código)
