# SPEC-03 · Base de conocimiento del AI Service

**Objetivo.** Una base propia del AI Service donde el texto normativo es buscable por
significado, por palabras y por cita, derivada del backend y reconstruible desde él.

## Alcance
- Esquema con migraciones versionadas.
- Fragmentos del catálogo público con vector, `tsvector` e identidad de cita.
- Estado de sincronización por fuente.
- Aislamiento por empresa preparado aunque en V1 no se guarde nada privado.

## Fuera de alcance
- Historial de conversaciones: vive en el backend (SPEC-07).
- Caché semántico: se agrega cuando haya datos de uso que lo justifiquen (D-10 queda escrita,
  no implementada en V1).
- Documentos privados y RCA indexados (decisión abierta C del plan: V2).

## Reglas

| Regla | De dónde sale |
|---|---|
| La fuente de verdad es el backend. Esta base se puede borrar y reconstruir con la sincronización | Propuesta del equipo: base independiente de datos derivados |
| Los identificadores son los UUID del backend (`norm_id`, `norm_version_id`, `article_id`). No se inventan ids | Evita tablas de equivalencias |
| El fragmento es el artículo (D-01). Solo se parte si supera el máximo, y las partes comparten la identidad | D-01 |
| Cada fragmento guarda su `ruta` jerárquica completa | D-02 |
| `tenant_id` nulo = catálogo público. Toda consulta filtra "de esta empresa o público" **en la base**, con RLS, no solo con `WHERE` | D-04, D-05, y el criterio del backend: RLS como barrera |
| El servicio se conecta con un rol sin `BYPASSRLS` y fija `app.tenant_id` al abrir cada transacción | Igual que el backend |
| Dos roles: `ia_consulta` (solo lectura, con RLS) para el servicio, e `ia_sincronizador` (escribe, con política `WITH CHECK tenant_id is null`) para SPEC-04. El que atiende consultas no puede escribir | Una consulta comprometida no altera el corpus |
| El modelo de embeddings y su dimensión quedan registrados por fragmento; cambiar de modelo es reindexar, y la migración lo dice | — |
| El `content_hash` del backend se guarda por versión: si no cambió, no se reindexa | Evita pagar embeddings dos veces |

## Esquema

```sql
-- versiones indexadas
version_norma (
  id                 uuid primary key,      -- norm_version_id del backend
  norm_id            uuid not null,
  tenant_id          uuid,                  -- null = catálogo público
  norm_type          text not null,
  norm_number        text not null,
  titulo             text not null,
  valid_from         date not null,
  valid_to           date,                  -- null = todavía rige
  is_current         boolean not null,
  content_hash       text not null,
  official_url       text,
  sincronizado_en    timestamptz not null default now()
)

fragmento (
  id                 bigserial primary key,
  article_id         uuid not null,         -- id del artículo en el backend
  version_id         uuid not null references version_norma(id) on delete cascade,
  tenant_id          uuid,
  article_type       text not null,
  article_number     text,
  parte              int not null default 1,
  total_partes       int not null default 1,
  ruta               text not null,         -- "Ley 19.300 › Título II › Párrafo 2º › Artículo 11"
  texto              text not null,
  embedding          vector(:dimension) not null,
  modelo_embedding   text not null,
  busqueda           tsvector generated always as (to_tsvector('spanish', ruta || ' ' || texto)) stored,
  unique (article_id, parte)
)

sincronizacion (
  fuente             text primary key,      -- 'catalogo'
  updated_at_maximo  timestamptz,           -- el máximo visto, no la hora de la corrida
  ultima_corrida     timestamptz,
  resultado          jsonb
)
```

Índices: HNSW coseno sobre `embedding`, GIN sobre `busqueda`, btree sobre
`(norm_type, norm_number, article_number)` vía `version_norma`, y `(tenant_id)` parcial.

Políticas RLS en `version_norma` y `fragmento`:
`tenant_id is null or tenant_id = current_setting('app.tenant_id')::uuid`.

## Criterios de aceptación

```gherkin
# language: es
Característica: La base del AI Service aísla por empresa aunque el código se equivoque

  Escenario: Un fragmento privado no se ve desde otra empresa
    Dado un fragmento público y un fragmento con tenant_id "A"
    Cuando se consulta la tabla fragmento con app.tenant_id "B" y sin ningún WHERE
    Entonces se obtiene solo el fragmento público

  Escenario: Sin tenant fijado no se ve nada privado
    Dado un fragmento con tenant_id "A"
    Cuando se consulta sin fijar app.tenant_id
    Entonces no se obtiene ese fragmento

  Escenario: El rol del servicio no puede saltarse RLS
    Entonces el rol de conexión del servicio no tiene BYPASSRLS ni es dueño de las tablas

  Escenario: La base se reconstruye desde cero
    Dada una base vacía con las migraciones aplicadas
    Cuando corre la sincronización completa
    Entonces el conteo de fragmentos coincide con el de artículos vigentes del backend

  Escenario: valid_to nulo significa vigente
    Dada una versión con valid_to nulo e is_current verdadero
    Cuando se filtra por vigentes a hoy
    Entonces esa versión aparece
```

## Pruebas
- **Integración** con PostgreSQL + pgvector en contenedor (testcontainers o el compose):
  migraciones desde cero, RLS con dos tenants, rol sin bypass.
- El escenario 4 corre contra el compose de Ambienta con el catálogo sincronizado.

## Implementación (20/09/2026)

Implementado en `servicio/migraciones/` y `servicio/src/ambienta_ia/conocimiento/`. Pruebas:
`tests/integracion/test_base_conocimiento.py` (RLS con dos empresas y sin ningún `WHERE`, roles
sin bypass, el de consulta no escribe, el sincronizador no escribe filas privadas).

El esquema vigente es el de `migraciones/001_esquema.sql`. Agrega sobre lo de arriba:
`clave_norma` ("ley/19300") y `numero_normal` ("10 bis") para la búsqueda exacta, y un índice
único por `norm_id` porque se indexa una sola versión por norma.

## Contra el backend real (21/09/2026)

Ver [`prueba-contra-ambienta/`](../prueba-contra-ambienta/README.md).
- El arnés usa una base propia: los roles son del servidor y las pruebas les reescriben la clave.
  **Las pruebas tienen que correr contra un PostgreSQL propio.**
