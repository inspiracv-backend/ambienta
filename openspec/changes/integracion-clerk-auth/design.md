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

**Configurar el template no alcanza: hay que pedirlo por nombre**
(comprobado el 10-ago-2026 contra la instancia real, y costo una tarde). Hay
dos tokens distintos y solo uno sirve:

| Llamada | Claims |
|---|---|
| `getToken()` | `azp, exp, fva, iat, iss, nbf, sid, sts, sub, v` — **sin `tenant_id`** |
| `getToken({ template: 'default' })` | `azp, exp, iat, iss, jti, nbf, sub, **tenant_id**` |

El primero es el token de sesion estandar, que ignora los JWT Templates. Que
el template se llame `default` **no** lo vuelve el predeterminado: es solo su
nombre. Con `getToken()` pelado, `auth.py` registra
`JWT de Clerk sin claims requeridos (sub=True, tenant_id=False)` y devuelve
401 en todos los endpoints — el sintoma es una app que autentica bien y no
muestra ningun dato.

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
Se marca inactivo y el sistema deja de permitir login, pero el historial se
conserva.

**Correccion (04-ago-2026, durante Fase 1).** La v1 de este diseno decia
`is_active = false`. Esa columna **no existe**. La tabla `users` real
(`db/01_schema.sql:158`) tiene:

```sql
status varchar(24) NOT NULL DEFAULT 'invited'
       CHECK (status IN ('invited','active','blocked','disabled')),
deleted_at timestamptz    -- del SoftDeleteMixin
```

Por lo tanto `user.deleted` mapea a `status = 'disabled'`, no a un booleano
nuevo. Se usa `status` y no `deleted_at` porque son cosas distintas: `disabled`
es "existe pero no puede entrar" (que es lo que significa borrar en Clerk),
mientras que `deleted_at` es baja logica del registro completo. Un usuario
eliminado en Clerk sigue siendo un registro vivo en nuestra BD — solo perdio
su medio de autenticacion.

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
`set_config`, las politicas de RLS — funciona identico. No hay migracion de
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

> **Corregido el 10-ago-2026 contra la instancia real.** Este apartado decia
> que el token viajaba como parametro en `RequestOptions`. Es inviable: ver
> abajo. Se deja lo que decia porque explica por que el codigo no se parece a
> las tareas de la Fase 4.

```ts
// Lo que se registra es un GETTER, una sola vez, no un token por llamada.
registrarProveedorDeToken(() => getToken({ template: CLERK_JWT_TEMPLATE }))

// Regla de prioridad en request():
// 1. Si el getter devuelve token → Authorization: Bearer <token>
// 2. Si no hay token pero hay tenantId → X-Tenant-Id: <tenantId> (dev)
// 3. Si no hay ninguno → la request sale sin auth (401 con Clerk activo)
```

**Por que un getter y no un parametro `token`.** El diseño original proponia
pasar el token en cada llamada. No funciona: **el JWT Template emite tokens de
60 segundos** (verificado: `exp - iat = 60`). Un string capturado en un store y
pasado como opcion queda vencido al minuto de tener la pantalla abierta, y
habria que re-obtenerlo antes de cada request en los 20 sitios de llamada.
`getToken()` de Clerk ya renueva por dentro, asi que lo que hay que conservar
es **la funcion**, registrada una vez desde dentro del provider.

Efecto secundario bueno: las 20 llamadas existentes no se tocan. El api-client
sigue siendo testeable sin mock de Clerk — sin proveedor registrado se comporta
igual que antes.

**Hay una carrera y esta cerrada explicitamente.** Los stores piden datos en un
`useEffect` y el puente registra el token en otro; Clerk arranca con
`isLoaded: false`. Sin sincronizacion, el primer request sale sin token, cobra
401 y el store cae a los mocks para siempre. `request()` espera una promesa que
se cumple cuando la identidad quedo resuelta — con getter o con `null`, ambas
son respuestas definitivas.

**El 401 no siempre manda al login.** Solo se redirige si Clerk dice que ya no
hay sesion. Un 401 con sesion viva de Clerk significa template mal configurado,
y mandar a `/login` ahi arma un bucle: `<SignIn />` ve al usuario dentro y lo
devuelve al tablero. En ese caso se registra el error y se corta.

---

## 6. Cambios en el frontend

### 6.0 Version de `@clerk/nextjs` y el salto de Next (decidido 09-ago-2026)

El diseño decia "instalar `@clerk/nextjs`" sin version, dando por hecho que
cualquiera sirve. No es asi: el paquete declara `next` como peer dependency y
el proyecto esta en **14.2.15**.

| Version de Clerk | `next` que exige | ¿Sirve hoy? |
|---|---|---|
| 7.7.1 (ultima) | `^15.2.8 \|\| ^16` | No. Exigiria migrar a Next 15 |
| 6.39.6 | `^13.5.7 \|\| ^14.2.25 \|\| ^15.2.3 \|\| ^16` | Casi: falta un parche |
| 5.7.6 | `^13.5.4 \|\| ^14.0.3` | Si, pero es de 2024 |

**Decision: subir Next a 14.2.35 y usar Clerk 6.x.**

Es un salto de **parche dentro del mismo minor** (14.2.15 → 14.2.35), no un
cambio de major: no hay migracion de App Router ni de React. A cambio se entra
a una linea de Clerk mantenida en vez de quedarse en la de hace un año.

Lo que se descarta y por que: **Clerk 5** funcionaria sin tocar nada, pero
adoptar hoy una dependencia de autenticacion que ya lleva un año sin ser la
linea principal significa migrar igual dentro de poco, con la diferencia de que
para entonces habra codigo escrito encima. **Next 15** es la otra punta: un
major con cambios en el App Router, y este cambio es de autenticacion, no de
framework.

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

**`auth.protect()` pelado NO manda a `/login`** (10-ago-2026). Manda al
Account Portal alojado de Clerk (`<slug>.accounts.dev/sign-in`), y en
desarrollo el navegador bloquea ese salto por cambio de origen:

```
Unsafe attempt to load URL https://rapid-octopus-10.accounts.dev/sign-in
from frame with URL http://localhost:3000/dashboard.
Domains, protocols and ports must match.
```

El resultado es un bucle entre el portal y `/dashboard` que termina en
`Throttling navigation to prevent the browser from hanging`. Hay que pasar
`unauthenticatedUrl` explicito. Poner `signInUrl` en el `ClerkProvider` **no
alcanza**: el provider vive en el cliente y el middleware corre antes.

**`/login` tiene que ser ruta catch-all.** `<SignIn />` navega a subrutas
propias (`/login/factor-two`, `/login/SignIn_clerk_catchall_check_<ts>`); con
`app/(auth)/login/page.tsx` esas dan 404 y Clerk aborta con
"The `<SignIn/>` component is not configured correctly". El archivo va en
`app/(auth)/login/[[...rest]]/page.tsx`.

### 6.2 Layout raiz — el provider va condicionado

**Correccion (09-ago-2026).** La v1 de este diseño decia que sin la variable
"ClerkProvider no inicializa (no rompe)". **Es falso.** Clerk lanza
`Missing publishableKey` y la aplicacion no monta.

Eso invalidaria el modo de desarrollo sin cuenta, que es el punto de todo el
fallback: un desarrollador que clona el repo y corre `docker compose up` no
tiene cuenta de Clerk, y con el provider incondicional no veria ni el login.

```ts
// apps/web/components/organisms/AuthProvider — componente nuevo
// Si hay NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY -> <ClerkProvider>{children}</ClerkProvider>
// Si no                                    -> {children} tal cual
```

Un componente y no un `if` suelto en el layout, porque el layout es un Server
Component y `ClerkProvider` necesita ser cliente.

**Lo mismo vale para el middleware.** `clerkMiddleware()` sin llave falla
igual, asi que `middleware.ts` deja pasar la peticion sin tocarla cuando la
variable no esta. Sin proveedor no hay sesion que proteger, y las pantallas
siguen cubiertas por los guards que ya existen en el cliente.

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

> **Invertido el 10-ago-2026.** Este apartado descartaba el interceptor global
> y proponia pasar el token store por store. Se implemento al reves, y con
> razon. Se deja el texto original abajo porque el argumento que lo tumba es
> util.

```ts
// Lo implementado: ningun store cambia.
// 1. <ClerkApiBridge/>, dentro del ClerkProvider, registra el getter una vez
// 2. request() lo consulta en cada llamada y renueva solo
```

**Por que se invirtio.** El argumento contra el interceptor era "problemas de
refresh". Es exactamente al reves: **los tokens duran 60 segundos**, asi que
pasarlos como valor es lo que crea el problema de refresh — cada store tendria
que re-pedirlo antes de cada llamada, y basta olvidarlo en uno para tener un
401 intermitente imposible de reproducir. El getter renueva por dentro.

Sobre "necesitaria acceso al token fuera de React": correcto, y por eso el
puente **si** es un componente React —vive bajo el `ClerkProvider` y usa
`useAuth()` como manda la libreria— que solo deja registrada la funcion. No
hay token en estado global; hay una referencia a `getToken`.

Lo que si cambio en `users-store`: con Clerk **no se enumeran tenants**. El
JWT ya acota `/users/` por RLS, y recorrer `/tenants/` pediria N veces la
misma lista porque la API ignora `X-Tenant-Id` cuando hay token. Sin Clerk se
sigue enumerando, que es lo que permite cambiar de rol con el DevRoleSwitcher.

<details><summary>Texto original (descartado)</summary>

```ts
// Patron para cada store:
// 1. En el componente que monta el store, obtener token via useAuth().getToken()
// 2. Pasar token al store como parametro de la funcion de carga
// 3. El store lo pasa a api.* como opts.token
```

**Por que no se crea un interceptor global.** Un interceptor en el api-client
necesitaria acceso al token fuera de React. La forma idiomatica de `@clerk/nextjs`
es obtener el token en el componente con `useAuth()` y pasarlo. Forzar un
singleton de token introduce estado global y problemas de refresh.

</details>

### 7.1 De que Clerk conozca a alguien no se sigue que Ambienta lo conozca

`useSession().user` sale de emparejar el **email** de Clerk contra `users`.
Se usa el email y no `clerk_id` porque esa columna solo se llena cuando el
webhook procesa el alta, y una persona que ya estaba en la base no lo tiene —
es el mismo criterio de `clerk_sync.adoptar_por_email`.

**En desarrollo local el webhook no corre.** Clerk no puede alcanzar
`localhost:8000`, asi que cada usuario creado en el dashboard queda sin fila
en la base y entra a una app vacia. Hasta que haya un tunel (ngrok) o un
entorno desplegado, el alta local es un `INSERT` a mano:

```sql
INSERT INTO users (tenant_id, email, full_name, user_type, status)
VALUES ('<uuid-del-tenant>', '<email en Clerk>', '<nombre>', 'tenant_admin', 'active');
```

El `tenant_id` de esa fila y el del `publicMetadata` en Clerk **tienen que
coincidir**: uno decide que datos ve, el otro quien es.

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

## 11. Verificacion de las decisiones

Cada decision de arriba tiene una prueba que la sostiene. Sin esto, un diseno
es una opinion.

### Que se probo por mutacion

Un test que no falla cuando se rompe lo que dice proteger no prueba nada. Las
dos propiedades que justifican este cambio se verificaron rompiendolas a
proposito:

| Mutacion aplicada | Resultado |
|---|---|
| Que `get_current_user()` confiara en el header `X-Tenant-Id` aun con Clerk activo | Fallo `test_tenant_id_sale_del_token_no_del_header`. Es la propiedad que justifica todo el cambio |
| Reemplazar `Webhook(...).verify(...)` por un `json.loads()` directo | Fallaron los tres tests de firma: otro secreto, sin cabeceras y cuerpo alterado |

La segunda importa especialmente: sin verificacion de firma, cualquiera que
conozca la URL del webhook puede crear usuarios en cualquier empresa.

### Contra Postgres real (05-ago-2026)

Los tests usan un doble de sesion, asi que no cubren el motor SQL. El ciclo
completo se corrio contra la base:

| Que | Resultado |
|---|---|
| Migracion `04_clerk_auth.sql` aplicada dos veces | Idempotente, sin error |
| `uq_users_clerk_id` | Creado |
| Los 5 usuarios del seed | Intactos, con `clerk_id` NULL |
| `user.created` | Fila creada con correo, nombre, tipo y estado correctos |
| `user.updated` | Nombre actualizado, empresa y rol sin tocar |
| `user.deleted` | `status = 'disabled'` y **la fila se conserva** |
| Reenviar el mismo `user.created` | Actualiza en vez de duplicar: sigue habiendo 1 fila |

La ultima linea es la que prueba la adopcion por correo: sin ella, la segunda
llegada del mismo evento violaria el UNIQUE de `email` y el webhook quedaria
fallando en bucle.

### Cobertura

57 tests en total sobre el backend de auth: 17 de validacion de credenciales y
16 de webhooks, mas los 24 heredados del tablero. `ruff` limpio sobre los
archivos de esta capacidad.

Ninguno necesita cuenta de Clerk: las llaves y las firmas se generan en los
propios tests. Eso es deliberado — un test que exige una cuenta de un proveedor
externo deja de correr en CI el dia que alguien rota una credencial.

## 12. Lo que este diseno deliberadamente no resuelve

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
