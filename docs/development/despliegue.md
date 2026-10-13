# Runbook de Despliegue — Producción

Procedimiento para desplegar Ambienta en un servidor. Escrito para ejecutarse paso a paso, incluyendo verificación y rollback.

> **Estado (13-oct-2026):** no existe un servidor de producción aprovisionado, así
> que este runbook **no se ha ejecutado nunca contra un servidor**. Lo que sí se
> hizo ese día fue ensayarlo completo en local con las imágenes de producción
> reales, y el ensayo encontró **seis fallas que rompían el primer despliegue**.
> Están corregidas y anotadas donde corresponde:
>
> | # | Lo que pasaba | Dónde |
> |---|---|---|
> | 1 | Caddy hacía `reverse_proxy api:3001` y la API escucha en **8000**: 502 en toda la API | `infra/caddy/Caddyfile` |
> | 2 | El servicio `web` no recibía `CLERK_SECRET_KEY`: 500 en toda pantalla protegida | `docker-compose.prod.yml` |
> | 3 | La API se conectaba como **dueño** de la base, así que el `REVOKE` que hace inmutable `audit_log` no le aplicaba | §2, §4.6 |
> | 4 | La auditoría rotada se escribía en disco efímero: `up -d --build` la borraba, y la tabla ya no la tiene | §4.11, §7 |
> | 5 | `/health/ready`, que este runbook mandaba a verificar, **no existe** | §4.2 |
> | 6 | Nada decía que hay que crear el primer Admin Global: sin él nadie puede entrar | §4.10 |
>
> Ninguna se habría visto antes del primer intento, y tres de ellas no se ven
> ni siquiera entonces: el sistema arranca, se ve bien y falla en silencio.
> La primera ejecución real igual debe hacerse con calma, verificando cada paso.

---

## 0. Antes de empezar: lo que necesitas tener

| Requisito | Cómo obtenerlo |
|---|---|
| Servidor Linux con Docker + Compose v2 | VPS (Hetzner, DigitalOcean, AWS EC2…). Mínimo 2 vCPU / 4 GB RAM / 40 GB disco |
| Dos dominios apuntando al servidor | Registros `A` de `app.tudominio.cl` y `api.tudominio.cl` → IP pública del servidor |
| Puertos 80 y 443 abiertos | Firewall del proveedor + `ufw` del servidor |
| Acceso SSH | — |
| Secretos generados | `openssl rand -base64 32` (uno por cada secreto, no reutilizar) |

**El DNS debe estar propagado antes del primer arranque.** Let's Encrypt valida el dominio por HTTP; si no resuelve, la emisión del certificado falla y Caddy reintenta con backoff.

Verificar la propagación:

```bash
dig +short app.tudominio.cl
dig +short api.tudominio.cl
```

Ambos deben devolver la IP del servidor.

---

## 1. Preparar el servidor

```bash
ssh usuario@servidor

# Docker (si no está instalado)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# cerrar sesión y volver a entrar para que aplique el grupo

# Firewall: solo SSH, HTTP y HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

Verificar que 5432 y 6379 **no** estén abiertos: el Compose de producción no los publica, pero conviene confirmar que el firewall tampoco.

---

## 2. Clonar y configurar

```bash
git clone https://github.com/inspiracv-backend/ambienta.git
cd ambienta
git checkout main          # o la rama/tag que se vaya a desplegar

cp .env.example .env
nano .env                  # completar TODOS los valores obligatorios
```

Generar cada secreto por separado — **no reutilizar uno para dos cosas**:

```bash
openssl rand -base64 32                                       # POSTGRES_PASSWORD
openssl rand -base64 32                                       # APP_DB_PASSWORD
python -c "import secrets; print(secrets.token_urlsafe(48))"  # TOKEN_INVITADO_SECRETO
```

> **`REDIS_PASSWORD` y `JWT_SECRET` ya no existen.** La primera murió con el
> servicio de Redis que ningún código consultaba; la segunda con ADR-006: la API
> no emite tokens propios, valida los de Clerk contra su JWKS pública. Si
> aparecen en un `.env` heredado, se borran.

**`APP_DB_PASSWORD` es la contraseña de `ambienta_app`, el rol con el que se
conecta la API** — y no es un detalle de estilo:

- Es el rol que **no puede saltarse RLS**, que es la única barrera entre
  empresas: ninguna consulta de la aplicación filtra por `tenant_id`.
- Es el rol al que aplica el `REVOKE UPDATE, DELETE ON audit_log` de `db/07`.
  Conectada como dueño de la base, la API podía **editar y borrar el registro
  de auditoría**: RNF-08 y RNF-25 existían en desarrollo y no en producción.

`db/07` lo crea con `ambienta_app_dev`, escrita en un archivo versionado de un
repositorio **público**. `infra/postgres/init/99-password-del-rol-app.sh` la
reemplaza por ésta en el primer arranque, y se niega a seguir si le pasan la de
desarrollo.

> **Si el volumen de datos ya existe, los scripts de init NO vuelven a correr.**
> Cambiar `APP_DB_PASSWORD` en el `.env` de una instalación ya desplegada no
> cambia nada en la base, y la API queda sin poder conectarse. El ALTER va a
> mano, y después se reinicia la API:
>
> ```bash
> docker compose -f docker-compose.prod.yml exec postgres \
>   psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
>   -c "ALTER ROLE ambienta_app WITH LOGIN PASSWORD 'la-nueva'"
> docker compose -f docker-compose.prod.yml up -d api cron
> ```

El resto de los secretos no se generan acá: vienen de los paneles de Clerk,
Resend y Backblaze. Ver §2.1.

```bash
chmod 600 .env             # solo el dueño puede leerlo
```

### 2.1 Lo que hay que configurar en Clerk (antes del primer ingreso)

Nada de esto está en el repositorio: son cuatro cosas en el panel de Clerk, y
sin ellas el despliegue levanta y nadie puede entrar.

1. **Instancia de producción.** Las llaves de desarrollo (`pk_test_`, `sk_test_`)
   no sirven en el dominio real. Las de producción (`pk_live_`, `sk_live_`) van a
   `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, y su JWKS e issuer a
   `CLERK_JWKS_URL` y `CLERK_ISSUER`.

2. **El JWT Template que inyecta `tenant_id`.** Es el paso que más fácil se
   olvida y el que deja **401 en toda la API**. En *JWT Templates* se crea uno
   —por defecto el código lo pide con el nombre `default`,
   `NEXT_PUBLIC_CLERK_JWT_TEMPLATE`— con:

   ```json
   { "tenant_id": "{{user.public_metadata.tenant_id}}" }
   ```

   El token de sesión estándar **no lleva claims personalizados**: sus claims son
   `azp, exp, fva, iat, iss, nbf, sid, sts, sub, v`. Que el template se llame
   `default` no lo vuelve el predeterminado — es solo su nombre.

3. **El webhook de usuarios**, en *Webhooks* → *Add Endpoint*:

   ```
   https://api.tudominio.cl/api/v1/webhooks/clerk
   ```

   Eventos `user.created`, `user.updated` y `user.deleted`. Su *Signing Secret*
   va en `CLERK_WEBHOOK_SECRET`. Sin esto, quien entra por SSO no tiene fila en
   `users` y recibe `403 sesion_sin_empresa`.

4. **Cerrar el registro público**, en *Restrictions* → modo *Restricted*. Si
   queda abierto, cualquiera con la URL se crea una cuenta. El acceso lo habilita
   la empresa por invitación, y la invitación es la que lleva el `tenant_id` en
   `public_metadata`.

El SSO con Google y Microsoft se configura también acá (*SSO Connections*), con
credenciales propias de cada proveedor: el callback de OAuth va a Clerk, no a
esta API.

### Recomendado: probar primero con el staging de Let's Encrypt

Let's Encrypt limita a **5 certificados por dominio por semana**. Si algo sale mal en el primer intento, ese límite se consume rápido. Para la primera prueba, descomentar en `infra/caddy/Caddyfile`:

```
acme_ca https://acme-staging-v02.api.letsencrypt.org/directory
```

El navegador mostrará el certificado como no confiable (es esperado), pero confirma que todo el flujo funciona. Luego se comenta esa línea, se ejecuta `docker compose -f docker-compose.prod.yml restart caddy` y se obtiene el certificado real.

---

## 3. Desplegar

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

La primera vez tarda bastante (descarga de imágenes base + dos builds completos). Seguir el progreso:

```bash
docker compose -f docker-compose.prod.yml logs -f
```

---

## 4. Verificar (no omitir ningún paso)

### 4.1 Todos los contenedores arriba

```bash
docker compose -f docker-compose.prod.yml ps
```

Los cinco servicios (`postgres`, `api`, `web`, `cron`, `caddy`) deben estar `Up`,
y `postgres`, `api` y `web` además `(healthy)`.

> **`api` tenía `restart: always` y ningún healthcheck**, así que `ps` decía
> «running» aunque no sirviera una sola respuesta, y Caddy le mandaba tráfico en
> cuanto el contenedor arrancaba. Ahora tiene el mismo healthcheck que en
> desarrollo.

> **`redis` ya no está, y `cron` sí.** Medido el 4-sep: no había una sola referencia a Redis en `apps/api/app/`, pero el Compose lo levantaba con volumen, healthcheck y una `REDIS_PASSWORD` obligatoria que impedía arrancar. La cola de avisos es la tabla `notifications` en Postgres — la decisión estaba tomada y escrita, y el Compose no se había enterado.
>
> `cron` es el servicio nuevo, y es el que faltaba de verdad: ver 4.7.

### 4.2 La API responde y alcanza sus dependencias

```bash
curl https://api.tudominio.cl/health
curl https://api.tudominio.cl/health/db
```

El segundo es el que importa: comprueba el esquema contra la base. Si da **503**,
la API está viva pero no alcanza la base o el esquema no cuadra: revisar
`docker compose -f docker-compose.prod.yml logs api`.

> **Acá decía `/health/ready`, y ese endpoint no existe.** La API expone
> `/health` y `/health/db` (`apps/api/app/main.py`). Verificar el despliegue con
> una URL inventada devuelve 404 y no dice nada del estado real.

**`/health/db` usa el motor de administración**, o sea `DATABASE_ADMIN_URL`. Si
está vacía, `db.py` cae a `DATABASE_URL` sin avisar — y como la API se conecta
con `ambienta_app`, que no puede revisar el esquema completo, este check queda en
rojo. El compose de producción la pasa explícita por eso.

### 4.3 El frontend carga

```bash
curl -I https://app.tudominio.cl/login
```

Debe devolver `200`. Abrirlo también en un navegador.

### 4.4 TLS válido

```bash
curl -vI https://app.tudominio.cl 2>&1 | grep -i 'SSL certificate\|issuer'
```

Debe mostrar un certificado emitido por Let's Encrypt (no el de staging, si ya se pasó a producción).

### 4.5 Las extensiones de Postgres existen

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT extname FROM pg_extension;"
```

Debe listar `vector`, `pgcrypto`, `pg_trgm`.

### 4.6 Las bases NO están expuestas a internet

Desde una máquina **distinta** al servidor:

```bash
nc -zv api.tudominio.cl 5432    # debe FALLAR (timeout o refused)
```

Si conecta, hay un problema de seguridad: revisar que el Compose de producción no publique ese puerto y que el firewall lo bloquee.

### 4.6.1 La API se conecta con el rol correcto, y la bitácora es inmutable

**Es la verificación que faltaba, y la que estaba fallando.** Hasta el 13-oct el
compose de producción armaba la URL de la API con `${POSTGRES_USER}` —el dueño de
la base—, así que las dos garantías que sostiene la base no existían en el único
entorno donde importan.

Con qué rol está conectada la API, de verdad:

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT usename, count(*) FROM pg_stat_activity WHERE datname = current_database() GROUP BY 1;"
```

Tiene que aparecer **`ambienta_app`**. Si solo aparece el dueño, la API está
conectada con él y nada de lo de abajo se cumple.

Que el rol de la aplicación no pueda tocar el registro de auditoría:

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT has_table_privilege('ambienta_app','audit_log','UPDATE') AS puede_editar,
          has_table_privilege('ambienta_app','audit_log','DELETE') AS puede_borrar,
          has_table_privilege('ambienta_app','audit_log','INSERT') AS puede_escribir;"
```

Lo correcto es `f | f | t`: escribe y no corrige (RNF-08, RNF-25).

Y que no pueda saltarse RLS:

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'ambienta_app';"
```

Ambas `f`. Si alguna es `t`, el aislamiento entre empresas no existe: ninguna
consulta de la aplicación filtra por `tenant_id`, RLS no es la segunda barrera
sino la única.

### 4.7 Los avisos de vencimiento van a correr

**Es el paso que no existía, y es el que decide si el producto cumple su función.**

Hasta el 4-sep no había cron en ninguna parte: ni en el Compose, ni en este runbook, ni en `infra/`. El generador de avisos, el despachador, el envío por Resend y las plantillas estaban todos construidos y probados — y nada los llamaba. Desplegando así, **un sistema de alertas de vencimiento no habría avisado nunca**, sin un solo error a la vista. La épica figura cerrada desde el 27-ago.

Ahora corre el servicio `cron`, que despierta a la hora de `HORA_AVISOS` (07 por defecto):

```bash
docker compose -f docker-compose.prod.yml logs cron | tail -5
```

Debe mostrar la línea con la próxima corrida:

```
[cron] proxima corrida de avisos: ...
```

Para no esperar hasta mañana, forzar una corrida ahora:

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.tareas avisos
```

Informa cuántos avisos creó, cuántos omitió por repetidos y **cuántas obligaciones no avisaron a nadie**. Ese último número es el que hay que mirar: significa que esa empresa no tiene ni responsable ni administrador activo.

### 4.8 El correo sale de verdad

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.tareas.comprobar_correo tu@correo.cl
```

Manda un correo real. El error más común —dominio del remitente sin verificar en Resend— **no se detecta hasta el primer envío**, que sin esto sería el primer aviso de vencimiento de un cliente. Y «aceptado por Resend» no es «entregado»: si no llega, revisar SPF y DKIM.

### 4.9 El almacenamiento acepta archivos

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.tareas.comprobar_almacenamiento
```

Sube, baja, compara el contenido y borra. Que `boto3` construya una URL firmada **no prueba nada**: la firma se genera igual con una clave equivocada y falla recién al usarla.

### 4.10 Crear el primer Admin Global

**Sin este paso el sistema está desplegado y nadie puede entrar.** Producción
arranca sin ninguna empresa y sin ningún usuario —no se carga `02_seed.sql`—,
dar de alta una empresa exige ser Admin Global, y un Admin Global no lo podía
crear nadie. Este runbook no lo mencionaba.

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.tareas crear-admin-global \
  --correo persona@tudominio.cl --nombre "Nombre Apellido" \
  --razon-social "Ambienta SpA" --rut 76.123.456-7
```

Deja hecho, en una sola transacción: la empresa de la plataforma, sus roles de
sistema, la persona como `platform_admin` con `admin_empresa`, y la invitación de
Clerk con el `tenant_id` en `public_metadata`. Si Clerk no responde, no queda
nada a medias.

**Se niega si ya existe un Admin Global**, a propósito: sumar gente al equipo de
plataforma es RF-84, y este comando no es la puerta trasera para eso.

La invitación llega por correo y la persona crea su cuenta desde ahí. Requiere
que §2.1 esté hecho: sin el JWT Template, entra y recibe 401 en todo.

### 4.11 El archivo de la auditoría sobrevive al redespliegue

```bash
docker compose -f docker-compose.prod.yml exec api sh -c \
  'touch /var/lib/ambienta/auditoria/.prueba && ls -la /var/lib/ambienta/auditoria'
```

Tiene que escribir sin error. Dos cosas se verifican acá:

1. **Que el directorio esté en un volumen.** `rotar-auditoria` escribe un JSON
   por empresa y **borra esas filas de `audit_log`**. Hasta el 13-oct el
   `docker-compose.prod.yml` no montaba volumen en esa ruta, así que el JSON
   caía en el sistema de archivos del contenedor y el `up -d --build` de §5 —el
   procedimiento de actualización de este mismo runbook— lo destruía. Habría
   borrado meses de registro de actividades, sin un solo error, en un producto
   cuya función es demostrar cumplimiento.
2. **Que el proceso pueda escribir.** La API corre como usuario sin privilegios;
   el directorio se crea en la imagen con ese dueño para que el volumen lo
   herede. Un volumen inicializado vacío sería de `root` y la rotación fallaría
   recién al final de mes.

Que el volumen existe de verdad:

```bash
docker volume ls | grep auditoria-archivada
```

**Está en la lista de respaldos de §7**, y es el único cuyo contenido no se puede
reconstruir desde ninguna otra parte: cuando la rotación corre, la tabla ya no lo
tiene.

### 4.12 Cargar el catálogo normativo

Producción arranca **sin `02_seed.sql`**, así que el catálogo son las ocho normas de ejemplo del esquema. Hay que traer las reales:

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.tareas sincronizar-bcn
```

Y **después** volver a aplicar la clasificación transversal, porque la sincronización crea normas que la migración no alcanzó a clasificar:

```bash
docker compose -f docker-compose.prod.yml exec -T postgres   psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 < db/23_normativa_transversal.sql
```

Medido en local: sin este segundo paso, el DS 1 queda con **cero** sectores y el DS 40 con uno de ocho. Nada falla — la empresa simplemente recibe menos normativa de la que le corresponde.

Comprobar el resultado:

```bash
docker compose -f docker-compose.prod.yml exec postgres   psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c   "SELECT count(*) AS normas FROM legal_norms WHERE deleted_at IS NULL;"
```

Deben ser **24 o más**, no 8. Con 8 la sincronización no corrió.

> **No correr `sembrar_demo` en producción.** La tarea se niega sola con `ENVIRONMENT=production`, y comprueba el entorno antes de abrir la sesión.

---

## 5. Actualizar una versión ya desplegada

```bash
cd ambienta
git pull

docker compose -f docker-compose.prod.yml up -d --build
```

Compose recrea solo los servicios cuya imagen cambió. Luego repetir las verificaciones 4.1 a 4.3.

> **Recordatorio sobre el frontend:** `NEXT_PUBLIC_API_URL` se hornea en el bundle en tiempo de build. Si cambia `DOMAIN_API`, hay que reconstruir la imagen de `web` (`--build`), no basta con reiniciar.

---

## 6. Rollback

```bash
git log --oneline -10             # identificar el commit estable anterior
git checkout <commit-estable>
docker compose -f docker-compose.prod.yml up -d --build
```

Los volúmenes de datos (`postgres-data`, `auditoria-archivada`, y los de los
certificados de Caddy) **no** se tocan al hacer rollback de código. `redis-data`
ya no existe: el servicio se eliminó el 4-sep.

Si el problema fue una migración de base de datos, el rollback de código **no la
revierte** — hay que restaurar desde backup (ver §7).

---

## 7. Backups — pendiente de implementar

**RNF-19 del Análisis Funcional exige respaldo automático diario, y hoy no existe ninguno configurado.** Esto es deuda abierta y debe resolverse antes de tener datos reales de clientes.

Backup manual mientras tanto. **Son dos cosas, no una:**

```bash
# 1. La base
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > backup-$(date +%F).sql.gz

# 2. La auditoría ya rotada, que NO está en la base
docker run --rm \
  -v ambienta-prod_auditoria-archivada:/origen:ro \
  -v "$PWD":/destino \
  alpine tar czf /destino/auditoria-$(date +%F).tar.gz -C /origen .
```

**El segundo respaldo es el que no se puede rehacer.** `rotar-auditoria` saca las
filas de `audit_log` después de releer el archivo que escribió: a partir de ese
momento el JSON del volumen es el único lugar donde existe ese registro. Un
`pg_dump` perfecto no lo contiene.

Restauración:

```bash
gunzip -c backup-2026-07-28.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

Para cumplir RNF-19/RNF-20 hace falta: cron diario, almacenamiento **fuera** del servidor (S3/R2), retención definida y **restauración probada** (un backup nunca verificado no es un backup).

---

## 8. Diagnóstico de problemas

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Caddy no obtiene certificado | DNS no propagado, o 80/443 cerrados | `dig +short <dominio>`; revisar firewall; `logs caddy` |
| `no such host: api` en logs de Caddy | El servicio `api` no arrancó | `logs api` — casi siempre falta una variable en `.env` |
| API reinicia en bucle | Variable de entorno faltante o inválida | `logs api`: pydantic-settings nombra exactamente la variable. El compose además corta con `:?` antes de arrancar |
| `/health/db` da 503 | Postgres no alcanzable, esquema desalineado, o `DATABASE_ADMIN_URL` vacía | `ps`; `logs api`; comprobar que el compose pase las dos URLs |
| El frontend llama a la API equivocada | `NEXT_PUBLIC_API_URL` quedó del build anterior | Reconstruir `web` con `--build` |
| `rate limit` de Let's Encrypt | Más de 5 intentos fallidos en la semana | Usar el ACME de staging y esperar el reset |
| **502 en toda la API**, con Caddy y `api` arriba | El `reverse_proxy` apunta a un puerto donde nadie escucha | La API escucha en **8000**. Comprobar el `Caddyfile`: decía 3001 hasta el 13-oct |
| **500 en toda pantalla protegida**, y el login se ve bien | Falta `CLERK_SECRET_KEY` en el servicio `web` | `clerkMiddleware()` corre en el servidor de Next. El login es público, así que el síntoma aparece recién al entrar |
| 401 en toda la API, con sesión válida | El JWT Template no existe o se llama distinto | §2.1 punto 2. El token de sesión estándar no lleva `tenant_id` |
| `403 sesion_sin_empresa` tras entrar por SSO | El webhook de Clerk no corrió | §2.1 punto 3; `logs api` filtrando por webhook |
| `permission denied for table audit_log` | **Es lo correcto**: la conexión de la aplicación no puede corregir la bitácora | Si la operación era legítima (rotación mensual), corre con `DATABASE_ADMIN_URL` |
| La API no se conecta tras cambiar `APP_DB_PASSWORD` | Los scripts de init no vuelven a correr sobre un volumen existente | El `ALTER ROLE` a mano de §2 |
| `"/repo/apps/web/public": not found` al construir | Falta el directorio `apps/web/public` en el repo | Debe existir aunque esté vacío (`.gitkeep`): `COPY` no admite "si existe" |
| Disco lleno | Imágenes y caché de build acumuladas | `docker system df`, luego `docker builder prune -af` y `docker image prune -f` |

Logs útiles:

```bash
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f caddy
docker stats --no-stream        # CPU/memoria por contenedor
```

---

## 9. Lo que este runbook todavía no cubre

Deuda operacional explícita, para que no se asuma resuelta:

1. **CI/CD** — el despliegue es manual por SSH. No hay pipeline ni despliegue automático por merge.
2. **Backups automáticos** (§7) — RNF-19 sin cumplir.
3. **Observabilidad** — logs a stdout únicamente. Sin agregación (Loki/Datadog), métricas ni alertas.
4. **Despliegue sin downtime** — `up -d --build` reinicia los contenedores; hay unos segundos de corte. Para zero-downtime haría falta réplicas + drenaje del balanceador.
5. **Entorno de staging** — solo existen dev (local) y producción. Un staging que refleje producción reduciría el riesgo de la primera vez.
6. **Rotación de secretos** — no hay procedimiento definido. `JWT_SECRET` ya no
   existe (las sesiones las firma Clerk), pero sí hay que poder rotar
   `APP_DB_PASSWORD` (§2 tiene el ALTER manual, sin automatizar),
   `TOKEN_INVITADO_SECRETO` —rotarlo invalida las sesiones de invitado activas— y
   las llaves de Clerk, Resend y Backblaze.
7. **Un `docker compose exec` corre como el rol de administración.** La rotación
   mensual lo necesita, pero significa que quien tenga acceso al servidor puede
   escribir en cualquier empresa: el aislamiento protege a la aplicación, no al
   operador.

---

## Referencias

- [Guía de entornos](./entornos.md)
- [Arquitectura del backend](../arquitectura/backend-arquitectura.md)


## Rotacion mensual del registro de actividades

El registro (`audit_log`) crece sin techo. Una vez al mes se archiva lo del mes
cerrado a un JSON **por empresa** y se saca de la tabla.

### El cron

```
0 3 1 * *  cd /srv/ambienta && docker compose exec -T api python -m app.tareas rotar-auditoria >> /var/log/ambienta-rotacion.log 2>&1
```

**El dia 1 a las 3 de la manana.** Ese dia el mes anterior ya cerro, y a esa
hora no hay nadie usando el sistema. La salida va a un archivo: una tarea de
cron que no deja rastro es una tarea que nadie sabe si corrio.

### Antes de confiar en ella, correrla en seco

```bash
docker compose exec -T api python -m app.tareas rotar-auditoria --en-seco
```

Escribe los archivos y **no borra nada**. Sirve para comprobar que el archivo
sale bien antes de habilitar la parte destructiva. Sin este paso, la primera
corrida real es la prueba.

Para un mes concreto: `--mes 2026-07`.

### Que garantiza y que no

- **Nunca borra lo que no quedo guardado.** Exporta, **relee el archivo**, y
  recien ahi borra — todo en una transaccion. Que `write_text` no lance no
  prueba que el contenido este en disco: un disco lleno puede truncar sin error.
- **Un archivo por empresa.** El registro de una empresa no viaja mezclado con
  el de otra, asi que entregarlo no exige filtrarlo primero.
- **Nunca el mes en curso.** Rotar a mitad de mes deja el registro partido en
  dos lugares para un periodo que no termino.
- Corre con **el dueno de la base**, no con `ambienta_app`: la conexion de la
  API no puede borrar de `audit_log` a proposito. Ver `RNF-25`.

### Donde caen los archivos

`RUTA_ARCHIVO_AUDITORIA`, por defecto `/var/lib/ambienta/auditoria`. **Hoy es
disco del servidor**; cuando exista la cuenta de Backblaze se cambia esa ruta
por su bucket y la tarea no se toca.

**Ese directorio hay que respaldarlo.** Si se pierde, se perdio el registro: la
tabla ya no lo tiene.

### Volver a cargar un mes archivado

El JSON conserva las columnas con el mismo nombre que la tabla, asi que se
reinserta directo sin transformar nada.
