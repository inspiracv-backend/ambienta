# Runbook de Despliegue — Producción

Procedimiento para desplegar Ambienta en un servidor. Escrito para ejecutarse paso a paso, incluyendo verificación y rollback.

> **Estado:** la infraestructura está lista y validada, pero **este runbook no se ha ejecutado nunca todavía** — no existe un servidor de producción aprovisionado. La primera ejecución debe hacerse con calma y verificando cada paso.

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

Generar cada secreto por separado:

```bash
openssl rand -base64 32    # POSTGRES_PASSWORD
openssl rand -base64 32    # REDIS_PASSWORD
openssl rand -base64 48    # JWT_SECRET (mín. 32 caracteres)
```

```bash
chmod 600 .env             # solo el dueño puede leerlo
```

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

Los cinco servicios (`postgres`, `redis`, `api`, `web`, `caddy`) deben estar `Up`; `postgres` y `redis` además `(healthy)`.

### 4.2 La API responde y alcanza sus dependencias

```bash
curl https://api.tudominio.cl/health
curl https://api.tudominio.cl/health/ready
```

El segundo debe devolver `"estado": "ok"` con `postgres` y `redis` en `ok`. Si da **503**, la API está viva pero no alcanza una dependencia: revisar `docker compose -f docker-compose.prod.yml logs api`.

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
nc -zv api.tudominio.cl 6379    # debe FALLAR
```

Si alguno conecta, hay un problema de seguridad: revisar que el Compose de producción no publique esos puertos y que el firewall los bloquee.

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

Los volúmenes de datos (`postgres-data`, `redis-data`) **no** se tocan al hacer rollback de código. Si el problema fue una migración de base de datos, el rollback de código no la revierte — hay que restaurar desde backup (ver §7).

---

## 7. Backups — pendiente de implementar

**RNF-19 del Análisis Funcional exige respaldo automático diario, y hoy no existe ninguno configurado.** Esto es deuda abierta y debe resolverse antes de tener datos reales de clientes.

Backup manual mientras tanto:

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > backup-$(date +%F).sql.gz
```

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
| API reinicia en bucle | Variable de entorno faltante o inválida | `logs api`: la validación Zod nombra exactamente la variable |
| `/health/ready` da 503 | Postgres o Redis no alcanzables | `ps` para ver cuál está caído |
| El frontend llama a la API equivocada | `NEXT_PUBLIC_API_URL` quedó del build anterior | Reconstruir `web` con `--build` |
| `rate limit` de Let's Encrypt | Más de 5 intentos fallidos en la semana | Usar el ACME de staging y esperar el reset |
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
6. **Rotación de secretos** — no hay procedimiento definido para rotar `JWT_SECRET` (rotarlo invalida todas las sesiones activas).

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
