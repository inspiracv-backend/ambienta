# Diseño: Ingesta del catálogo normativo desde la BCN

## 1. Dos fuentes, y por qué se empieza por la que funciona

| Fuente | Qué entrega | Estado hoy |
|---|---|---|
| **SPARQL abierto** (`datos.bcn.cl/sparql`) | Metadatos, relaciones entre normas, versiones | **Responde 200 sin autenticación** |
| **API de Ley Chile** (`bcn.cl/leychile/api`) | Presumiblemente el texto completo | **Clave emitida pero "No activa"**: 401 |
| Web service XML de 2009 (`obtxml`) | Texto completo de la norma | 401 |

Se construye contra el SPARQL. No es una solución de segunda: **es la única que
se puede probar hoy**, y trae justo lo que las tablas vacías necesitan.

**Qué se pierde:** el articulado. Sin él, `legal_articles` sigue vacía y la
matriz legal no se puede evaluar artículo por artículo. Es una limitación real y
hay que decirla, no taparla.

**Por qué igual vale la pena ahora:** `leychileCode` es la bisagra. Es el mismo
identificador que pide el web service XML (`idNorma`), así que guardarlo hoy
convierte el día que la clave se active en "traer el texto", no en "volver a
mapear todo".

## 2. El mapeo

Comprobado contra la Ley 20.920 el 13-ago-2026:

| Propiedad BCN | Columna | Nota |
|---|---|---|
| `bn:leychileCode` | `external_norm_id` | **La bisagra con el XML** |
| `bn:hasNumber` | `norm_number` | |
| `dc:title` | `title` | |
| `bn:publishDate` | `publication_date` | |
| `bn:promulgationDate` | `promulgation_date` | |
| `bn:type` | `norm_type` | Viene como URI: `…/tipo#ley` |
| `bn:hasXmlDocument` / `hasHtmlDocument` | `official_url` | |
| URI de la norma | `issuing_body` | El ministerio va en la ruta |
| `frbr:subject` | `subjects` | |
| respuesta completa | `source_payload` | Cruda, para poder remapear sin volver a pedir |

### Las relaciones dejan de ser un campo vacío

`modifiesTo`, `isModifiedBy`, `recasts`, `isRecastedBy`, `rectifies`,
`isRectifiedBy`, `regulates`, `isRegulatedBy` → `legal_relations`.

Es lo que `docs/estado-crud-base-de-datos.md` describe como *"relaciones entre
normas (deroga, modifica, complementa). Las declara la ley, no el usuario"*. Con
esto se leen de la fuente oficial en vez de la memoria de quien cargó la lista.

### Las versiones

`versionOf`, `hasVersion`, `versionDate`, `isLatestVersion` →
`legal_norm_versions`. Importa para cumplimiento: **qué versión estaba vigente
cuando se hizo una evaluación** no es lo mismo que la vigente hoy.

## 3. La misma norma vuelve varias veces

La consulta de la Ley 20.920 devolvió **tres filas idénticas salvo la URI**: el
modelo RDF distingue obra, expresión y manifestación, y una tercera variante
llevaba el sufijo `/es@2016-06`.

**Se deduplica por `leychileCode`**, no por URI. La URI identifica una
representación; el código identifica la norma. Deduplicar por URI dejaría tres
filas de la misma ley y rompería la clave de negocio.

**Qué se pierde:** la distinción entre versiones idiomáticas. Hoy no la
necesitamos —todo es español de Chile— y `source_payload` conserva lo crudo por
si algún día importa.

## 4. Idempotencia

Sincronizar dos veces no debe duplicar nada ni pisar lo que un humano ajustó.

- Se busca por `external_norm_id`; si existe, se actualiza; si no, se crea.
- **Los campos que la BCN es dueña se refrescan** (título, fechas, relaciones).
- **Lo que decidió una persona no se toca**: qué artículos entran en el cálculo,
  a qué plantas aplica, quién es responsable. Es la misma regla que ya sigue la
  sincronización de usuarios: un cambio río arriba no revierte una decisión
  tomada acá.

## 5. Lo que no se toca: el catálogo es global

`legal_norms` es catálogo compartido, sin `tenant_id`, y **la ley es igual para
todas las empresas**. La ingesta escribe ahí y en ninguna tabla de empresa.

Eso tiene una consecuencia que conviene tener presente: **una norma derogada río
arriba cambia el cumplimiento de todas las empresas a la vez**, sin que nadie
haya tocado nada. Por eso la bitácora no es opcional.

## 6. Dónde corre

Lo correcto es el worker: es un job periódico, no una petición de usuario. Pero
`apps/worker` **es una carpeta vacía**.

Mientras tanto, un comando que se dispara a mano, con la lógica **separada de
cómo se invoca**, para que mudarla al worker sea cambiar el disparador y nada
más. Es la misma separación que ya se usó entre el router del webhook y su
servicio, y por la misma razón: poder probarla sin levantar la infraestructura.

## 7. La bitácora

`norm_sync_runs` registra cada corrida: cuándo empezó, cuántas normas trajo,
cuántas creó, cuántas actualizó y qué falló.

**Sin esto la ingesta es una caja negra.** Una sincronización que trae cero
normas porque la consulta cambió se ve exactamente igual que una que no tenía
nada nuevo que traer.

Esa tabla ya está descrita como *"la escribe el sistema; editarla sería
falsificar el registro de qué se sincronizó"*, así que se escribe y no se expone
como recurso editable.

## 8. Riesgos

| Riesgo | Mitigación |
|---|---|
| Son 748.783 normas | Traer un subconjunto acotado por materia y organismo. **Es decisión de negocio**, y sin ella la ingesta no debe correr suelta |
| El endpoint público puede caerse o limitar | Reintento con espera creciente, y que un fallo deje bitácora en vez de romper. La falta de datos nuevos no es una emergencia |
| La consulta SPARQL se rompe si cambia la ontología | Fijar el prefijo y validar que la respuesta trae los campos esperados. Cero resultados **no es** un éxito silencioso |
| La clave nunca se activa | El adaptador sigue sirviendo: entrega metadatos y relaciones. Solo el articulado queda pendiente |
