# Entornos de Ambienta

Dos entornos, definidos como código en el repositorio.

| | Desarrollo | Producción |
|---|---|---|
| Archivo Compose | `docker-compose.yml` | `docker-compose.prod.yml` |
| Proyecto Docker | `ambienta-dev` | `ambienta-prod` |
| Dónde corre | Máquina del desarrollador | Servidor (VPS) |
| Web | http://localhost:3000 | `https://<DOMAIN_WEB>` |
| API | http://localhost:8000/api/v1 | `https://<DOMAIN_API>/api/v1` |
| Health | http://localhost:8000/health | `https://<DOMAIN_API>/health` |
| Postgres | `localhost:5432` (expuesto) | Solo red interna (túnel SSH) |
| Redis | *(no en el stack actual)* | *(pendiente, epica de Worker)* |
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

Los tres servicios deben estar `Up`, y `postgres` además `(healthy)`.

```bash
curl http://localhost:8000/health
```

Debe devolver `200 OK`.

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
docker compose up -d postgres
npm install

# Terminal 1 — API (requiere Python 3.12+)
cd apps/api && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
npm run dev:web
```

### Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `failed to connect to the docker API` | Docker Desktop no está corriendo. Ábrelo y espera a que el ícono quede estable. |
| `port is already allocated` | Otro proceso ocupa 3000/8000/5432. Libéralo o cambia el mapeo en `docker-compose.yml`. |
| La API reinicia en bucle | Revisa los logs: `docker compose logs api`. |
| Cambié `requirements.txt` y no toma efecto | Las dependencias se instalan en la imagen: `docker compose up -d --build api`. |
| `/health` da 503 | Postgres no está listo. `docker compose ps` para verificar. |
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

**Autenticación (Clerk, ADR-006).** No hay `JWT_SECRET`: la API **valida** un
JWT RS256 contra el JWKS público de Clerk, no lo emite. No hay secreto
compartido de firma que generar.

| Variable | Servicio | Para qué |
|---|---|---|
| `CLERK_JWKS_URL` | api | Llaves públicas para verificar la firma. **Si está vacía, la API acepta el header `X-Tenant-Id` sin autenticar** — nunca dejarla vacía en producción |
| `CLERK_ISSUER` | api | Emisor esperado del token |
| `CLERK_WEBHOOK_SECRET` | api | Firma svix del webhook que sincroniza usuarios |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | web | Llave pública. Vacía ⇒ DevRoleSwitcher |
| `CLERK_SECRET_KEY` | web | La usa `clerkMiddleware()` en el servidor de Next |
| `NEXT_PUBLIC_CLERK_JWT_TEMPLATE` | web | Nombre del template que inyecta el claim `tenant_id` |

Las credenciales de SSO (Microsoft, Google) **ya no son variables**: se
configuran en el panel de Clerk, no en el `.env`.

> **`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` se hornea en el bundle en tiempo de
> build.** Ponerla solo en el runtime del contenedor no basta: el navegador
> recibe un bundle compilado sin la llave y cae al DevRoleSwitcher aunque la
> variable esté presente en el servidor. En producción va como *build arg*.

Opcionales (hasta que existan): `RESEND_API_KEY`.

El Compose de producción **falla al arrancar** si falta cualquiera de las obligatorias, con un mensaje que nombra la variable — no arranca a medias.

### Desplegar

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Ver el [runbook de despliegue](./despliegue.md) para el procedimiento completo, verificación post-despliegue y rollback.

### Diferencias de seguridad respecto a desarrollo

- Postgres en una red Docker `internal: true` → sin ruta desde internet, aun con el firewall mal configurado.
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
