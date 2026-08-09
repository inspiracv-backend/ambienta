# Tasks: Integracion de Clerk como proveedor de autenticacion

Plan de implementacion de [`proposal.md`](./proposal.md) / [`design.md`](./design.md).

> **Nada de esto se ejecuta hasta que la propuesta este aprobada**
> (CLAUDE.md §1: solo se implementan features con spec aprobada).

---

## Supuestos vigentes

| # | Supuesto | Por que se tomo | Si se rechaza |
|---|---|---|---|
| S-1 | No se usan Organizations de Clerk para mapear tenants | Sub-tenancy por contrato (RF-65, RF-66) no encaja en el modelo plano de Organizations; reduce lock-in | Se implementa Organizations, se mapean a tenants, y se aceptan las limitaciones de sub-tenancy |
| S-2 | `tenant_id` se inyecta como claim de primer nivel en el JWT via JWT Template de Clerk | Es la unica forma de tener `tenant_id` en cada request sin call extra a la API de Clerk | Se lee `publicMetadata` del JWT directamente (requiere que Clerk lo incluya sin template) o se hace un lookup a nuestra BD en cada request |
| S-3 | El backend valida JWT con JWKS publica, no con el SDK de Clerk para Python | Elimina dependencia de Clerk en runtime; la JWKS se cachea y no requiere call HTTP por request | Se usa `clerk-backend-api` de Python; cada request valida contra la API de Clerk (mas lento, mas acoplado) |
| S-4 | El DevRoleSwitcher se mantiene como fallback en dev sin Clerk | Permite desarrollo local sin cuenta de Clerk; activado por ausencia de `CLERK_PUBLISHABLE_KEY` | Se elimina y todo desarrollador necesita cuenta de Clerk desde el dia uno |
| S-5 | El webhook de Clerk crea/actualiza usuarios en nuestra BD | La API nunca llama a Clerk; toda la info del usuario esta en nuestra BD | Se consulta la API de Clerk en cada request para obtener datos del usuario (lento, acoplado) |

## Supuestos a confirmar con el equipo

| # | Supuesto | Que falta para confirmarlo | Impacto si se rechaza |
|---|---|---|---|
| S-6 | `tenant_id` va en `publicMetadata` y se mapea con JWT Template | Verificar en el dashboard de Clerk que el JWT Template soporta mapear `publicMetadata.tenant_id` → claim `tenant_id` | Si no soporta el mapeo, hay que usar un campo de `unsafeMetadata` o un claim custom de otra forma; cambia la configuracion, no el codigo |
| S-7 | Los usuarios de seed se crean directo en la BD, sin pasar por Clerk | Es el mecanismo actual; Clerk no esta involucrado en desarrollo | Si se quiere que los devs usen Clerk desde el dia uno, hay que crear usuarios de prueba en Clerk y sincronizarlos por webhook |
| S-8 | No se usa `CLERK_SECRET_KEY` en el backend | El backend solo valida JWT (JWKS publica) y verifica webhooks (HMAC). No llama la API de Clerk | Si se necesita crear usuarios desde el backend (ej: Admin Empresa invita), se necesita el secret key |
| S-9 | Se deshabilita el signup publico en Clerk | Hoy el Admin Empresa registra usuarios (RF-03); self-signup no tiene flujo definido | Si se permite, hay que decidir que pasa con un usuario que se registra sin tenant asignado |

---

## Fase 0 — Prerequisitos fuera de este modulo

Sin esto, las fases siguientes se construyen sobre supuestos.

- [ ] **Crear cuenta de Clerk** (gratis para desarrollo). Obtener `PUBLISHABLE_KEY`, dominio y JWKS URL
- [ ] **Configurar JWT Template** en el dashboard de Clerk para inyectar `publicMetadata.tenant_id` como claim `tenant_id` en el JWT. Verificar que el JWT resultante trae el claim
- [ ] **Verificar la calidad del SSO con Microsoft/Entra ID** con una cuenta real de Azure. ADR-006 lo dejo como pendiente. Si falla, Microsoft SSO se pospone y no bloquea el resto
- [ ] **Decidir si se deshabilita signup publico** en Clerk (ver supuesto S-9 y decision abierta #4 de la propuesta)

## Fase 1 — Backend: modulo `auth.py` y validacion JWT

> **Completada 04-ago-2026.** Rama `feat/clerk-auth-fase1-backend`.
> 17 tests pasando, verificados con mutacion sobre la propiedad de seguridad.

- [x] Instalar dependencias: `python-jose[cryptography]`, `httpx`
- [x] Crear `apps/api/app/auth.py` con el contrato de §2.3 del design:
  - [x] `_get_jwks()` con cache en memoria y TTL de 1 hora
  - [x] `get_current_user()` que valida JWT RS256 y retorna `CurrentUser`
  - [x] `HTTPBearer(auto_error=False)` para permitir el fallback
  - [x] Si JWKS no disponible y cache vacio: 503 (no 401)
- [x] Actualizar `apps/api/app/deps.py`:
  - [x] `get_tenant_id()` pasa de leer header a depender de `get_current_user()`
  - [x] Si `CLERK_JWKS_URL` no esta configurado: fallback al header `X-Tenant-Id`
  - [x] `get_tenant_db()` **no cambia** (sigue usando `get_tenant_id()`)
- [x] Tests:
  - [x] JWT valido con claims completos → retorna `CurrentUser` correcto
  - [x] JWT expirado → 401
  - [x] JWT sin `tenant_id` en claims → 401
  - [x] JWT con firma invalida → 401
  - [x] Sin JWT y sin CLERK_JWKS_URL → fallback a header (desarrollo)
  - [x] Sin JWT y con CLERK_JWKS_URL → 401 (produccion)

### Agregado durante la implementacion (no estaba en la spec)

- [x] `CLERK_ISSUER`: se valida el claim `iss`. Sin esto, un JWT de **otra**
      instancia de Clerk pasaba la verificacion de firma si compartia la JWKS
      publica. Test: `test_token_de_otro_emisor_da_401`
- [x] Fallback a JWKS vencida cuando Clerk no responde. Rechazar a todos los
      usuarios porque el CDN de Clerk parpadeo es peor que el riesgo que cubre
      el TTL. Test: `test_si_clerk_cae_se_usa_el_cache_vencido`
- [x] `user_id` vacio en modo desarrollo, en vez de inventar una identidad.
      Cualquier codigo que dependa de saber quien es el usuario falla visible
- [x] Infraestructura de tests para la API (`pytest.ini`, `tests/`,
      `requirements-dev.txt`) — no existia ninguna
- [x] `.gitignore` de Python: habia **25 archivos `.pyc` commiteados** al repo

## Fase 2 — Backend: migracion SQL y webhook

> **Completada 05-ago-2026.** Rama `feat/clerk-auth-fase2-webhook`.
> 16 tests nuevos (33 en total). Verificado contra Postgres real.

- [x] Migracion `db/04_clerk_auth.sql`: `clerk_id text` + constraint UNIQUE
- [x] ~~`CREATE INDEX idx_users_clerk_id`~~ → **innecesario**: el UNIQUE ya crea
      su indice. Agregar otro sobre la misma columna duplica escrituras sin
      acelerar ninguna lectura
- [x] Crear `apps/api/app/routers/webhooks.py`:
  - [x] `POST /api/v1/webhooks/clerk` sin autenticacion JWT
  - [x] Verificar firma HMAC con `CLERK_WEBHOOK_SECRET` (libreria `svix`)
  - [x] `user.created` → INSERT en `users`
  - [x] `user.updated` → UPDATE email y nombre WHERE `clerk_id`
  - [x] `user.deleted` → `status = 'disabled'` (ver correccion en design.md:
        `is_active` no existe)
  - [x] Payload invalido o firma incorrecta → 400
- [x] Registrar router en `main.py` sin dependencia de auth
- [x] Tests:
  - [x] Firma valida + `user.created` → usuario creado
  - [x] Firma de otro secreto → 400
  - [x] Sin cabeceras de firma → 400
  - [x] Cuerpo alterado despues de firmar → 400
  - [x] Evento desconocido → 200 (ignorar, no fallar)

### Agregado durante la implementacion (no estaba en la spec)

- [x] **`services/clerk_sync.py` separado del router.** Permite probar la
      traduccion de eventos sin fabricar firmas HTTP
- [x] **Adopcion por email.** Si ya existe un usuario con ese correo pero sin
      `clerk_id`, se le pega el id en vez de crear un duplicado. Sin esto, la
      primera entrada de alguien que ya estaba en la base violaba el UNIQUE de
      `email` y el webhook fallaba en loop
- [x] **El tenant y el rol no se pisan en `user.updated`.** Un cambio de foto en
      Clerk no debe revertir lo que un admin configuro en Ambienta
- [x] **Se toma el correo marcado como primario**, no el primero del arreglo:
      con dos correos el orden no dice cual usa la persona
- [x] **Rol validado contra el CHECK de `user_type`.** Un rol inventado desde el
      dashboard de Clerk cae al default en vez de que lo rechace la base
- [x] **Nombre vacio cae al correo.** Entrar por SSO sin perfil deja el nombre
      en blanco y la columna es NOT NULL
- [x] **503 si falta `CLERK_WEBHOOK_SECRET`**, no 401: el que llama no tiene la
      culpa de que falte la configuracion
- [x] **400 y no 500 si el payload viene incompleto.** Es autentico (venia
      firmado) pero le falta algo que solo se arregla en el dashboard de Clerk;
      con 5xx, Clerk reintentaria para siempre un payload que no va a mejorar

## Fase 3 — Frontend: `@clerk/nextjs` y proteccion de rutas

- [x] Instalar `@clerk/nextjs` en `apps/web` (v6.39.6 + `@clerk/localizations`;
      obligo a subir Next 14.2.15 → 14.2.35, ver design §6.0)
- [x] Crear `apps/web/middleware.ts`:
  - [x] `clerkMiddleware` con `createRouteMatcher`
  - [x] Rutas publicas: `/login(.*)`, `/signup(.*)`, `/acceso-invitado(.*)`,
        `/crear-ticket(.*)`. **No** `/api/webhook/clerk`: ese endpoint vive en
        FastAPI (Fase 2), no en Next, asi que el matcher de acá no lo alcanza
  - [x] Todo lo demas: `auth.protect()` → redirect a `/login`
  - [x] Sin llave el middleware deja pasar todo: `clerkMiddleware()` tambien
        falla sin `publishableKey`, no se puede llamar incondicionalmente
- [x] Envolver `app/layout.tsx` con `<ClerkProvider>` — via `AuthProvider`,
      que lo hace condicional (design §6.2 decia que sin llave no rompia; si
      rompe, corregido)
- [x] Refactorizar `app/(auth)/login/page.tsx`:
  - [x] Si `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` → `<SignIn />` con redirect a `/dashboard`
  - [x] Si no → `<DevRoleSwitcher />` (fallback dev)
- [x] Crear `app/(auth)/signup/page.tsx` con `<SignUp />`
- [x] Reemplazar avatar estatico por `<UserButton />` (condicional a Clerk).
      Estaba en `AppHeader`, no en el sidebar; se reemplazo el boton de cerrar
      sesion, que con proveedor real tiene que invalidar la sesion en Clerk
- [ ] Verificar:
  - [ ] Sin sesion + ruta protegida → redirect a `/login` — **bloqueado**: no
        hay cuenta de Clerk todavia (decision abierta del equipo)
  - [ ] Con sesion → acceso normal — **bloqueado**, mismo motivo
  - [x] Sin `CLERK_PUBLISHABLE_KEY` → DevRoleSwitcher funciona como antes
        (tsc 0, lint 0, 190 tests, build 0, tablero al 40% en el navegador)

## Fase 4 — Frontend: api-client con Bearer token

- [ ] Actualizar `RequestOptions` en `api-client.ts`: agregar campo `token`
- [ ] Actualizar `request()`: logica de prioridad (token > tenantId > sin auth)
- [ ] Manejo de 401: redirect a `/login`, sin reintento
- [ ] Crear hook `useApiToken()` que encapsula `useAuth().getToken()`
- [ ] Actualizar los 13 stores para pasar `token` en las llamadas:
  - [ ] `plants-store`
  - [ ] `areas-store`
  - [ ] `declarations-store`
  - [ ] `audits-store`
  - [ ] `non-conformities-store`
  - [ ] `action-plans-store`
  - [ ] `risks-store`
  - [ ] `documents-store`
  - [ ] `obligations-store`
  - [ ] `normativas-store`
  - [ ] `users-store`
  - [ ] `kpis-store`
  - [ ] `notifications-store`
- [ ] Verificar que la carga de datos funciona end-to-end con JWT real

## Fase 5 — Configuracion SSO (sin codigo)

- [ ] Configurar Microsoft SSO en Clerk:
  - [ ] App Registration en Azure / Entra ID
  - [ ] Redirect URI apuntando a Clerk
  - [ ] Client ID + Secret copiados a Clerk
  - [ ] Test end-to-end con cuenta real
- [ ] Configurar Google SSO en Clerk:
  - [ ] OAuth Client ID en Google Cloud Console
  - [ ] Redirect URI apuntando a Clerk
  - [ ] Client ID + Secret copiados a Clerk
  - [ ] Test end-to-end con cuenta real

## Fase 6 — Entorno y documentacion

- [ ] Agregar variables de Clerk a `docker-compose.yml` (servicios `web` y `api`)
- [ ] Actualizar `.env.example`:
  - [ ] Reemplazar seccion de `JWT_SECRET` por variables de Clerk
  - [ ] Reemplazar seccion de OAuth directo (MICROSOFT_CLIENT_ID, etc.) por nota de que SSO se configura en Clerk
  - [ ] 6 variables nuevas con placeholders y comentarios
- [ ] Actualizar `docs/development/setup-local.md`: instrucciones de desarrollo con y sin Clerk
- [ ] Actualizar `docs/development/entornos.md`: variables de Clerk en la tabla de entornos
- [ ] GitHub Actions CI: las variables de Clerk son secretos; CI corre con fallback (sin Clerk)

## Fase 7 — Verificacion end-to-end

- [ ] **Sin Clerk configurado** (desarrollo):
  - [ ] DevRoleSwitcher funciona
  - [ ] API acepta header `X-Tenant-Id`
  - [ ] Todos los flujos existentes siguen funcionando
- [ ] **Con Clerk configurado** (staging/produccion):
  - [ ] Login muestra `<SignIn />`, DevRoleSwitcher no aparece
  - [ ] Login con email+password → sesion real → dashboard con datos del tenant
  - [ ] Login con Microsoft SSO → misma experiencia
  - [ ] Login con Google SSO → misma experiencia
  - [ ] `/dashboard` sin sesion → redirect a `/login`
  - [ ] API con JWT valido → datos correctos del tenant
  - [ ] API con JWT invalido → 401
  - [ ] API con JWT de tenant 1 → no ve datos de tenant 2 (RLS verificado)
  - [ ] Webhook `user.created` → usuario aparece en tabla `users`
  - [ ] `<UserButton />` muestra nombre y foto del usuario
  - [ ] Token expirado durante sesion → Clerk lo renueva automaticamente
  - [ ] Logout → sesion destruida, redirect a `/login`

---

## Orden sugerido

Fase 0 primero y de verdad: sin la cuenta de Clerk y el JWT Template
configurado, no se puede validar ningun JWT en las fases siguientes. La
verificacion de Microsoft SSO tambien va aqui para saber si se puede prometer.

Fase 1 y 3 pueden avanzar en paralelo: el backend (validacion JWT) y el
frontend (middleware + login) son independientes entre si.

Fase 2 depende de Fase 1: el webhook necesita que `clerk_id` exista en la tabla
`users`, y el endpoint se registra en el mismo `main.py` que ya tiene la
dependencia de auth.

Fase 4 depende de Fase 1 + 3: necesita que el frontend tenga el JWT (Fase 3) y
que el backend lo valide (Fase 1).

Fase 5 se puede hacer en cualquier momento: es configuracion en dashboards
externos.

Fase 6 y 7 al final: configuracion de entorno y verificacion.

**Estimacion de alcance:** cambio medio-grande. Toca `deps.py`, el api-client,
todos los stores del frontend, el sistema de login, y agrega un modulo nuevo de
webhooks. **No toca el modelo de datos de negocio** (solo agrega `clerk_id` a
`users`). El RLS no cambia. Los 93 endpoints existentes no cambian de firma —
solo cambia de donde viene el `tenant_id` que ya reciben.

**Dependencias externas:**
- Cuenta de Clerk (gratis para desarrollo, plan Pro para produccion)
- App Registration en Azure / Entra ID para Microsoft SSO
- OAuth Client ID en Google Cloud para Google SSO

**Issues de Linear relacionados:**
- ABA-20: Integrar Clerk y validar sus tokens en la API
- ABA-59: Definir como mapear organizations de Clerk a nuestros tenants
- ABA-21: SSO con Microsoft (Entra ID) via Clerk
- ABA-22: SSO con Google via Clerk
