# Proposal: Normativa aplicable por empresa

Fuentes: reunión con el mentor (18-ago-2026) · `db/01_schema.sql` · `openspec/changes/ingesta-normativa-bcn` · RF-17, RF-19, RF-24, RF-29.

## Why

Hoy el sistema sabe **qué normas existen** y sabe **cómo se evalúa un artículo**,
pero no sabe **qué normas le tocan a esta empresa**. Ese hueco es el que impide
que Ambienta se venda solo: al dar de alta una empresa, alguien tiene que armarle
la matriz a mano, decidiendo norma por norma si aplica.

Es también la primera pregunta de un fiscalizador — *cómo determinaron que estas
normas les aplican, y cómo saben que no falta ninguna* — y hoy la única respuesta
posible es "lo decidió una persona, y no quedó escrito por qué".

Tres cosas ya están construidas y esperando exactamente esto:

| Tabla | Qué guarda | Estado |
|---|---|---|
| `norm_sectors` | Qué norma aplica a qué sector, con nivel y confianza | Existe, vacía |
| `tenant_legal_matrices` → `matrix_norms` | La matriz de cumplimiento de una empresa | Existe, se puebla a mano |
| `article_compliance` | La evaluación artículo por artículo | Existe y **ya funciona de punta a punta** |

Lo que falta es el eslabón del medio: **del perfil de la empresa a su matriz**.

## Lo que se comprobó, no lo que se supone

**El catálogo no viene clasificado por sector.** `norm_sectors.source` tiene
`DEFAULT 'analyst'` y un `CHECK (source IN ('automatic','analyst','client'))`, y
hay una columna `confidence` para cuando la clasificación no sea humana. El
esquema ya asumió que **alguien clasifica**. La BCN entrega el texto de la ley,
no a qué industria le aplica.

Esto cambia el plan: el filtro no se "activa", **se alimenta**. Y alimentarlo es
trabajo de negocio, no de código.

**La empresa no tiene dónde declarar su perfil.** `tenants` tiene
`business_activity varchar(300)` — texto libre — y nada más. No hay sector
estructurado ni tamaño. Sin eso no hay entrada para ningún filtro.

**El nivel de aplicabilidad ya está modelado.** `norm_sectors.applicability_level`
distingue `directa`, `indirecta` y `referencial`. Es justo la diferencia entre
"esta norma la debe cumplir" y "esta norma se la recomendamos revisar", que es lo
que pidió el mentor.

## What Changes

- **Perfil normativo de la empresa**: `tenants` gana sector económico
  estructurado y tramo de tamaño. El texto libre `business_activity` se conserva:
  describe el giro, que no es lo mismo que el sector regulatorio.
- **Clasificación de normas por sector**: pantalla y endpoints para que el Admin
  Global declare qué normas aplican a qué sector y con qué nivel, dejando escrito
  el fundamento (`rationale`). Es la alimentación del filtro.
- **Cálculo de normativa aplicable**: dado el perfil de una empresa, el sistema
  determina qué normas le corresponden, separadas en **obligatorias**
  (aplicabilidad directa) y **recomendadas** (indirecta o referencial).
- **Generación de la matriz de cumplimiento**: a partir de esa lista se crea la
  matriz de la empresa con sus normas y los artículos a evaluar, en estado sin
  evaluar.
- **Revisión de vigencia**: el Admin Global puede ver qué normas del catálogo
  tienen una versión más nueva que la que las empresas están evaluando.
- **Trazabilidad de la decisión**: cada norma en la matriz de una empresa registra
  **por qué entró** — qué regla la incluyó, o si la agregó una persona.

## Capabilities

### New Capabilities

- `normativa-aplicable`: cómo el sistema determina qué normas le corresponden a
  una empresa a partir de su perfil, cómo se distingue lo obligatorio de lo
  recomendado, y cómo esa determinación se vuelve una matriz de cumplimiento
  auditable.

### Modified Capabilities

Ninguna. `contrato-de-recursos` y `dashboard` no cambian su comportamiento: los
endpoints nuevos siguen el contrato existente, y el tablero seguirá leyendo las
mismas métricas.

## Impact

**Base de datos.** Columnas nuevas en `tenants` (sector, tamaño). Columna nueva en
`matrix_norms` para el origen de la inclusión. Migración `db/NN_*.sql` idempotente
que **debe declarar su propia política RLS y sus GRANT** si crea alguna tabla —
las de `01_schema.sql` corren una sola vez y una tabla nueva no las hereda.

**API.** Endpoints nuevos bajo `/catalog/norms/{id}/sectors` (administrar la
clasificación) y bajo `/compliance` (calcular y generar la matriz). Escribir la
clasificación exige Admin Global: la ley es la misma para todas las empresas.

**Frontend.** El alta de empresa pide sector y tamaño. Pantalla nueva de
clasificación normativa para el Admin Global. La matriz legal muestra por qué
entró cada norma.

**Lo que este cambio NO hace:**

- **No ingiere desde la BCN.** Eso es `ingesta-normativa-bcn`, que ya existe como
  cambio propio y está bloqueado esperando que la BCN habilite la API key.
- **No genera documentos ni firma.** Los blueprints, el PDF y la firma
  electrónica van por cambio aparte — y la firma avanzada (Ley 19.799) exige un
  prestador acreditado, que es una contratación y no una tarea de desarrollo.
- **No clasifica normas automáticamente.** El sistema provee dónde y cómo
  registrar la clasificación; quién la hace y con qué criterio es una decisión de
  negocio.
