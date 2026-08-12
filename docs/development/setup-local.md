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

## Login de desarrollo

No hay auth real todavia. La pantalla de login muestra un panel **Acceso rapido de desarrollo** con los roles disponibles:

| Rol | Que puede hacer |
|---|---|
| Superadmin | Gestion de tenants y plataforma completa |
| Admin Empresa | Gestiona su empresa y empleados |
| Usuario Interno | Operativo, crea/envia declaraciones |
| Gestor | Admin Empresa + cartera de clientes |
| Cliente Invitado | Solo tickets de soporte |

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
