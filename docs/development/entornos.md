# Entornos de Ambienta

Dos entornos, definidos como código en el repositorio.

| | Desarrollo | Producción |
|---|---|---|
| Archivo Compose | `docker-compose.yml` | `docker-compose.prod.yml` |
| Proyecto Docker | `ambienta-dev` | `ambienta-prod` |
| Dónde corre | Máquina del desarrollador | Servidor (VPS) |
| Web | http://localhost:3000 | `https://<DOMAIN_WEB>` |
| API | http://localhost:3001/api/v1 | `https://<DOMAIN_API>/api/v1` |
| Health | http://localhost:3001/health | `https://<DOMAIN_API>/health` |
| Postgres | `localhost:5432` (expuesto) | Solo red interna (túnel SSH) |
| Redis | `localhost:6379` (expuesto, sin clave) | Solo red interna, **con** clave |
| TLS | No (HTTP plano) | Sí, automático (Caddy + Let's Encrypt) |
| Recarga de código | Hot reload (volúmenes montados) | No — imagen inmutable |
| Secretos | En el Compose, en texto plano | En `.env`, fuera de git |
| `NODE_ENV` | `development` | `production` |
| Usuario del contenedor | root (para escribir en volúmenes) | No-root (`ambienta`, uid 1001) |

---

## Desarrollo

### Requisitos
- Docker Desktop (o Docker Engine + Compose v2)
- Node.js 24+ y npm 10+ *(solo si vas a correr las apps fuera de Docker)*

### Levantar

```bash
docker compose up -d
```

No requiere `.env`: el `docker-compose.yml` ya trae los valores locales. Esas credenciales son deliberadamente obvias (`ambienta_dev`, `dev-only-secret-...`) para que nadie las confunda con reales.

La primera vez tarda varios minutos (descarga de imágenes + `npm ci` dentro de los contenedores). Los arranques siguientes son rápidos.

### Verificar que todo quedó bien

```bash
docker compose ps
```

Los cuatro servicios deben estar `Up`, y `postgres`/`redis` además `(healthy)`.

```bash
curl http://localhost:3001/health/ready
```

Debe devolver `"estado": "ok"` con `postgres` y `redis` en `ok`.

### Comandos habituales

```bash
docker compose logs -f api          # seguir logs de la API
docker compose logs -f web          # seguir logs del frontend
docker compose restart api          # reiniciar solo la API
docker compose down                 # detener (los datos se conservan)
docker compose down -v              # detener Y BORRAR la base de datos
docker compose up -d --build api    # reconstruir tras cambiar dependencias
```

### Conectarse a la base de datos

```bash
docker compose exec postgres psql -U ambienta -d ambienta
```

O desde un cliente gráfico (DBeaver, TablePlus, pgAdmin):

```
Host: localhost   Puerto: 5432
Base: ambienta    Usuario: ambienta    Contraseña: ambienta_dev
```

### Trabajar sin Docker

Las apps pueden correr directo en el host, usando los contenedores solo para las bases de datos:

```bash
docker compose up -d postgres redis
npm install

# Terminal 1 — API (necesita las variables de entorno)
DATABASE_URL=postgresql://ambienta:ambienta_dev@localhost:5432/ambienta \
REDIS_URL=redis://localhost:6379 \
JWT_SECRET=dev-only-secret-no-usar-en-produccion-32c \
npm run dev --workspace @ambienta/api

# Terminal 2 — Frontend
npm run dev --workspace @ambienta/web
```

### Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `failed to connect to the docker API` | Docker Desktop no está corriendo. Ábrelo y espera a que el ícono quede estable. |
| `port is already allocated` | Otro proceso ocupa 3000/3001/5432/6379. Libéralo o cambia el mapeo en `docker-compose.yml`. |
| La API reinicia en bucle | Falta una variable requerida. `docker compose logs api` muestra exactamente cuál (la validación Zod lo dice). |
| Cambié `package.json` y no toma efecto | Las dependencias se instalan en la imagen: `docker compose up -d --build api`. |
| `/health/ready` da 503 | Postgres o Redis no están listos. `docker compose ps` para ver cuál. |
| Las extensiones de Postgres no existen | El script de init corre **solo** al crear el volumen. Si el volumen ya existía: `docker compose down -v && docker compose up -d`. |

---

## Producción

> **Este entorno requiere un servidor con DNS configurado.** No se puede levantar completo en una máquina local, porque Let's Encrypt necesita validar los dominios públicamente.

### Requisitos previos

1. **Servidor** con Docker + Compose v2 (VPS: Hetzner, DigitalOcean, AWS EC2…). Mínimo sugerido: 2 vCPU / 4 GB RAM.
2. **DNS**: registros `A` de `DOMAIN_WEB` y `DOMAIN_API` apuntando a la IP pública del servidor. **Antes** del primer arranque.
3. **Firewall**: puertos 80 y 443 abiertos. El 5432 y 6379 deben permanecer **cerrados**.
4. **`.env`** completo (ver abajo).

### Configurar

```bash
cp .env.example .env
```

Completar en `.env`, generando cada secreto con `openssl rand -base64 32`:

- `DOMAIN_WEB`, `DOMAIN_API`, `ACME_EMAIL`
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `REDIS_PASSWORD`
- `JWT_SECRET` (mínimo 32 caracteres)

Opcionales (hasta que existan): credenciales OAuth y `RESEND_API_KEY`.

El Compose de producción **falla al arrancar** si falta cualquiera de las obligatorias, con un mensaje que nombra la variable — no arranca a medias.

### Desplegar

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Ver el [runbook de despliegue](./despliegue.md) para el procedimiento completo, verificación post-despliegue y rollback.

### Diferencias de seguridad respecto a desarrollo

- Postgres y Redis en una red Docker `internal: true` → sin ruta desde internet, aun con el firewall mal configurado.
- Redis con contraseña obligatoria y persistencia AOF.
- Contenedores de app con usuario no-root (uid 1001).
- Caddy añade HSTS, `X-Content-Type-Options`, `X-Frame-Options` y oculta la cabecera `Server`.
- `restart: always` (en dev es `unless-stopped`, para que no reviva solo tras apagar el equipo).

### Acceder a la base de datos en producción

No está expuesta. Hay que hacer túnel SSH:

```bash
ssh -L 5432:localhost:5432 usuario@servidor
# y luego, en otra terminal, conectarse a localhost:5432
```

O directo dentro del servidor:

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U <POSTGRES_USER> -d <POSTGRES_DB>
```

---

## Un detalle importante sobre `NEXT_PUBLIC_API_URL`

Las variables `NEXT_PUBLIC_*` de Next.js se **incrustan en el bundle de JavaScript durante el build**, no se leen en runtime. Consecuencia práctica:

- Cambiar el dominio de la API exige **reconstruir la imagen del frontend**, no basta con reiniciar el contenedor.
- Cada entorno necesita su propia imagen de `web`.

Por eso el Dockerfile de `web` recibe `NEXT_PUBLIC_API_URL` como `ARG` y `docker-compose.prod.yml` lo pasa en `build.args`.
