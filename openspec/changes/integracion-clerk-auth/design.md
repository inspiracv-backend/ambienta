# Design: Integracion de Clerk como proveedor de autenticacion

Documento tecnico de [`proposal.md`](./proposal.md).
Fuentes: `apps/api/app/deps.py` (auth actual) · `apps/web/lib/api-client.ts` (cliente HTTP) · `apps/web/components/organisms/DevRoleSwitcher/` (login mock) · Clerk docs (clerk.com/docs).

---

## 1. Las dos capas y por que son dos dependencias distintas

| Capa | Responsabilidad | Paquete | Razon |
|---|---|---|---|
| Frontend | Sesion, proteccion de rutas, componentes de login | `@clerk/nextjs` | Clerk maneja la sesion en el browser, emite el JWT |
| Backend | Validar JWT, extraer claims, alimentar RLS | `python-jose` + `httpx` | Solo lee el JWT firmado; nunca habla con la API de Clerk |

**Por que el backend no usa el SDK de Clerk para Python.** El SDK de Clerk
hace llamadas HTTP a la API de Clerk en cada request para verificar la sesion.
Validar el JWT localmente con la JWKS publica es mas rapido, no depende de la
disponibilidad de Clerk en runtime, y reduce el lock-in a un solo archivo
(`auth.py`). Si se cambia de proveedor, se reescribe ese archivo y nada mas.

**Por que no hay un tercer componente (BFF o API Gateway).** El frontend ya
habla directo con FastAPI. Meter un gateway para insertar el JWT seria agregar
un hop sin ganar nada: `@clerk/nextjs` ya pone el token en el browser, y el
api-client ya sabe agregarlo al header.

---

## 2. Modelo

### 2.1 Cambio en `users` — columna `clerk_id`

```ts
// Agregado a la tabla existente `users`
users {
  // ... campos existentes sin cambio ...
  clerk_id: string | null    // TEXT UNIQUE. null para usuarios de seed (dev)
}
```

**Por que `clerk_id` es nullable.** Los usuarios del seed SQL no existen en
Clerk. Si fuera NOT NULL, el seed de desarrollo no insertaria. El constraint
UNIQUE admite multiples nulls en PostgreSQL, asi que no hay conflicto.

**Por que no se reemplaza `id` por `clerk_id`.** El `id` es UUID y esta
referenciado como FK en 14 tablas (audit_log, action_plans, non_conformities,
etc.). Cambiar la PK de users seria una migracion masiva sin beneficio: basta
con un indice unico en `clerk_id` para hacer lookup O(1) desde el webhook.

### 2.2 Claims del JWT de Clerk

```ts
// Lo que Clerk firma en el JWT (RS256)
ClerkJwtPayload {
  sub: string                // Clerk user ID ("user_2abc...")
  iss: string                // "https://<clerk-domain>"
  exp: number
  iat: number
  nbf: number
  // publicMetadata se inyecta como claims de primer nivel
  // via JWT Template en el dashboard de Clerk
  tenant_id: string          // UUID del tenant en nuestra BD
  ambienta_role?: string     // Opcional, para futuro RBAC
}
```

**Por que `tenant_id` va en un JWT Template y no directo en publicMetadata.**
Clerk no inyecta `publicMetadata` en el JWT por defecto — hay que configurar
un JWT Template que lo mapee a un claim de primer nivel. Si no se configura el
template, el JWT no trae `tenant_id` y la API rechaza con 401. Es un paso
manual en el dashboard de Clerk que hay que documentar.

**Por que no se usa un claim estandar como `org_id`.** Clerk usa `org_id` para
sus Organizations, que decidimos no usar (ver proposal.md, decision
estructural). Usar el mismo nombre causaria confusion cuando Clerk lo rellene
con su propio valor si algun dia se habilitan Organizations por error.

### 2.3 Contrato de `auth.py` — la unica pieza acoplada a Clerk

```ts
// Contrato, no implementacion. Lo que auth.py expone a deps.py.
CurrentUser {
  user_id: string            // El `sub` del JWT (Clerk user ID)
  tenant_id: string          // UUID, extraido del claim `tenant_id`
}

// Dependencia FastAPI
get_current_user(credentials: HTTPBearerToken | null) -> CurrentUser
  // 1. Si no hay credentials y CLERK_JWKS_URL no esta configurado:
  //    → caer al fallback (header X-Tenant-Id)
  // 2. Si no hay credentials y CLERK_JWKS_URL SI esta configurado:
  //    → 401 Unauthorized
  // 3. Si hay credentials:
  //    → validar JWT con JWKS publica (RS256)
  //    → extraer sub y tenant_id
  //    → si faltan claims: 401
  //    → si JWT invalido o expirado: 401
  //    → retornar CurrentUser
```

**Por que `auto_error=False` en el `HTTPBearer`.** Si se deja en `True`
(default), FastAPI responde 403 antes de que nuestro codigo pueda decidir si
aplicar el fallback de desarrollo. Con `False`, la funcion recibe `None` y
decide ella.

**Por que la JWKS se cachea en memoria y no en Redis.** La JWKS publica cambia
cuando Clerk rota sus claves, que es infrecuente (meses). Un cache en memoria
con TTL de 1 hora evita una llamada HTTP por request sin riesgo de servir claves
viejas por mas de una hora. Redis agregaria una dependencia que hoy no existe en
el stack.

### 2.4 Contrato del webhook — sincronizacion Clerk → BD

```ts
// POST /webhook/clerk
// Sin autenticacion JWT — se verifica con svix (firma HMAC del payload)

ClerkWebhookEvent {
  type: 'user.created' | 'user.updated' | 'user.deleted'
  data: {
    id: string                     // Clerk user ID
    email_addresses: { email_address: string }[]
    first_name: string | null
    last_name: string | null
    public_metadata: {
      tenant_id: string            // UUID
      role?: string
    }
  }
}

// Comportamiento por evento:
// user.created → INSERT en users con clerk_id, email, nombre, tenant_id
// user.updated → UPDATE email y nombre en users WHERE clerk_id = data.id
// user.deleted → No se borra: se marca inactivo (soft delete) para audit trail
```

**Por que no se borra el usuario en `user.deleted`.** Los audit logs referencian
`user_id`. Borrar el usuario romperia las FKs o dejaria registros huerfanos.
Se marca `is_active = false` y el sistema deja de permitir login, pero el
historial se conserva.

**Por que el webhook no pasa por autenticacion JWT.** Es Clerk quien llama al
endpoint, no un usuario con sesion. La verificacion es via HMAC con el
`CLERK_WEBHOOK_SECRET` (protocolo svix), que es el estandar de Clerk para
webhooks. El endpoint se registra sin el middleware de auth.

---

## 3. Flujo de autenticacion completo

```
  Usuario                Clerk.com              Next.js              FastAPI           PostgreSQL
    │                       │                     │                    │                   │
    ├── Login ─────────────►│                     │                    │                   │
    │                       ├── JWT (RS256) ─────►│                    │                   │
    │                       │                     │ guarda sesion      │                   │
    │   ◄── Dashboard ──────┤                     │                    │                   │
    │                       │                     │                    │                   │
    ├── GET /api/plants ────┼─────────────────────┤                    │                   │
    │                       │                     ├─ Bearer <JWT> ────►│                   │
    │                       │                     │                    ├─ validar con JWKS  │
    │                       │                     │                    ├─ extraer tenant_id │
    │                       │                     │                    ├─ SET LOCAL ROLE ──►│
    │                       │                     │                    ├─ set_config(tid) ─►│
    │                       │                     │                    │◄── datos filtrados─┤
    │                       │                     │◄── JSON ───────────┤                   │
    │   ◄── render ─────────┤                     │                    │                   │
```

**El unico cambio en el flujo de datos es el origen del `tenant_id`.** Antes
llegaba como header `X-Tenant-Id` sin firmar. Ahora llega como claim dentro de
un JWT firmado con RS256. Todo lo que pasa despues — `SET LOCAL ROLE`,
`set_config`, las 37 politicas de RLS — funciona identico. No hay migracion de
datos, no hay cambio de schema en las tablas de negocio, no hay cambio en los
routers.

---

## 4. Cambios en `deps.py`

```ts
// Antes
get_tenant_id(x_tenant_id: Header) -> UUID
  // Lee el header X-Tenant-Id sin validacion de identidad

// Despues
get_tenant_id(user: CurrentUser = Depends(get_current_user)) -> UUID
  // Extrae tenant_id del JWT validado
  // get_tenant_db() NO cambia: sigue dependiendo de get_tenant_id()
```

**La funcion `get_tenant_db()` no se toca.** Solo cambia de donde viene el UUID
que recibe. El `SET LOCAL ROLE` y el `set_config` siguen exactamente igual.
Esto es deliberado: la capa de RLS no debe saber ni importarle como se
autentico el usuario.

---

## 5. Cambios en `api-client.ts`

```ts
// Contrato del request actualizado
RequestOptions {
  // ... campos existentes ...
  token?: string              // JWT de Clerk. Nuevo.
  tenantId?: string           // Solo para fallback de desarrollo. Existente.
}

// Regla de prioridad en request():
// 1. Si hay token → Authorization: Bearer <token>
// 2. Si no hay token pero hay tenantId → X-Tenant-Id: <tenantId> (dev)
// 3. Si no hay ninguno → la request se envia sin auth (401 en prod)

// Manejo de 401:
// Si la API responde 401 → redirigir a /login
// No reintentar: el token expiro o es invalido, hay que re-autenticar
```

**Por que el token se pasa como parametro y no se lee directo del hook de
Clerk.** El api-client es una funcion pura, no un componente React. No puede
llamar `useAuth()`. El token se obtiene en el store o componente que llama y se
pasa como opcion. Esto mantiene el api-client testeable sin mock de Clerk.

---

## 6. Cambios en el frontend

### 6.1 Middleware de Next.js

```ts
// apps/web/middleware.ts — archivo nuevo
// Usa clerkMiddleware de @clerk/nextjs/server

// Rutas publicas (no requieren sesion):
//   /login, /signup, /api/webhook/clerk

// Todas las demas rutas: auth.protect()
// Si no hay sesion → redirect a /login
```

**Por que se usa `clerkMiddleware` y no `authMiddleware`.** `authMiddleware`
esta deprecado en `@clerk/nextjs` v5+. `clerkMiddleware` con `createRouteMatcher`
es la API actual y soporta proteccion condicional por ruta.

### 6.2 Layout raiz

```ts
// apps/web/app/layout.tsx
// Envolver el children en <ClerkProvider>
// ClerkProvider lee NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY del entorno
// Si la variable no existe, ClerkProvider no inicializa (no rompe)
```

### 6.3 Pagina de login — condicional

```ts
// apps/web/app/(auth)/login/page.tsx
// Si NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY existe:
//   → renderizar <SignIn /> de Clerk con redirect a /dashboard
// Si no existe:
//   → renderizar DevRoleSwitcher (fallback de desarrollo)
```

**Por que la decision es en build-time y no en runtime.** Las variables
`NEXT_PUBLIC_*` se inyectan en el bundle de Next.js durante el build. Verificar
su presencia en el componente es una comparacion con `undefined`, no un fetch.
Esto significa que para cambiar entre Clerk y DevRoleSwitcher hay que rebuildar,
lo cual es aceptable: no es un toggle que cambie en produccion.

### 6.4 `<UserButton />` en el sidebar

```ts
// Reemplaza el avatar estatico actual en el sidebar
// Si Clerk esta configurado: <UserButton /> muestra foto, nombre, y logout
// Si no: se mantiene el avatar actual
```

---

## 7. Stores — como obtienen el token

Hoy los 13 stores llaman `api.plants.list()`, `api.audits.list()`, etc. sin
pasar token. Despues de Clerk, cada llamada necesita el JWT.

```ts
// Patron para cada store:
// 1. En el componente que monta el store, obtener token via useAuth().getToken()
// 2. Pasar token al store como parametro de la funcion de carga
// 3. El store lo pasa a api.* como opts.token

// Alternativa: crear un hook useApiToken() que encapsula useAuth().getToken()
// y lo expone con la misma interfaz que el tenantId actual del DevRoleSwitcher.
// Asi el cambio en cada store es minimo: reemplazar tenantId por token.
```

**Por que no se crea un interceptor global.** Un interceptor en el api-client
necesitaria acceso al token fuera de React. La forma idiomatica de `@clerk/nextjs`
es obtener el token en el componente con `useAuth()` y pasarlo. Forzar un
singleton de token introduce estado global y problemas de refresh.

---

## 8. Variables de entorno

### Frontend (`apps/web`)

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY    # pk_test_... o pk_live_...
NEXT_PUBLIC_CLERK_SIGN_IN_URL        # /login
NEXT_PUBLIC_CLERK_SIGN_UP_URL        # /signup
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL  # /dashboard
```

### Backend (`apps/api`)

```
CLERK_JWKS_URL          # https://<clerk-domain>/.well-known/jwks.json
CLERK_WEBHOOK_SECRET    # whsec_... (para verificar firma de webhooks)
```

**Por que no se usa `CLERK_SECRET_KEY` en el backend.** El secret key es para
llamar a la API de Clerk (crear usuarios, etc.). El backend solo valida JWT con
la JWKS publica y verifica webhooks con el HMAC — no necesita el secret key.
No tenerlo reduce la superficie de ataque si el servidor se compromete.

---

## 9. Configuracion SSO en Clerk

No requiere codigo. Se configura en el dashboard de Clerk:

| Proveedor | Paso | Dato |
|---|---|---|
| Microsoft (Entra ID) | Azure portal → App registrations → New | Redirect URI: `https://<clerk-domain>/v1/oauth_callback` |
| Google | Cloud Console → OAuth client ID | Redirect URI: `https://<clerk-domain>/v1/oauth_callback` |

**La URL de callback es de Clerk, no nuestra.** El usuario autentica en
Microsoft/Google, el callback va a Clerk, y Clerk emite el JWT. Nuestra app
nunca ve el OAuth code ni el access token del IdP.

---

## 10. Riesgos y mitigaciones

| Riesgo | Mitigacion |
|---|---|
| Lock-in con Clerk | Toda la validacion vive en `auth.py` (1 archivo). El backend nunca llama la API de Clerk |
| JWKS no disponible | Cache en memoria con TTL. Si el cache esta vacio y Clerk no responde: 503 (no 401, para distinguir "no autenticado" de "no puedo autenticar") |
| Latencia del webhook | Asincrono. La BD puede tener delay de segundos. El primer request de un usuario recien creado podria llegar antes que el webhook — la API debe manejar el caso con 403 + mensaje explicito |
| Desarrollo sin Clerk | Fallback completo: DevRoleSwitcher + header X-Tenant-Id. Activado por ausencia de `CLERK_PUBLISHABLE_KEY` |
| Microsoft SSO falla con tenants restrictivos | Verificar con cuenta real antes de prometer (pendiente ADR-006) |
| JWT expira durante sesion larga | `@clerk/nextjs` renueva el token automaticamente. El api-client redirige a /login si recibe 401 |

---

## 11. Lo que este diseno deliberadamente no resuelve

- **RBAC granular.** Los 39 permisos siguen en nuestra BD. Clerk solo dice
  "este usuario es quien dice ser" — nunca "este usuario puede hacer X". El
  RBAC va en la spec de `sistema-actores-roles-rbac`.
- **Flujo de Cliente Invitado.** El acceso por link especial + RUT + clave
  dinamica (RF-01, RF-02, RF-07) es un flujo custom que no pasa por Clerk.
  Spec separada, ABA-23.
- **MFA configurable por tenant.** Clerk trae MFA, pero decidir si cada tenant
  puede hacerlo obligatorio para sus usuarios es logica nuestra. Post-MVP.
- **Signup publico.** La propuesta deja abierta la decision de si se permite
  self-signup o solo invitacion (decision abierta #4 en proposal.md). Este
  diseno soporta ambas opciones sin cambio de schema.
- **Migracion de usuarios reales.** No hay: los del seed son de desarrollo.
  Si se necesita onboarding masivo, sera un script separado.
