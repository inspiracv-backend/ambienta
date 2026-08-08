# Proposal: Integracion de Clerk como proveedor de autenticacion

Fuentes: `docs/arquitectura/adr/ADR-006-autenticacion-clerk.md` (Aceptado, 03-ago-2026) · `Analisis Funcional v1.8` (Notion, §3.1 RF-01 a RF-09) · `apps/api/app/deps.py` (auth actual) · `apps/web/components/organisms/DevRoleSwitcher/` (login mock) · `openspec/changes/sistema-actores-roles-rbac/` (spec de actores).

## Contexto

La autenticacion actual de Ambienta es **simulada en ambas capas**:

1. **Frontend**: el componente `DevRoleSwitcher` muestra una lista de usuarios
   del seed de la BD. Al seleccionar uno, guarda `userId` y `tenantId` en
   memoria (React context). No hay JWT, no hay sesion real, no hay proteccion
   de rutas server-side.

2. **API**: el unico mecanismo de identificacion es el header `X-Tenant-Id`
   que el frontend envia en cada request (`api-client.ts:29`). No se valida
   identidad: cualquier caller puede inventar un UUID y la API lo acepta sin
   cuestionarlo.

3. **RLS funciona**, pero confia ciegamente en que el caller dice la verdad
   sobre su tenant. `deps.py:34` ejecuta `SET LOCAL ROLE ambienta_app` y
   `set_config('ambienta.tenant_id', ...)` con el valor que llega del header.

El **ADR-006** (aprobado 03-ago-2026) decidio usar **Clerk** como proveedor,
descartando JWT propio, Supabase Auth y Firebase Auth. Esta propuesta
especifica como integrarlo.

### Que se rompe hoy

1. **Acceso cross-tenant trivial.** Un usuario puede ver datos de otro tenant
   fabricando un header `X-Tenant-Id`. Las politicas de RLS no sirven si el
   dato de entrada es mentira.
2. **No hay login real.** El DevRoleSwitcher esta en el build de produccion
   si no se elimina manualmente. No hay redireccion a login, no hay sesion,
   no hay logout.
3. **No se puede desplegar a produccion.** Sin autenticacion real, exponer la
   app a internet seria dar acceso irrestricto a todos los datos.
4. **Los audit logs son ficcion.** Registran `user_id` de la sesion simulada
   sin garantia de que corresponda a un humano real.

## Objetivo

Reemplazar la autenticacion simulada por **Clerk** en dos capas:

1. **Frontend**: `@clerk/nextjs` con middleware, proteccion de rutas,
   componentes de login/signup, y sesion real con JWT.
2. **API**: validar JWT de Clerk en FastAPI, extraer `user_id` y `tenant_id`
   de los claims, y alimentar el mecanismo de RLS existente sin cambiarlo.

Al terminar, el sistema tiene login real con soporte para email+password,
Microsoft SSO, Google SSO y MFA — todo gestionado por Clerk.

## Decision estructural: tenant en nuestra BD, no en Clerk Organizations

Clerk trae una primitiva de **Organizations** con invitaciones y roles por
organizacion. La pregunta es si mapear organizations a tenants o mantener el
tenant solo en nuestra base.

**Decision: (b) Tenant solo en nuestra base.** Clerk autentica; la pertenencia
y los permisos son nuestros.

**Por que.** La sub-tenancy por contrato (RF-65, RF-66) no encaja en el modelo
plano de organizations. Un Gestor crea sub-tenants a partir de un Contrato
formal, con dashboard propio del cliente final — eso no tiene equivalente en
Clerk. Ademas, los 39 permisos granulares del RBAC (RF-08) ya estan modelados
en nuestra BD y no conviene duplicarlos.

**Consecuencia practica.** Al crear un usuario en Clerk, se guarda su
`tenant_id` como `publicMetadata.tenant_id` para que aparezca en el JWT.
La API lo lee del claim firmado — ya no se puede falsificar.

## Alcance

### Incluye

- `@clerk/nextjs` en `apps/web`: provider, middleware de rutas, `<SignIn />`,
  `<SignUp />`, `<UserButton />`
- Validar JWT de Clerk en FastAPI con JWKS publica (RS256)
- Extraer `user_id` y `tenant_id` del JWT firmado — reemplaza el header
  `X-Tenant-Id` sin cambiar `get_tenant_db()`
- Sincronizacion Clerk → tabla `users` via webhook (`user.created`,
  `user.updated`)
- Columna `clerk_id` en tabla `users` para vincular identidades
- Envio de `Authorization: Bearer <token>` en el api-client del frontend
- Configuracion de Microsoft SSO y Google SSO en dashboard de Clerk (sin codigo)
- Variables de entorno nuevas en `.env.example` y `docker-compose.yml`
- Fallback: DevRoleSwitcher sigue funcionando en desarrollo sin Clerk

### NO incluye

- **RBAC granular** — los 39 permisos siguen en nuestra BD; Clerk solo
  autentica, no autoriza. Va en la spec de `sistema-actores-roles-rbac`.
- **Organizations de Clerk** — decision explicita de no usarlas (ver arriba).
- **Flujo de Cliente Invitado** (RF-01, RF-02, RF-07: link especial + RUT +
  clave dinamica) — es un flujo custom que no pasa por Clerk. Spec separada,
  ABA-23.
- **Clave local post-SSO** (RF-06) — spec separada, ABA-24.
- **MFA obligatorio configurable por tenant** — Clerk lo trae, pero la
  configuracion por tenant es post-MVP.
- **Migracion de usuarios reales** — no hay: los del seed son de desarrollo.
- **Codigo de implementacion** — esta propuesta es spec-only (CLAUDE.md §1).

## Lo que esto exige del resto del sistema

| Area | Impacto |
|---|---|
| `apps/api/app/deps.py` | `get_tenant_id()` pasa de leer un header a extraer del JWT. `get_tenant_db()` no cambia. |
| `apps/api/app/auth.py` | Modulo nuevo. Toda la logica de validacion JWT vive aqui (mitigacion lock-in). |
| `apps/api/app/routers/webhooks.py` | Router nuevo para recibir eventos de Clerk (sin auth JWT — se verifica con svix). |
| `apps/web/lib/api-client.ts` | Agregar `Authorization: Bearer` al request. Mantener fallback `X-Tenant-Id` para dev. |
| `apps/web/middleware.ts` | Archivo nuevo. `clerkMiddleware` protege todas las rutas excepto login/signup. |
| `apps/web/app/layout.tsx` | Envolver en `<ClerkProvider>`. |
| `apps/web/app/(auth)/login/page.tsx` | Condicional: `<SignIn />` si Clerk esta configurado, DevRoleSwitcher si no. |
| Todos los stores (`lib/*-store.tsx`) | Pasar `token` de Clerk en las llamadas a `api.*`. Son 13 stores. |
| `db/01_schema.sql` | `ALTER TABLE users ADD COLUMN clerk_id TEXT UNIQUE`. |
| `.env.example` | 6 variables nuevas de Clerk (3 frontend, 3 backend). |
| `docker-compose.yml` | Las variables de Clerk en los servicios `web` y `api`. |
| Docs (`entornos.md`, `setup-local.md`) | Seccion sobre desarrollo con y sin Clerk. |
| GitHub Actions CI | Las variables de Clerk son secretos; CI corre sin ellas (fallback). |
| Dashboard (S-06) | No cambia funcionalmente, pero los datos que muestra ahora estan protegidos por auth real. |
| Audit log | Los `user_id` registrados ahora corresponden a usuarios reales de Clerk. |

## Decisiones que requiere el equipo

Estas **no** las resuelve esta propuesta por su cuenta:

1. **¿Como se onboardean los primeros usuarios reales en Clerk?** Los del seed
   SQL no existen en Clerk. Hay que decidir si el Admin Empresa los crea desde
   el dashboard de Clerk, si se expone un flujo de invitacion en la app, o si
   se crea un script de migracion que los suba via API de Clerk.

2. **¿El `tenant_id` va en `publicMetadata` o en un claim custom?** Ambos
   aparecen en el JWT. `publicMetadata` es mas simple (se setea via API de
   Clerk); un claim custom es mas limpio semánticamente pero requiere
   configurar un template de JWT en Clerk. La propuesta asume `publicMetadata`.

3. **¿Se verifica la calidad del SSO con Microsoft/Entra ID antes de
   comprometerse?** ADR-006 lo dejo como pendiente de verificar. Algunos
   tenants de Azure tienen configuraciones restrictivas que pueden bloquear
   el flujo. Conviene probar con una cuenta real antes de documentar SSO como
   feature.

4. **¿Se permite signup sin invitacion?** Hoy el Admin Empresa registra
   usuarios (RF-03). Si Clerk permite self-signup, cualquiera podria crearse
   cuenta. Hay que decidir si se deshabilita signup publico o si se permite
   con aprobacion posterior.

5. **¿Que pasa con el DevRoleSwitcher a largo plazo?** La propuesta lo
   mantiene como fallback en dev. Si el equipo crece, todo desarrollador
   necesitaria una cuenta de Clerk o depender del fallback. Definir el corte.

## Criterios de aceptacion

- [ ] Al acceder a `/dashboard` sin sesion, redirige a la pagina de login de Clerk
- [ ] Login con email+password crea sesion y redirige al dashboard con datos reales
- [ ] El JWT de Clerk incluye `tenant_id` en los claims (via publicMetadata)
- [ ] La API valida el JWT con la JWKS publica y extrae user_id + tenant_id
- [ ] El RLS sigue funcionando: tenant 1 no ve datos de tenant 2
- [ ] Microsoft SSO funciona end-to-end
- [ ] Google SSO funciona end-to-end
- [ ] El api-client envia `Authorization: Bearer <token>` en cada request
- [ ] Un JWT invalido o expirado produce 401 en la API, no datos vacios
- [ ] Sin `CLERK_PUBLISHABLE_KEY`, el DevRoleSwitcher sigue funcionando (fallback dev)
- [ ] La tabla `users` tiene `clerk_id` que vincula al usuario de Clerk
- [ ] Los webhooks de Clerk sincronizan user.created/updated a nuestra BD

## Alternativas consideradas y descartadas

**JWT propio sin proveedor.** Es lo que planteaba el Analisis Funcional v1.7
(RF-05 original). Requiere implementar OAuth con Microsoft y Google a mano,
rotacion de tokens, MFA, passkeys y recuperacion de clave. Semanas de trabajo
que no aporta diferenciacion al producto. Descartado en ADR-006.

**Supabase Auth.** La integracion nativa con RLS suena ideal, pero solo sirve
cuando el cliente habla directo con PostgREST. Ambienta tiene FastAPI en el
medio — la ventaja de Supabase nunca se ejerceria. Descartado en ADR-006.

**Firebase Auth.** Sin historia con Postgres, multi-tenancy real exige
Identity Platform, y arrastra a GCP sin aportar nada. Descartado en ADR-006.

**Mantener el header X-Tenant-Id en produccion.** Inseguro por definicion:
cualquiera puede fabricar el header. Descartado por RNF-07 (aislamiento).
