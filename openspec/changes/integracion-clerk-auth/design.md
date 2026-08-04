# Design: Integracion de Clerk como proveedor de autenticacion

Documento tecnico de [`proposal.md`](./proposal.md).

---

## 1. Arquitectura general

```
                    ┌──────────────┐
                    │   Clerk.com  │
                    │  (hosted)    │
                    └──────┬───────┘
                           │ JWT (RS256)
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼─────┐      ┌────▼─────┐      ┌─────▼──────┐
   │  Next.js  │      │  FastAPI  │      │  Webhooks  │
   │ @clerk/   │ ───► │  deps.py  │      │  /webhook  │
   │ nextjs    │ JWT  │  validate │      │  /clerk    │
   └──────────┘      └────┬──────┘      └─────┬──────┘
                          │                    │
                     SET LOCAL             INSERT/UPDATE
                     tenant_id             users table
                          │                    │
                    ┌─────▼────────────────────▼──────┐
                    │        PostgreSQL + RLS          │
                    └─────────────────────────────────┘
```

**Flujo:**
1. Usuario hace login via Clerk (email, Google o Microsoft SSO)
2. Clerk emite JWT con claims custom (tenant_id en publicMetadata)
3. Frontend envia JWT en header `Authorization: Bearer <token>`
4. FastAPI valida JWT con JWKS publica de Clerk
5. Extrae `user_id` (sub) y `tenant_id` (claim custom)
6. Ejecuta `SET LOCAL ROLE ambienta_app` + `set_config('ambienta.tenant_id', ...)`
7. RLS filtra automaticamente por tenant

---

## 2. Frontend: @clerk/nextjs

### 2.1 Instalacion

```bash
npm install @clerk/nextjs --workspace @ambienta/web
```

### 2.2 Provider (layout.tsx)

```tsx
// apps/web/app/layout.tsx
import { ClerkProvider } from '@clerk/nextjs';

export default function RootLayout({ children }) {
  return (
    <ClerkProvider>
      <html lang="es">
        <body>{children}</body>
      </html>
    </ClerkProvider>
  );
}
```

### 2.3 Middleware (proteccion de rutas)

```typescript
// apps/web/middleware.ts
import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';

const isPublicRoute = createRouteMatcher([
  '/login(.*)',
  '/signup(.*)',
  '/api/webhook/clerk(.*)',
]);

export default clerkMiddleware(async (auth, req) => {
  if (!isPublicRoute(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: ['/((?!_next|[^?]*\\.(?:html?|css|js|jpe?g|png|gif|svg|ico)).*)'],
};
```

### 2.4 Pagina de login

```tsx
// apps/web/app/(auth)/login/page.tsx
import { SignIn } from '@clerk/nextjs';

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignIn
        appearance={{
          elements: {
            rootBox: 'mx-auto',
          },
        }}
        redirectUrl="/dashboard"
      />
    </div>
  );
}
```

### 2.5 api-client con JWT

```typescript
// apps/web/lib/api-client.ts
import { useAuth } from '@clerk/nextjs';

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  // JWT de Clerk como Authorization header
  if (opts.token) {
    headers['Authorization'] = `Bearer ${opts.token}`;
  }
  // Fallback para desarrollo sin Clerk
  if (opts.tenantId && !opts.token) {
    headers['X-Tenant-Id'] = opts.tenantId;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    signal: opts.signal,
  });

  if (res.status === 401) {
    // Token expirado o invalido — forzar re-login
    window.location.href = '/login';
    throw new ApiError(401, 'Unauthorized', null);
  }

  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, res.statusText, detail);
  }

  return res.json() as Promise<T>;
}
```

### 2.6 DevRoleSwitcher como fallback

```tsx
// apps/web/app/(auth)/login/page.tsx
import { SignIn } from '@clerk/nextjs';

const CLERK_CONFIGURED = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default function LoginPage() {
  if (!CLERK_CONFIGURED) {
    // Fallback: DevRoleSwitcher para desarrollo local sin Clerk
    return <DevRoleSwitcher />;
  }
  return <SignIn redirectUrl="/dashboard" />;
}
```

---

## 3. Backend: validacion JWT en FastAPI

### 3.1 Dependencia de validacion

```python
# apps/api/app/auth.py
import httpx
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

CLERK_JWKS_URL = os.environ.get("CLERK_JWKS_URL")
_jwks_cache: dict | None = None
_bearer = HTTPBearer(auto_error=False)


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(CLERK_JWKS_URL)
            _jwks_cache = resp.json()
    return _jwks_cache


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Valida JWT de Clerk y retorna {user_id, tenant_id}."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        jwks = await _get_jwks()
        payload = jwt.decode(
            credentials.credentials,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")  # desde publicMetadata
        if not user_id or not tenant_id:
            raise HTTPException(status_code=401, detail="Missing claims")
        return {"user_id": user_id, "tenant_id": tenant_id}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### 3.2 deps.py actualizado

```python
# apps/api/app/deps.py (cambios)

from .auth import get_current_user

# ANTES: get_tenant_id leia del header X-Tenant-Id
# AHORA: get_tenant_id extrae del JWT validado

def get_tenant_id(
    user: dict = Depends(get_current_user),
) -> UUID:
    return UUID(user["tenant_id"])


# get_tenant_db NO cambia — sigue usando get_tenant_id
```

### 3.3 Fallback para desarrollo sin Clerk

```python
# En deps.py, si CLERK_JWKS_URL no esta configurado:

CLERK_CONFIGURED = bool(os.environ.get("CLERK_JWKS_URL"))

def get_tenant_id(...):
    if CLERK_CONFIGURED:
        # Validar JWT de Clerk
        user = get_current_user(credentials)
        return UUID(user["tenant_id"])
    else:
        # Fallback: leer del header (solo desarrollo)
        return UUID(x_tenant_id_header)
```

---

## 4. Sincronizacion de usuarios (Webhooks)

### 4.1 Endpoint de webhook

```python
# apps/api/app/routers/webhooks.py

@router.post("/clerk")
async def clerk_webhook(request: Request, db: Session = Depends(get_db)):
    """Recibe eventos de Clerk: user.created, user.updated."""
    payload = await request.json()
    event_type = payload.get("type")
    data = payload.get("data", {})

    if event_type == "user.created":
        # Crear usuario en nuestra BD
        user = User(
            id=UUID(data["id"]),  # clerk user id
            clerk_id=data["id"],
            email=data["email_addresses"][0]["email_address"],
            full_name=f"{data.get('first_name', '')} {data.get('last_name', '')}",
            tenant_id=UUID(data["public_metadata"]["tenant_id"]),
            user_type=data["public_metadata"].get("role", "usuario_interno"),
        )
        db.add(user)
        db.commit()

    elif event_type == "user.updated":
        # Actualizar datos en nuestra BD
        ...

    return {"ok": True}
```

### 4.2 Modelo: agregar clerk_id

```sql
-- Migracion: agregar clerk_id a users
ALTER TABLE users ADD COLUMN clerk_id TEXT UNIQUE;
CREATE INDEX idx_users_clerk_id ON users (clerk_id);
```

---

## 5. Configuracion de SSO en Clerk

No requiere codigo. Se configura en el dashboard de Clerk:

### Microsoft (Entra ID)
1. Clerk Dashboard → SSO Connections → Add → Microsoft
2. En Azure portal: App registrations → New registration
3. Redirect URI: `https://clerk.ambienta.cl/v1/oauth_callback`
4. Copiar Client ID y Client Secret a Clerk

### Google
1. Clerk Dashboard → SSO Connections → Add → Google
2. En Google Cloud Console: OAuth client ID
3. Redirect URI: `https://clerk.ambienta.cl/v1/oauth_callback`
4. Copiar Client ID y Client Secret a Clerk

---

## 6. Variables de entorno

### Frontend (apps/web)

```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/login
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/signup
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
```

### Backend (apps/api)

```env
CLERK_SECRET_KEY=sk_test_...
CLERK_JWKS_URL=https://<clerk-domain>/.well-known/jwks.json
CLERK_WEBHOOK_SECRET=whsec_...
```

### .env.example

Se agregan las variables anteriores con valores placeholder y comentarios.

---

## 7. Consideraciones de seguridad

- El JWT se valida con JWKS publica (RS256), no con un secret compartido
- El `tenant_id` viene firmado dentro del JWT — no se puede falsificar
- La JWKS se cachea en memoria para evitar llamadas HTTP en cada request
- El webhook de Clerk se verifica con `CLERK_WEBHOOK_SECRET` (svix)
- El header `X-Tenant-Id` se mantiene **solo** como fallback en desarrollo
- En produccion, si no hay JWT, la API responde 401 (nunca cae al fallback)
- Los claims del JWT no reemplazan el RBAC: solo autentican. Los permisos
  se verifican contra `user_permissions` en nuestra BD

## 8. Riesgos y mitigaciones

| Riesgo | Mitigacion |
|---|---|
| Lock-in con Clerk | Toda la validacion vive en `auth.py` (1 archivo). Si se cambia de proveedor, se reescribe solo ese modulo |
| JWKS no disponible | Cache en memoria + retry con backoff. Si falla, 503 (no 401) |
| Latencia del webhook | El webhook es asincrono; la BD puede tener un delay de segundos respecto a Clerk |
| Desarrollo sin Clerk | Fallback a DevRoleSwitcher + header X-Tenant-Id cuando `CLERK_PUBLISHABLE_KEY` no esta configurado |
| SSO de Microsoft falla con ciertos tenants de Azure | Verificar con Entra ID antes de comprometerse (pendiente ADR-006) |
