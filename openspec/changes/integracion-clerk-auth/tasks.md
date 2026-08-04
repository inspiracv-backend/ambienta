# Tasks: Integracion de Clerk como proveedor de autenticacion

Plan de implementacion de [`proposal.md`](./proposal.md) / [`design.md`](./design.md).

> **Nada de esto se ejecuta hasta que la propuesta este aprobada**
> (CLAUDE.md §1: solo se implementan features con spec aprobada).

---

## Supuestos

| # | Supuesto | Por que se tomo | Si se rechaza |
|---|---|---|---|
| S-1 | No se usan Organizations de Clerk para mapear tenants | Sub-tenancy por contrato no encaja; reduce lock-in | Se implementa Organizations y se mapea a tenants |
| S-2 | `tenant_id` va en `publicMetadata` del usuario de Clerk y se inyecta como claim custom en el JWT | Es la forma mas directa de tener tenant_id en cada request sin call extra | Se usa un endpoint de lookup o se lee de nuestra BD en cada request |
| S-3 | El DevRoleSwitcher se mantiene como fallback en dev (sin Clerk configurado) | Permite desarrollo local sin cuenta de Clerk | Se elimina completamente y se requiere Clerk siempre |
| S-4 | Los usuarios de seed se crean directo en la BD, sin pasar por Clerk | Son datos de desarrollo, no usuarios reales | Se crean via API de Clerk y se sincronizan por webhook |
| S-5 | El webhook de Clerk crea usuarios en nuestra BD | Evita que la API tenga que buscar en Clerk en cada request | Se usa la API de Clerk para sync manual |

---

## Fase 1 — Backend: validacion JWT y auth.py

- [ ] Instalar dependencias: `python-jose[cryptography]`, `httpx`
- [ ] Crear `apps/api/app/auth.py`:
  - [ ] Funcion `_get_jwks()` con cache en memoria
  - [ ] Funcion `get_current_user()` que valida JWT RS256 y retorna `{user_id, tenant_id}`
  - [ ] `HTTPBearer` con `auto_error=False` para el fallback
- [ ] Actualizar `apps/api/app/deps.py`:
  - [ ] `get_tenant_id()` extrae del JWT cuando `CLERK_JWKS_URL` esta configurado
  - [ ] Fallback al header `X-Tenant-Id` cuando no hay Clerk (desarrollo)
  - [ ] `get_tenant_db()` no cambia (sigue usando `get_tenant_id`)
- [ ] Agregar migracion SQL: `ALTER TABLE users ADD COLUMN clerk_id TEXT UNIQUE`
- [ ] Verificar con curl que un JWT valido pasa y uno invalido da 401
- [ ] Verificar que sin `CLERK_JWKS_URL`, el fallback sigue funcionando

## Fase 2 — Backend: webhook de sincronizacion

- [ ] Crear `apps/api/app/routers/webhooks.py`:
  - [ ] `POST /webhook/clerk` que recibe eventos de Clerk
  - [ ] Verificar firma del webhook con `CLERK_WEBHOOK_SECRET` (svix)
  - [ ] Handler `user.created`: crear usuario en tabla `users`
  - [ ] Handler `user.updated`: actualizar email/nombre
- [ ] Registrar router en `main.py` (sin autenticacion — el webhook se verifica con svix)
- [ ] Testear con Clerk CLI: `clerk webhooks test`

## Fase 3 — Frontend: @clerk/nextjs

- [ ] Instalar `@clerk/nextjs` en `apps/web`
- [ ] Crear `apps/web/middleware.ts` con `clerkMiddleware`:
  - [ ] Rutas publicas: `/login`, `/signup`, `/api/webhook/clerk`
  - [ ] Todo lo demas requiere sesion
- [ ] Envolver `app/layout.tsx` con `<ClerkProvider>`
- [ ] Refactorizar `app/(auth)/login/page.tsx`:
  - [ ] Si `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` existe → renderizar `<SignIn />`
  - [ ] Si no → renderizar DevRoleSwitcher (fallback dev)
- [ ] Crear `app/(auth)/signup/page.tsx` con `<SignUp />`
- [ ] Agregar `<UserButton />` en el sidebar (reemplaza el avatar actual)
- [ ] Agregar variables de entorno de Clerk a `.env.example`
- [ ] Verificar que el middleware redirige a `/login` sin sesion

## Fase 4 — Frontend: api-client con Bearer token

- [ ] Actualizar `RequestOptions` en `api-client.ts`: agregar campo `token`
- [ ] Actualizar `request()`: enviar `Authorization: Bearer <token>` cuando hay token
- [ ] Mantener fallback `X-Tenant-Id` para desarrollo sin Clerk
- [ ] Crear hook `useApiToken()` que usa `useAuth().getToken()` de Clerk
- [ ] Actualizar todos los stores para pasar `token` en las llamadas a `api.*`
- [ ] Manejar 401: redirigir a `/login`
- [ ] Verificar que la carga de datos funciona con JWT real

## Fase 5 — Configuracion SSO (no requiere codigo)

- [ ] Crear cuenta de Clerk (si no existe)
- [ ] Configurar dominio de produccion en Clerk dashboard
- [ ] Configurar Microsoft SSO:
  - [ ] Crear App Registration en Azure / Entra ID
  - [ ] Configurar Redirect URI
  - [ ] Copiar Client ID + Secret a Clerk
- [ ] Configurar Google SSO:
  - [ ] Crear OAuth Client ID en Google Cloud Console
  - [ ] Configurar Redirect URI
  - [ ] Copiar Client ID + Secret a Clerk
- [ ] Testear login con Microsoft
- [ ] Testear login con Google

## Fase 6 — Docker y entorno

- [ ] Agregar variables de Clerk a `docker-compose.yml` (servicio `web` y `api`)
- [ ] Actualizar `.env.example` con todas las variables nuevas
- [ ] Actualizar `docs/development/entornos.md` con instrucciones de Clerk
- [ ] Actualizar `docs/development/setup-local.md`: nota sobre desarrollo sin Clerk
- [ ] Actualizar GitHub Actions CI si es necesario (las variables son secretos)

## Fase 7 — Verificacion

- [ ] Sin Clerk configurado: DevRoleSwitcher funciona, API acepta header X-Tenant-Id
- [ ] Con Clerk configurado: login muestra `<SignIn />`, DevRoleSwitcher desaparece
- [ ] Login con email+password → sesion real → dashboard con datos del tenant
- [ ] Login con Microsoft SSO → misma experiencia
- [ ] Login con Google SSO → misma experiencia
- [ ] Acceder a `/dashboard` sin sesion → redirige a `/login`
- [ ] API con JWT valido → responde correctamente con datos del tenant
- [ ] API con JWT invalido → 401
- [ ] API con JWT de tenant 1 → no ve datos de tenant 2 (RLS)
- [ ] Webhook: crear usuario en Clerk → aparece en tabla `users`
- [ ] El `<UserButton />` muestra nombre y foto del usuario logueado

---

## Orden sugerido

Fase 1 y 3 pueden avanzar en paralelo (backend y frontend son independientes).
Fase 2 depende de Fase 1 (necesita la migracion de `clerk_id`).
Fase 4 depende de Fase 1 + 3 (necesita JWT del frontend y validacion del backend).
Fase 5 se puede hacer en cualquier momento (es configuracion en dashboard).
Fase 6 y 7 al final.

**Estimacion:** cambio grande. Toca `deps.py`, todos los stores del frontend,
el sistema de login, y agrega un modulo nuevo de webhooks. No rompe el modelo
de datos (solo agrega `clerk_id`). El RLS no cambia.

**Dependencias externas:**
- Cuenta de Clerk (gratis para desarrollo)
- App Registration en Azure para Microsoft SSO
- OAuth Client ID en Google Cloud para Google SSO

**Issues de Linear relacionados:**
- ABA-20: Integrar Clerk y validar sus tokens en la API
- ABA-59: Definir como mapear organizations de Clerk a nuestros tenants
- ABA-21: SSO con Microsoft (Entra ID) via Clerk
- ABA-22: SSO con Google via Clerk
