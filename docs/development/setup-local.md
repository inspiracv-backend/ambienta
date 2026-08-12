# Setup local

Guia para levantar Ambienta en tu maquina de desarrollo.

## Requisitos

- **Docker Desktop** (o Docker Engine + Compose v2)
- **Node.js 20+** y **npm 10+** (solo si quieres correr el frontend fuera de Docker)
- **Python 3.12+** (solo si quieres correr la API fuera de Docker)
- **Git**

## Paso 1: clonar el repositorio

```bash
git clone https://github.com/inspiracv-backend/ambienta.git
cd ambienta
```

## Paso 2: levantar con Docker Compose

```bash
docker compose up -d
```

No requiere `.env` — el `docker-compose.yml` ya trae credenciales de desarrollo en texto plano. La primera vez tarda varios minutos (descarga de imagenes + instalacion de dependencias).

## Paso 3: verificar

```bash
docker compose ps
```

Deben aparecer 3 servicios `Up`: `postgres`, `api`, `web`.

```bash
curl http://localhost:8000/health
```

Debe responder `200 OK`.

## URLs de desarrollo

| Servicio | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000/api/v1 |
| Swagger | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| PostgreSQL | `postgresql://ambienta:ambienta_dev@localhost:5432/ambienta` |

## Login

Hay auth real (Clerk, ADR-006), pero **el repo levanta sin ella**. Cuál de los
dos modos corre lo decide una sola variable:

| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Qué pasa |
|---|---|
| vacía | **Modo desarrollo**: DevRoleSwitcher, y la API acepta el header `X-Tenant-Id` |
| con valor | **Modo real**: pantalla de Clerk, y la API exige un JWT válido |

No hace falta cuenta de Clerk para trabajar en el repo. Si la variable está
vacía, todo funciona como antes.

### Modo desarrollo (por defecto)

La pantalla de login muestra un panel **Acceso rápido de desarrollo**:

| Rol | Qué puede hacer |
|---|---|
| Superadmin | Gestión de tenants y plataforma completa |
| Admin Empresa | Gestiona su empresa y empleados |
| Usuario Interno | Operativo, crea/envía declaraciones |
| Gestor | Admin Empresa + cartera de clientes |
| Cliente Invitado | Solo tickets de soporte |

### Modo real (con Clerk)

Cinco variables en `.env`, todas documentadas en `.env.example`:

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_CLERK_JWT_TEMPLATE=default
CLERK_JWKS_URL=https://<instancia>.clerk.accounts.dev/.well-known/jwks.json
CLERK_ISSUER=https://<instancia>.clerk.accounts.dev
```

Tres cosas que cuestan una tarde si no se saben:

1. **Hay que crear un JWT Template en Clerk** con el claim `tenant_id`, y poner
   su nombre en `NEXT_PUBLIC_CLERK_JWT_TEMPLATE`. **El token de sesión estándar
   no lleva ese claim**: `getToken()` a secas devuelve un token sin `tenant_id`
   y la API responde 401. Tiene que ser `getToken({ template })`.

2. **`CLERK_SECRET_KEY` va también al servicio `web`**, no solo a la API.
   `clerkMiddleware()` corre en el servidor de Next y falla con
   *"Missing secretKey"* si no la encuentra.

3. **El webhook no llega a `localhost`.** Clerk no puede alcanzar
   `localhost:8000`, así que un usuario creado en Clerk **no aparece solo** en
   la tabla `users`. En local hay que insertarlo a mano, emparejando `clerk_id`:

   ```bash
   docker compose exec postgres psql -U ambienta -d ambienta \
     -c "UPDATE users SET clerk_id = 'user_xxx' WHERE email = 'dev@abada.cl';"
   ```

   En el VPS el webhook sí llega y esto no hace falta.

## Sin Docker (modo hibrido)

Levantar solo las bases de datos en Docker y las apps en el host:

```bash
docker compose up -d postgres
npm install

# Terminal 1 — API
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
npm run dev:web
```

## Conectarse a la base de datos

```bash
docker compose exec postgres psql -U ambienta -d ambienta
```

O con un cliente grafico (DBeaver, TablePlus, pgAdmin):

```
Host: localhost   Puerto: 5432
Base: ambienta    Usuario: ambienta    Contrasena: ambienta_dev
```

## Problemas frecuentes

| Sintoma | Solucion |
|---|---|
| `failed to connect to the docker API` | Docker Desktop no esta corriendo |
| `port is already allocated` | Otro proceso ocupa 3000/8000/5432. Liberalo o cambia el mapeo en `docker-compose.yml` |
| La API reinicia en bucle | Revisa logs: `docker compose logs api` |
| Cambie `requirements.txt` y no toma efecto | `docker compose up -d --build api` |
| El schema SQL no se aplico | El init corre solo al crear el volumen: `docker compose down -v && docker compose up -d` |
