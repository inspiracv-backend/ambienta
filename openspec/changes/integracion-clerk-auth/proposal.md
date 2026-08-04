# Proposal: Integracion de Clerk como proveedor de autenticacion

Fuentes: `docs/arquitectura/adr/ADR-006-autenticacion-clerk.md` (Aceptado, 03-ago-2026) · `Analisis Funcional v1.8` (Notion) · `apps/api/app/deps.py` (auth actual: header X-Tenant-Id sin JWT) · `apps/web/components/organisms/DevRoleSwitcher/` (login mock actual) · `openspec/changes/sistema-actores-roles-rbac/` (spec de actores, aprobada).

## Contexto

La autenticacion actual de Ambienta es **simulada**:

1. **Frontend**: el DevRoleSwitcher muestra una lista de usuarios de la BD.
   Al seleccionar uno, guarda `userId` y `tenantId` en memoria (React context).
   No hay JWT, no hay sesion real, no hay proteccion de rutas.

2. **API**: el unico mecanismo de identificacion es el header `X-Tenant-Id`
   que el frontend envia en cada request. Cualquiera puede inventar un UUID
   y la API lo acepta. No hay validacion de identidad.

3. **RLS funciona**, pero confia ciegamente en que el caller dice la verdad
   sobre su tenant. En produccion esto es una vulnerabilidad critica.

El **ADR-006** (aprobado 03-ago-2026) decidio usar **Clerk** como proveedor.
Esta propuesta especifica como integrarlo en ambas capas.

### Que se rompe hoy

- Un usuario puede acceder a datos de otro tenant inventando un header.
- No hay login real: el DevRoleSwitcher es visible en produccion si no se
  elimina manualmente.
- No se puede desplegar a produccion sin autenticacion real.
- Los logs de auditoria registran `user_id` de la sesion simulada, sin
  garantia de que corresponda a un usuario real.

## Objetivo

Reemplazar la autenticacion simulada por **Clerk** en dos capas:

1. **Frontend**: `@clerk/nextjs` con middleware, proteccion de rutas,
   componentes de login/signup, y sesion real con JWT.
2. **API**: validar JWT de Clerk en FastAPI, extraer `user_id` y `tenant_id`
   de los claims, y alimentar el mecanismo de RLS existente.

Al terminar, el DevRoleSwitcher desaparece y el sistema tiene login real
con soporte para Microsoft SSO, Google SSO, email+password y MFA.

## Alcance

### Incluye

- Instalar y configurar `@clerk/nextjs` en `apps/web`
- Clerk Middleware para proteger rutas del App Router
- Componentes de login/signup de Clerk (reemplazan DevRoleSwitcher)
- Sincronizacion Clerk → tabla `users`: webhook `user.created` / `user.updated`
- Validar JWT de Clerk en FastAPI (`deps.py`) con la JWKS publica
- Extraer `tenant_id` del JWT (claim custom o metadata de user)
- Mapeo de usuario Clerk → usuario en nuestra BD (`users.clerk_id`)
- Enviar JWT como `Authorization: Bearer <token>` en el api-client del frontend
- Configurar Microsoft SSO y Google SSO en el dashboard de Clerk
- Variables de entorno: `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_JWKS_URL`
- Eliminar DevRoleSwitcher del build de produccion
- Actualizar `docker-compose.yml` y `.env.example` con las nuevas variables

### NO incluye

- **RBAC granular** — los 39 permisos siguen en nuestra BD (spec separada
  `sistema-actores-roles-rbac`). Clerk solo autentica, no autoriza.
- **Organizations de Clerk** — decision: **no usarlas** (ver ADR-006,
  mitigacion de lock-in). El tenant_id vive solo en nuestra BD.
- **Flujo de Cliente Invitado** (RUT + clave dinamica) — es un flujo
  custom que no pasa por Clerk (spec separada, ABA-23).
- **Clave local post-SSO** (RF-06) — spec separada (ABA-24).
- **MFA obligatorio por tenant** — Clerk lo trae, pero la configuracion
  por tenant es post-MVP.
- **Migracion de usuarios existentes** — no hay usuarios reales todavia;
  los del seed son de desarrollo.

## Decisiones de diseño

### 1. Tenant en nuestra BD, no en Clerk Organizations

**Decision:** el campo `tenant_id` vive **solo** en `users.tenant_id` de
nuestra base de datos. No se usan Organizations de Clerk.

**Razon:** la sub-tenancy por contrato (RF-65, RF-66) no encaja en el
modelo plano de organizations. Mantiene el proveedor reemplazable (punto 2
de mitigacion del lock-in en ADR-006).

**Consecuencia:** al crear un usuario en Clerk, hay que guardar su
`tenant_id` como `publicMetadata.tenant_id` para que aparezca en el JWT.
La API lo lee del claim y lo usa para el `SET LOCAL`.

### 2. Una sola dependencia de FastAPI para validar tokens

**Decision:** toda la logica de validacion vive en `deps.py`, en una
funcion `get_current_user()` que reemplaza `get_tenant_id()`. El resto
de la API no sabe que Clerk existe.

**Razon:** mitigacion del lock-in (ADR-006 punto 1). Si manana se
cambia de proveedor, se toca un archivo.

### 3. DevRoleSwitcher se mantiene en desarrollo

**Decision:** en `NODE_ENV=development` y sin `CLERK_PUBLISHABLE_KEY`,
el DevRoleSwitcher sigue funcionando como fallback para desarrollo local
sin cuenta de Clerk. En produccion (o con Clerk configurado) desaparece.

## Criterios de aceptacion

- [ ] Al acceder a `/dashboard` sin sesion, redirige a la pagina de login de Clerk
- [ ] Al hacer login con email+password, se crea sesion y se redirige al dashboard
- [ ] El JWT de Clerk incluye `tenant_id` en los claims (via publicMetadata)
- [ ] La API valida el JWT con la JWKS publica de Clerk y extrae user_id + tenant_id
- [ ] El RLS sigue funcionando: tenant 1 no ve datos de tenant 2
- [ ] Microsoft SSO funciona (configurado en dashboard de Clerk)
- [ ] Google SSO funciona (configurado en dashboard de Clerk)
- [ ] El api-client envia `Authorization: Bearer <token>` en vez de solo `X-Tenant-Id`
- [ ] Si el JWT es invalido o expirado, la API responde 401
- [ ] El DevRoleSwitcher no aparece cuando Clerk esta configurado
- [ ] El DevRoleSwitcher sigue funcionando en dev sin Clerk (fallback)
- [ ] La tabla `users` tiene columna `clerk_id` que referencia al usuario de Clerk
- [ ] Los webhooks de Clerk sincronizan creacion/actualizacion de usuarios

## Alternativas consideradas

**JWT propio sin proveedor.** Es lo que planteaba el Analisis Funcional v1.7
original (RF-05). Requiere implementar OAuth con Microsoft y Google a mano,
rotacion de tokens, MFA, passkeys y recuperacion de clave. Semanas de
trabajo que no aporta diferenciacion al producto. Descartado en ADR-006.

**Supabase Auth.** La integracion nativa con RLS suena ideal, pero solo
sirve cuando el cliente habla directo con PostgREST. Ambienta tiene FastAPI
en el medio, asi que esa ventaja no aplica. Descartado en ADR-006.

**Firebase Auth.** Sin historia con Postgres, multi-tenancy real exige
Identity Platform, y arrastra a GCP. Descartado en ADR-006.
