# Design: Sistema de Actores, Roles, Multi-tenancy y Audit Log

## Arquitectura

### Módulos NestJS (`apps/api/src/`)

```
apps/api/src/
├── auth/              # Passport strategies, JWT, guards, decorators
│   ├── strategies/     # local-rut-clave.strategy.ts, microsoft.strategy.ts (stub), google.strategy.ts (stub)
│   ├── guards/         # jwt-auth.guard.ts, perfil-empresa-complete.guard.ts, permissions.guard.ts
│   └── decorators/     # @Public(), @RequierePermiso(), @CurrentUser()
├── tenants/            # CRUD de tenants, plantas, módulos activos (Sección L del frontend)
├── perfil-empresa/     # Datos de empresa, plantas, departamentos (guard bloqueante RF-10)
├── users/              # CRUD de usuarios, invitación, roles
├── permissions/        # Catálogo de permisos + asignación granular por usuario
├── invitados/          # Flujo Cliente Invitado: link especial, RUT+clave dinámica, tickets
├── sub-tenancy/        # Contratos → creación de sub-tenants + tenant_access_grants
├── audit/              # Servicio de audit log (solo INSERT, nunca UPDATE/DELETE)
└── common/             # TenantScopeInterceptor, filtros de excepción, pipes de validación
```

`packages/db` (nuevo paquete compartido): cliente de PostgreSQL + esquema + migraciones. **Se propone Drizzle ORM** como default documentado — es independiente de la disputa Fastify/NestJS de ADR-002 (Drizzle funciona igual de bien sobre NestJS), combina bien con SQL crudo para las políticas RLS, y sus migraciones son explícitas e inspeccionables. Si el equipo prefiere Prisma/TypeORM, el modelo de datos de este documento no cambia, solo la capa de acceso.

### Flujo de una request autenticada

```
Request → JwtAuthGuard (valida JWT, decodifica claims: sub, tenant_id, role)
        → TenantScopeInterceptor (SET LOCAL app.current_tenant_id = <tenant_id> en la conexión)
        → PermissionsGuard (si la ruta exige @RequierePermiso(...), resuelve el set de
          permisos efectivos del usuario y verifica)
        → PerfilEmpresaCompleteGuard (si la ruta es de negocio y role=admin_empresa,
          verifica tenants.perfil_empresa_completo)
        → Controller
```

Las políticas RLS de Postgres leen `current_setting('app.current_tenant_id')`, no confían en que el controller filtre por `tenant_id` manualmente — es la segunda barrera que exige CLAUDE.md ("RLS en PostgreSQL como segunda barrera", "RBAC verificado siempre en la API, nunca solo en frontend").

## Contratos de API (alto nivel — no exhaustivo, se detalla en la spec OpenAPI cuando se implemente)

| Endpoint | Método | Auth | Notas |
|---|---|---|---|
| `/auth/local/login` | POST | Público | `{ rut, clave }` → JWT. Cubre Admin Empresa/Usuario Interno con clave local (RF-06) y Cliente Invitado con clave dinámica |
| `/auth/local/set-password` | POST | JWT (cualquier proveedor) | Setea clave local para un usuario que entró por Microsoft/Google (RF-06) |
| `/auth/microsoft/callback` | POST | Público | **Stub** — 501 hasta tener `MICROSOFT_CLIENT_ID`/`SECRET` |
| `/auth/google/callback` | POST | Público | **Stub** — 501 hasta tener `GOOGLE_CLIENT_ID`/`SECRET` |
| `/invitados/generar-acceso` | POST | Público | RF-02/RF-07: genera RUT + clave dinámica, devuelve ambos una sola vez (no se puede recuperar la clave en claro después) |
| `/invitados/tickets` | POST | JWT (Cliente Invitado) | Crea ticket de gestión |
| `/admin/invitados/:userId/registrar-permanente` | POST | JWT + `@RequierePermiso('usuarios.invitar')` | RF-03: solo Admin Empresa. Cambia `role` de `cliente_invitado` a `usuario_interno`/`admin_empresa` y exige `departamento_id` si aplica |
| `/perfil-empresa` | GET/PATCH | JWT (admin_empresa) | Datos, plantas, departamentos |
| `/perfil-empresa/completar` | POST | JWT (admin_empresa) | Marca `perfil_empresa_completo = true`, libera el guard |
| `/usuarios` | GET/POST | JWT + permiso | Listado e invitación (S-41 del frontend, ahora respaldado por datos reales) |
| `/usuarios/:id/permisos` | POST/DELETE | JWT + `@RequierePermiso('usuarios.gestionar_permisos')` | Asignar/revocar un permiso individual |
| `/contratos` | POST | JWT (admin_empresa, tenant con `es_gestor=true`) | Crea Contrato **y** el sub-tenant asociado en una transacción (RF-66) |
| `/tenant-access-grants` | GET/POST/DELETE | JWT + permiso | Consulta/otorga/revoca el acceso cruzado Gestor→sub-tenant (ver §Modelo de datos) |
| `/audit-log` | GET | JWT + `@RequierePermiso('auditoria.ver')` | Filtrado por `tenant_id`; Superadmin ve todo |

## Modelo de datos

Convención: `snake_case`, `id` como `uuid` (`gen_random_uuid()`), timestamps `created_at`/`updated_at` en todas las tablas de negocio (se omiten abajo por brevedad salvo donde importan).

### `tenants`
Igual forma que `packages/shared/src/schemas/tenant.ts` ya define para el mock de frontend (`nombre`, `rut`, `sector`, `es_gestor`, `giro`, `direccion`, `perfil_empresa_completo`, `estado`, `limite_usuarios`, `modulos_activos text[]`) **más**:
- `parent_gestor_tenant_id uuid NULL REFERENCES tenants(id)` — **NULL para tenants normales; poblado solo si este tenant es un sub-tenant** creado a partir de un Contrato. Ver decisión en "Sub-tenancy" más abajo.

### `plants`, `departamentos`
Igual forma que ya existe en `packages/shared` (Plant, Departamento) — `tenant_id`, `nombre`, y en el caso de `plants` también `comuna`/`region`.

### `users`
| Columna | Tipo | Notas |
|---|---|---|
| `id` | uuid | |
| `tenant_id` | uuid NULL | **NULL solo permitido cuando `role = 'superadmin'`** (CHECK constraint) — resuelve la inconsistencia detectada en el análisis (§6, punto no numerado sobre A0 sin tenant vs. "todo usuario pertenece a una Empresa") |
| `nombre` | text | |
| `email` | text UNIQUE | |
| `role` | enum: `superadmin`, `admin_empresa`, `usuario_interno`, `cliente_invitado`, `cliente_final` | **5 valores** — ver nota sobre Gestor abajo |
| `departamento_id` | uuid NULL REFERENCES departamentos(id) | `CHECK (role <> 'usuario_interno' OR departamento_id IS NOT NULL)` — aplica RF-11 a nivel de base de datos, no solo de UI |
| `plant_ids` | — | modelado como tabla puente `user_plants(user_id, plant_id)`, no array, para poder hacer `JOIN`/RLS por planta si se necesita más adelante |
| `rut` | text NULL | obligatorio si `role = 'cliente_invitado'` o si el usuario seteó clave local (RF-06) |
| `estado` | enum: `activo`, `invitado`, `desactivado` | igual que el mock de frontend (`lib/user-status.ts`) |
| `ultima_actividad` | timestamptz NULL | |
| `auth_provider` | enum: `microsoft`, `google`, `local`, `lti` (reservado) | `lti` se agrega al enum ahora pero no se implementa el flujo — es el punto de extensión para A6 |
| `clave_hash` | text NULL | `argon2id`, nunca texto plano (RNF-05). NULL si `auth_provider` es `microsoft`/`google` y el usuario no seteó clave local |
| `clave_dinamica_expira_en` | timestamptz NULL | solo para `cliente_invitado` — **default propuesto: 30 días desde la generación** (pregunta abierta del análisis, §2.4, sin respuesta en el documento base — se documenta aquí como supuesto a validar) |

**Nota — Gestor (A4) NO es un valor de `role`.** Se modela como la combinación `role = 'admin_empresa'` + `tenants.es_gestor = true`, siguiendo la recomendación explícita del análisis de actores (§7.2). Esto es más estricto que el mock actual de `apps/web`, que sí tiene un valor `'gestor'` separado en su `RoleSchema` — **se marca como discrepancia a reconciliar en el frontend** cuando se implemente este backend (fuera de alcance de esta propuesta, ver `tasks.md`).

### `permissions` + `user_permissions`
Tabla de catálogo + tabla de asignación (no columnas booleanas fijas, según pidió explícitamente el prompt de implementación):

```
permissions(id, key UNIQUE, descripcion)
user_permissions(user_id, permission_id, granted_by uuid REFERENCES users(id), granted_at)
```

Seed inicial de `permissions.key` (lista abierta, se agregan más sin migración estructural):
- `puede_editar_evidencia`, `puede_aprobar_cierre` (hallazgo §3.3 del análisis — hoy no existían como conceptos separados)
- `usuarios.invitar`, `usuarios.gestionar_permisos`
- `auditoria.ver`
- `platform.tenants.manage`, `platform.support.tickets` (formaliza el sub-rol de Soporte del análisis, §3.1/§7.3, **sin crear un actor nuevo** — Soporte = un usuario `role='superadmin'` que solo tiene `platform.support.tickets`, no `platform.tenants.manage`)

Cada `role` tiene un set de permisos **default** que se otorgan al crear el usuario (seed), pero pueden revocarse/ampliarse individualmente — esto resuelve la nota de diseño del análisis (§2.3): "A2 no es una fila única sino un espacio de configuración".

### `contratos` + sub-tenancy
```
contratos(id, gestor_tenant_id REFERENCES tenants(id), sub_tenant_id REFERENCES tenants(id),
          nombre, fecha_inicio, fecha_termino, campos_custom jsonb, archivo_url)
```

**Decisión de diseño (responde la pregunta abierta §6.8 y §8 del análisis):** un sub-tenant **es un tenant real** (fila en `tenants` con su propio `id`, su propio aislamiento RLS), no una partición lógica dentro del tenant del Gestor. `tenants.parent_gestor_tenant_id` solo registra la relación de origen. Crear un Contrato es una transacción que:
1. Crea el `tenant` del sub-tenant (`es_gestor = false`, `parent_gestor_tenant_id = <gestor_tenant_id>`).
2. Crea el usuario A5 inicial (`role = 'cliente_final'`, `tenant_id = <sub_tenant_id>`).
3. Crea la fila en `contratos`.
4. Crea un `tenant_access_grant` (ver abajo) con un scope mínimo por default.

Esto mantiene el aislamiento RLS **uniforme** (todo tenant se aísla igual, sin caso especial) y convierte "el Gestor administra datos del cliente final" en un **grant explícito y auditable**, no en un bypass silencioso de RLS — responde directamente el punto 8 de la sección 6 del análisis.

```
tenant_access_grants(id, grantor_tenant_id REFERENCES tenants(id),  -- el sub-tenant (dueño del dato)
                      grantee_tenant_id REFERENCES tenants(id),      -- el Gestor
                      scope enum: 'obligaciones:read', 'obligaciones:write', 'dashboard:read',
                      created_by REFERENCES users(id), created_at, revoked_at NULL)
```

Las políticas RLS de las tablas de negocio (cuando existan) deberán incluir una cláusula `OR tenant_id IN (SELECT grantor_tenant_id FROM tenant_access_grants WHERE grantee_tenant_id = current_tenant_id() AND scope = '<scope correspondiente>' AND revoked_at IS NULL)` — se documenta el patrón aquí para que los módulos de negocio futuros lo hereden.

**Default propuesto para A5 (cliente final):** lectura de sus propias Obligaciones + recepción de notificaciones, sin edición de Contrato — implementado como el set de permisos default del rol `cliente_final` (no requiere lógica especial, ya que A5 vive en su propio `tenant_id` y el RBAC normal ya lo limita).

### `refresh_tokens`
```
refresh_tokens(id, user_id REFERENCES users(id), token_hash, expires_at, revoked_at NULL, device_label, created_at)
```
Necesaria para JWT con rotación de refresh token. Como beneficio directo, esto convierte la sección "Sesiones activas" de S-42 (hoy mock puro en el frontend) en datos reales cuando se conecte — no se implementa esa conexión en esta propuesta, pero el modelo ya lo permite.

### `audit_log` (inmutable — RNF-08, RNF-25)
```
audit_log(id, actor_type enum('human','system'),
          actor_user_id uuid NULL REFERENCES users(id),      -- solo si actor_type='human'
          actor_system_key text NULL,                         -- solo si actor_type='system'
          tenant_id uuid NULL,                                -- NULL para acciones de plataforma
          action text, entity_type text, entity_id uuid,
          motivo text,                                        -- el "por qué" de RNF-08
          aprobado_por uuid NULL REFERENCES users(id),        -- el "quién aprobó", cuando aplica
          payload_before jsonb, payload_after jsonb,
          created_at timestamptz DEFAULT now())
CHECK ((actor_type = 'human' AND actor_user_id IS NOT NULL AND actor_system_key IS NULL)
    OR (actor_type = 'system' AND actor_system_key IS NOT NULL AND actor_user_id IS NULL))
```

`actor_system_key` usa los identificadores que ya sugirió el análisis de actores (§9): `system.ambiagent`, `system.ingest_bcn`, `system.monitor_normativo`, `system.ambiagent_admin`. **Inmutabilidad real, no solo de convención:** el rol de base de datos que usa `apps/api` para conectarse **no tiene privilegio `UPDATE`/`DELETE` sobre `audit_log`** (`REVOKE UPDATE, DELETE ON audit_log FROM app_role`), solo `INSERT` y `SELECT`. Cualquier corrección se hace como un nuevo registro que referencia al anterior, nunca sobrescribiendo.

## Consideraciones de seguridad

- **RLS:** cada tabla de negocio con `tenant_id` lleva una política `USING (tenant_id = current_setting('app.current_tenant_id')::uuid OR <regla de tenant_access_grants si aplica>)`. `TenantScopeInterceptor` ejecuta `SET LOCAL app.current_tenant_id` al inicio de cada transacción — nunca se confía en que el controller agregue `WHERE tenant_id = ...` a mano (RNF-07, CLAUDE.md regla 4).
- **Contraseñas y claves dinámicas:** `argon2id` para `clave_hash`. La clave dinámica de Cliente Invitado se muestra **una sola vez** en la respuesta de `/invitados/generar-acceso` (igual que ya hace el mock de frontend) y se guarda solo su hash — si expira (`clave_dinamica_expira_en`), el invitado debe generar acceso de nuevo, no se puede "recuperar" la clave vieja.
- **Rate limiting:** `/auth/local/login` e `/invitados/generar-acceso` son los dos endpoints públicos de mayor riesgo de fuerza bruta/abuso — se recomienda throttling (ej. `@nestjs/throttler`) desde el día 1, aunque el análisis original no lo menciona explícitamente.
- **OAuth stub seguro, no roto:** si `MICROSOFT_CLIENT_ID`/`GOOGLE_CLIENT_ID` no están en el entorno, el módulo de auth **no registra esas estrategias** y las rutas correspondientes devuelven `501 Not Implemented` con un mensaje claro, en vez de fallar de forma confusa o (peor) simular un login falso.
- **RBAC verificado siempre en la API:** `PermissionsGuard` es la autoridad — cualquier ocultamiento de UI en `apps/web` (como ya existe, ej. sidebar condicional) es solo cosmético, nunca la barrera real (CLAUDE.md regla 4).

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Drizzle como ORM es una decisión mía, no aprobada formalmente | Documentado como supuesto explícito (ver `tasks.md`); el modelo de datos en sí es agnóstico de ORM, se puede migrar a Prisma/TypeORM sin rediseñar tablas |
| El stub de OAuth queda "olvidado" y nunca se completa | El arranque de `apps/api` loguea una advertencia explícita si `MICROSOFT_CLIENT_ID`/`GOOGLE_CLIENT_ID` faltan, listando qué proveedor falta — visible en cada `npm run dev` hasta que se resuelva |
| `tenant_access_grants` se usa como bypass general de RLS en vez de accesos puntuales | `scope` es un enum acotado (no "acceso total"), cada grant queda en el audit log con `created_by`, y se puede revocar (`revoked_at`) sin borrar el historial |
| Un actor nuevo (ej. otro tipo de integración externa) aparece más adelante y no encaja en `actor_type` humano/sistema | El diseño de `permissions`/`user_permissions` ya es extensible sin migración; agregar un tercer `actor_type` si hiciera falta es una migración menor y aislada, no un rediseño |
| El CHECK constraint de `departamento_id` para `usuario_interno` podría chocar con datos de seed mal formados | Se seedea primero `departamentos`, luego `users`, respetando el orden de dependencias — ver `tasks.md` |
