## Context

Ver `proposal.md — Why` para la motivación. Lo que importa acá es el estado del
modelo, que condiciona todo lo demás.

La cadena de cumplimiento está construida y funciona:

```
legal_norms → legal_norm_versions → legal_articles
      ↓
  matrix_norms (tenant_id, RLS) → article_compliance → obligations → avisos
```

Y tiene una propiedad que este cambio rompe. Medido el 4-sep contra la base:

| Tabla | `tenant_id` | RLS |
|---|---|---|
| `legal_norms` | no | **no** |
| `legal_articles` | no | **no** |
| `matrix_norms` | sí | sí |
| `article_compliance` | sí | sí |

El comentario de la tabla lo declara: *«Catalogo global: sin tenant_id a
proposito. La norma es la misma para todos los tenants; lo que se registra por
empresa es la aplicabilidad y el cumplimiento.»* Es una decisión correcta para
una ley y falsa para una RCA.

Dos piezas ya existen y hoy no las usa nadie: el permiso `catalog.write`
sembrado como *«Cargar RCAs e ISO del tenant»*, y la fila de `norm_sources`
`('RCA', 'Resoluciones de Calificacion Ambiental', 'https://seia.sea.gob.cl',
'{"carga":"manual_pdf"}')`. La intención estaba escrita; la estructura la
contradice.

## Goals / Non-Goals

**Goals:**

- Que una RCA cargada por la empresa A sea invisible para la empresa B, y que
  eso lo garantice Postgres y no un `if` de la aplicación.
- Que una norma propia confirmada entre a la cadena existente sin código nuevo
  aguas abajo.
- Que ninguna omisión de una extracción automática pueda terminar como
  cumplimiento verificado.
- Que el módulo funcione con carga manual, sin parser.

**Non-Goals:**

- No se construye un parser genérico de documentos legales. El alcance es RCA
  del SEA e ISO con cláusulas numeradas.
- No se resuelve el versionado de RCAs modificatorias en esta entrega (ver
  Preguntas abiertas).
- No se toca el flujo de sincronización con la BCN más allá de excluir lo
  propio.
- No se implementa extracción asistida por IA. Eso vive en la épica de
  AmbiAgent y depende de este modelo, no al revés.

## Decisions

### 1. `tenant_id` nullable en las tablas del catálogo, no tablas paralelas

La alternativa era `tenant_legal_norms` y `tenant_legal_articles` separadas.

Se descarta porque **toda la cadena aguas abajo apunta a `legal_articles.id`**:
`article_compliance`, las obligaciones que cuelgan de ella, los reportes y el
cálculo de cumplimiento. Con tablas paralelas cada uno de esos puntos necesita
saber de qué tabla viene el artículo, y eso es una condición nueva en cada sitio
que hoy no la tiene. La primera que se olvide produce una RCA evaluable que no
aparece en el porcentaje de cumplimiento — el tipo de error que este repositorio
viene persiguiendo.

Con `tenant_id` nullable, `NULL` significa "del catálogo compartido" y el resto
del sistema no se entera de nada.

**Lo que se cede:** una columna nullable es más fácil de olvidar en una consulta
nueva que una tabla con otro nombre. Se compensa con RLS, que actúa aunque la
consulta no la mencione, y con una prueba de aislamiento como la que ya existe
para el resto.

### 2. La política de RLS admite lo global y lo propio en la misma tabla

```
tenant_id IS NULL OR tenant_id = current_tenant_id()
```

Es lo que permite que el catálogo compartido siga siendo de todos mientras lo
propio queda acotado. La alternativa —RLS estricta por tenant— dejaría la ley
invisible para todos, porque ninguna fila del catálogo tiene tenant.

**Ojo con el `WITH CHECK`.** La lectura admite `NULL`; la escritura **no puede**,
o cualquier empresa podría insertar una norma global. El `WITH CHECK` va sobre
`tenant_id = current_tenant_id()`, así que crear catálogo compartido queda fuera
del alcance de una sesión de empresa — como debe ser: eso lo hace la
sincronización con la BCN, que corre con otro contexto.

### 3. Un origen nuevo en `matrix_norms`, no reutilizar "agregada a mano"

`matrix_norms` ya distingue lo que propuso el cálculo de lo que agregó una
persona. La tentación es guardar la RCA como "agregada a mano" y no tocar nada.

Se descarta porque son cosas distintas con reglas distintas: lo manual es una
decisión revisable de la empresa, y lo propio es una imposición de la autoridad.
El día que alguien cambie el criterio sobre lo manual —por ejemplo, permitir que
un recálculo lo retire tras confirmación— se llevaría la RCA por delante sin que
nadie lo haya pedido. Un valor propio hace que ese cambio no la alcance.

### 4. La extracción escribe candidatos en su propia tabla

Los candidatos no son artículos en estado borrador dentro de `legal_articles`.
Viven aparte, con el fragmento de origen, su ubicación en el documento y su
estado de revisión.

La alternativa —artículos con `status = 'propuesto'`— mete filas sin confirmar en
la tabla de la que cuelga todo el cumplimiento. Basta una consulta que olvide
filtrar por estado para que un candidato sin revisar aparezca como artículo
evaluable, y ahí el "propone, no crea" deja de ser cierto sin que nada falle.
Separar las tablas hace que ese olvido sea imposible en vez de improbable.

**Lo que se cede:** una tabla más y un paso de copia al confirmar. Barato.

### 5. La norma propia cuelga de una `document_version`, no de un archivo suelto

El control documental ya sube a B2 con el `tenant_id` en la ruta, guarda hash y
tamaño reales del objeto, y tiene ciclo de vida con aprobación. Reusarlo da
trazabilidad ante un fiscalizador y evita un segundo camino de subida con sus
propias reglas de aislamiento.

**Lo que se cede:** cargar una RCA obliga a pasar por el flujo de documentos, que
es un paso más. A cambio, el PDF que respalda cada compromiso siempre existe y
siempre es el mismo que se revisó.

### 6. Extracción de texto en la API, síncrona y acotada

Para la primera entrega la extracción corre en el request, con un tope de tamaño
y páginas, y devuelve los candidatos. No hay cola ni worker.

La alternativa —encolarlo— es lo correcto para documentos grandes, y hoy no
existe worker: `apps/api/app/tareas/` con cron es lo que hay. Montar una cola
para esto sería infraestructura nueva antes de saber si hace falta.

**Lo que se cede:** una RCA de 200 páginas puede pasarse del tiempo de respuesta.
Por eso el tope es explícito y el error dice qué pasó, y por eso la carga manual
existe como camino independiente. Si aparece el caso, la extracción se mueve a
`app/tareas/` sin cambiar el modelo ni las specs.

### 7. La sincronización con la BCN ignora lo propio, y hay que hacerlo explícito

`bcn.sincronizar()` adopta normas sembradas que coinciden por número y título en
vez de duplicarlas. Una RCA con número "RCA-045/2018" no va a coincidir con nada
de la BCN, pero la protección no puede depender de eso: basta un criterio de
coincidencia más laxo en el futuro para que la sincronización pise la RCA de una
empresa. El filtro por `tenant_id IS NULL` va en la consulta, y con prueba.

## Risks / Trade-offs

**Activar RLS sobre una tabla que hoy no la tiene puede vaciar pantallas** →
`legal_norms` tiene 24 filas y `legal_articles` 689, todas con `tenant_id` en
`NULL`, así que la política las sigue mostrando. La migración se aplica y se
comprueba con un conteo antes y después; si el número baja, la política está mal.

**El `GRANT` y la política no se heredan** → una tabla que cambia en una
migración no recibe el bucle de políticas ni el `GRANT ON ALL TABLES` de
`01_schema`, que corrieron una sola vez. La migración declara los suyos. Es la
trampa documentada en CLAUDE.md y ya costó tiempo antes.

**La revisión humana se vuelve un trámite de aceptar todo** → si la pantalla no
muestra el fragmento original al lado, quien revisa acepta en bloque y la
confirmación no protege nada. Por eso el fragmento y su ubicación son requisito
de spec, no un detalle de interfaz.

**Un PDF escaneado no deja extraer texto** → se informa como tal y la norma queda
disponible para carga manual. Lo que no puede pasar es devolver cero candidatos
sin distinguir "no hay compromisos" de "no se pudo leer": es la misma confusión
entre "no hay" y "no se supo" que el resto del sistema ya evita.

**La licencia de las normas ISO** → guardar el texto íntegro de un documento del
INN en un SaaS multi-tenant tiene implicancias de licenciamiento. Hasta que haya
decisión, el modelo admite guardar solo estructura y tareas, que es el camino sin
riesgo. Ver Preguntas abiertas.

**El parser da una falsa sensación de completitud** → alguien puede asumir que lo
extraído es todo lo que la RCA exige. La pantalla dice cuántos candidatos salieron
y de qué secciones, y el estado de la norma distingue "revisada" de "cargada".

## Migration Plan

1. Migración `db/NN_normativa_propia.sql`, idempotente: agrega `tenant_id` a
   `legal_norms` y `legal_articles`, crea la tabla de candidatos, habilita RLS
   con `FORCE` en las tres, declara sus políticas y sus `GRANT` a `ambienta_app`.
2. Registrarla en **las cinco listas**: `docker-compose.yml`,
   `docker-compose.prod.yml`, `db/run.sh`, `db/README.md` y el bucle de
   `.github/workflows/ci.yml`.
3. Comprobar el conteo del catálogo antes y después. Si baja, revertir.
4. API y pantallas. La carga manual primero; la extracción después, detrás del
   mismo flujo de revisión.

**Reversión:** la migración no borra datos. Revertir es quitar las políticas y la
columna; las normas propias que se hayan cargado quedarían visibles entre
empresas, así que revertir **exige borrar antes las filas con `tenant_id` no
nulo**. Queda escrito en la propia migración.

## Open Questions

Estas tres se pueden responder sin cambiar las specs ni el modelo:

1. **¿Cuál es el tope de tamaño y páginas para la extracción síncrona?** Se fija
   midiendo con RCAs reales. Mientras tanto, un tope conservador.
2. **¿Qué biblioteca de extracción de texto?** Decisión de implementación; el
   contrato es "de este PDF salen estos fragmentos con su ubicación".
3. **¿La pantalla de revisión permite crear la obligación en el mismo paso?**
   Conveniencia de interfaz. El artículo y su evaluación ya quedan creados; la
   obligación se puede crear después por el camino que ya existe.

Las que **no** son diferibles y bloquean la implementación —el texto completo de
las ISO, qué secciones de una RCA son exigibles, y qué pasa con una RCA
modificatoria— están en `proposal.md — Decisiones que necesita el equipo`. La
tercera afecta al modelo, así que hay que responderla antes de la tarea de
versionado; las dos primeras, antes de escribir el parser.
