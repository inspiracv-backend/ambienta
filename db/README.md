# Base de datos — Ambienta

Esquema PostgreSQL del sistema. 51 tablas, RLS multi-tenant y catálogos base.

## Ejecutar

Con Docker, desde cero:

```bash
docker run -d --name ambienta-pg -e POSTGRES_PASSWORD=ambienta -e POSTGRES_DB=ambienta -p 5432:5432 pgvector/pgvector:pg16
```

Después, en orden:

```bash
psql "postgresql://postgres:ambienta@localhost:5432/ambienta" -v ON_ERROR_STOP=1 -f db/01_schema.sql -f db/03_seed_catalogos.sql
```

O todo junto con el script:

```bash
bash db/run.sh
```

## Archivos

| Archivo | Qué hace |
|---|---|
| `01_schema.sql` | Extensiones, 51 tablas, 152 FK, índices, triggers, RLS y rol de aplicación. Transaccional: o entra todo o no entra nada |
| `02_smoke_test.sql` | Verifica que las garantías se cumplan: aislamiento entre empresas, inmutabilidad del audit log y los CHECK de negocio. Hace `ROLLBACK` al final |
| `03_seed_catalogos.sql` | Países, fuentes normativas, 39 permisos, sectores CIIU y plantillas de declaración. Idempotente |

`02_smoke_test.sql` no es parte del despliegue — es la verificación. Corrélo después de cualquier cambio al esquema.

## Multi-tenancy: cómo lo usa la API

El aislamiento tiene dos barreras. La primera es el `WHERE tenant_id = ...` de cada repositorio. La segunda es RLS, que existe justamente para cuando la primera falle.

Para que RLS funcione, **la API debe abrir cada transacción declarando el tenant de la sesión**:

```sql
SET LOCAL ambienta.tenant_id = '<uuid del tenant>';
```

Y conectarse con un rol que no sea superusuario — `ambienta_app` está creado para eso. Un superusuario **ignora RLS por completo**, así que si la API se conecta como `postgres` el aislamiento no existe aunque las policies estén ahí.

Sin `ambienta.tenant_id` seteado, las consultas no devuelven filas. Falla cerrado a propósito: es preferible una pantalla vacía a una fuga de datos entre clientes.

## Qué NO incluye

**El borrador v1.8 del Análisis Funcional** (RF-90 a RF-114): instrumentos de auditoría, checklist por cláusula, entidad Hallazgo separada del registro de mejora, información documentada y colaboración. Ese borrador tiene 9 decisiones abiertas y CLAUDE.md §1 exige spec aprobada antes de implementar. Va en una migración posterior.

## Decisiones tomadas por defecto

Tres puntos del modelo estaban sin cerrar. Se eligió un valor por defecto para no bloquear el arranque, pero **conviene confirmarlos**:

| Punto | Qué se hizo | Qué falta decidir |
|---|---|---|
| Escala de severidad | `minor · major · critical` (la del modelo del backend), como `CHECK` | RF-100 del borrador v1.8 pide que sea configurable por empresa. Cuando se apruebe, el `CHECK` pasa a ser tabla de catálogo |
| Estados de un hallazgo | Los 6 del backend | El frontend usa 3 y el borrador v1.8 modela las etapas como entidad propia |
| Etapas del tratamiento | Columna `improvement_stages` JSONB en `nonconformities` | Si se normalizan, se convierte en tabla hija. El JSONB evita perder lo que el frontend ya guarda mientras tanto |

El stack del backend (NestJS o FastAPI) **no afecta este esquema**: es el mismo en ambos casos. Esa decisión bloquea la API, no la base.

## Convenciones

- `uuid` para entidades de negocio, `bigserial` para eventos, `smallserial` para catálogos
- `timestamptz` para eventos, `date` para vigencias legales
- `created_at/by` y `updated_at/by` en toda tabla de negocio; `updated_at` lo mantiene un trigger
- Borrado lógico con `deleted_at` e índices parciales `WHERE deleted_at IS NULL`
- El catálogo normativo (`legal_norms`, `legal_articles`, `sectors`, `countries`) **no lleva `tenant_id`**: la ley es la misma para todos
