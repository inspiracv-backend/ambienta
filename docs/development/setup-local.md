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

## Consumir la API desde fuera (agente de IA, integraciones)

Para quien no viene a tocar el frontend sino a **leer datos desde otro
servicio**. En modo desarrollo no hace falta token: basta declarar de que
empresa se esta hablando.

```bash
curl -H "X-Tenant-Id: a0000000-0000-0000-0000-000000000001"   http://localhost:8000/api/v1/me
```

**Ese header solo funciona con Clerk apagado.** Si tu `.env` tiene
`CLERK_JWKS_URL`, la API lo ignora y exige un JWT — es lo correcto, pero
sorprende cuando uno prueba en una maquina configurada y en otra no.

### Las dos empresas sembradas

| `X-Tenant-Id` | Empresa | `tenant_type` |
|---|---|---|
| `a0000000-0000-0000-0000-000000000001` | Minera Andes SpA | `company` (cliente directo) |
| `a0000000-0000-0000-0000-000000000002` | EcoGestion Consultoria Ambiental | `manager` (gestor) |

Sirven para probar los dos casos: **el tipo de empresa cambia como se administra
su normativa**, y con una sola no se nota.

### Los tres endpoints del agente

```bash
GET /api/v1/me                              # quien habla: usuario, empresa, sector, tramo, roles
GET /api/v1/compliance/normativa-aplicable  # que normas le aplican, y por que
GET /api/v1/compliance/resumen              # como va el cumplimiento
```

Tres trampas que cuestan tiempo:

1. **Filtrar por `tramo`, no por numero de empleados.** El sistema filtra la
   normativa por tramo (`micro`/`pequena`/`mediana`/`grande`). El numero de
   empleados **no existe en la base**: filtrar por el da otra cosa.

2. **En `normativa-aplicable`, mirar `estado` antes que las listas.** Una lista
   vacia tiene tres causas y **solo una significa "no tiene obligaciones"**. Las
   otras dos —falta declarar el sector, faltan normas clasificadas— significan
   que todavia no se sabe. Responder "esta al dia" ahi le dice a una empresa que
   no debe nada cuando nadie miro.

3. **En `resumen` hay tres porcentajes y no son intercambiables.**
   `porcentaje_sobre_evaluados` da 100 % con un articulo cumplido y diecinueve
   sin evaluar. Va siempre con `cobertura`, o se usa `porcentaje`, que ya los
   combina. **No derivar uno de los otros dos**: se redondean por separado y las
   guardas son asimetricas.

### La pantalla del chatbot ya existe

`/chatbot` esta construida, con el panel de conversacion armado y alimentado por
respuestas de ejemplo (`apps/web/mocks/chatbot`). El trabajo es **reemplazar esa
fuente**, no construir la interfaz. Para persistir el hilo estan
`/support/chatbot` y `/support/chatbot/{id}/messages`.

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
