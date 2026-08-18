# Design: Normativa aplicable por empresa

## Context

Ver `proposal.md` — Why.

Lo que condiciona el diseño y no es negociable:

- **RLS es la única barrera.** Ninguna consulta de la aplicación filtra por
  `tenant_id` (`CLAUDE.md §4`). El catálogo normativo y su clasificación por
  sector **no llevan `tenant_id` a propósito**: la ley es la misma para todas las
  empresas. La matriz sí lo lleva.
- **`db/01_schema.sql` no es una migración.** Todo cambio de esquema necesita
  además un `db/NN_*.sql` idempotente, y si crea una tabla debe declarar **su
  propia política RLS y sus GRANT**: el bucle de políticas de `01_schema` corre
  una sola vez.
- **El articulado cuelga de la versión, no de la norma.** `legal_articles` tiene
  `norm_version_id`. Una empresa evalúa artículos de una versión concreta, y por
  eso el aviso de versión nueva no puede ser un simple "cambió el texto".
- **La evaluación ya funciona de punta a punta** desde el 17-ago: `article_compliance`
  se lee y se escribe desde la matriz legal. Este cambio la alimenta, no la toca.

## Goals / Non-Goals

**Goals:**

- Que el perfil de una empresa sea un dato cruzable, no una descripción.
- Que la clasificación norma↔sector sea administrable, fundamentada y auditable.
- Que generar la matriz sea **idempotente**: correrlo dos veces no duplica ni pisa.
- Que toda norma en una matriz pueda responder "¿por qué está acá?".

**Non-Goals:**

- **Clasificar normas automáticamente.** El esquema deja lugar
  (`source='automatic'`, `confidence`) pero este cambio no lo implementa.
- **Recalcular solo.** No hay proceso en segundo plano: el recálculo se dispara
  desde la interfaz o desde el alta de la empresa. El worker no existe todavía.
- **Resolver conflictos entre versiones.** Se avisa que hay versión nueva; migrar
  las evaluaciones de una versión a otra es otro problema y otro cambio.

## Decisions

### El sector va como referencia al catálogo, no como enum ni como texto

**Decisión:** `tenants.sector_id` apunta a la tabla `sectors` que ya existe.
`business_activity` se conserva sin tocar.

**Por qué no un enum:** agregar un sector sería una migración. En Chile la
clasificación de referencia (CIIU) tiene cientos de entradas y cambia.

**Por qué no seguir con el texto libre:** es exactamente lo que impide cruzar.

**Por qué se conserva `business_activity`:** el giro que la empresa declara ante
el SII no siempre coincide con el sector regulatorio, y perder ese dato para
"normalizar" borraría lo que la persona escribió.

**Verificado el 18-ago-2026: la tabla ya existe y sirve tal cual.** `sectors`
está en `db/01_schema.sql`, la referencia `norm_sectors.sector_id`, y **está
sembrada con 8 secciones CIIU** — entre ellas `C · Industria manufacturera`, que
es justamente el caso que motivó este cambio. Tiene `parent_id`, así que admite
bajar a subclases cuando haga falta.

**No se crea ninguna tabla de sectores.** Solo se agrega `tenants.sector_id`
apuntando a la que ya está.

### El tamaño va como tramo, no como número exacto

**Decisión:** `tenants.size_bracket` con valores cerrados (micro, pequeña,
mediana, grande).

**Por qué:** la normativa se escribe por tramo, no por número. Un umbral legal
dice "empresas de más de 50 trabajadores", y guardar 47 obliga a que cada regla
reimplemente el umbral. El tramo se declara una vez.

**Alternativa considerada:** guardar el número exacto y derivar el tramo. Se
descarta porque el número cambia cada mes y nadie lo actualiza — el dato quedaría
viejo y el filtro daría resultados falsos sin que se note.

### El cálculo devuelve una propuesta; generar la matriz es un acto aparte

**Decisión:** dos operaciones distintas. Una **calcula y muestra** la normativa
aplicable; otra **la aplica** a la matriz.

**Por qué:** el mentor pidió "un check de normativas recomendadas". Un check es
una revisión humana antes de comprometer. Generar la matriz de golpe al crear la
empresa le daría cientos de artículos a evaluar sin que nadie mirara si tienen
sentido.

**Trade-off:** un paso más en el alta. Se acepta: la matriz es el corazón del
producto y equivocarla cuesta más que un clic.

### La matriz se sincroniza, no se reemplaza

**Decisión:** el recálculo compara lo que hay contra lo que corresponde, y
**solo agrega**. Lo que ya no aplica se **marca**, nunca se borra. Lo agregado a
mano se respeta siempre.

**Por qué:** borrar una norma evaluada elimina la evidencia de que en su momento
se evaluó. Un fiscalizador que revisa 2026 en 2028 necesita ver lo que regía
entonces.

**Cómo se distingue:** una columna nueva `matrix_norms.inclusion_source`
(automático/manual). El responsable ya lo da `created_by`.

**Corregido al implementar (18-ago):** la primera versión de esta migración
agregaba cuatro columnas a `matrix_norms`. **Tres ya existían**:
`selected_version_id` —con el comentario *"Versión congelada usada para evaluar.
Sin esto no se puede reconstruir una evaluación pasada"*— cubre la versión;
`created_by` cubre el responsable; y `applicability` con `not_applicable` más
`applicability_reason` cubre lo que deja de aplicar. También estaba ya
`matrix_norms.sector_id`.

Duplicarlas habría dejado **dos fuentes de verdad para el mismo dato**, que es
peor que no tenerlo: la segunda se desactualiza en silencio. Solo se agrega
`inclusion_source`.

### El aviso de versión nueva compara versiones, no fechas

**Decisión:** el aviso sale de comparar `matrix_norms.selected_version_id` —que
**ya existe**— con la versión que hoy tiene `is_current`. No hace falta columna
nueva.

**Por qué no comparar fechas:** una norma puede tener correcciones que no cambian
el articulado. `content_hash` y el versionado ya existen; usar fechas
reintroduciría falsos positivos que el esquema ya evita.

### Escribir la clasificación exige Admin Global

**Decisión:** los endpoints de clasificación usan `exigir_admin_global`; leerlos
no lo exige.

**Por qué:** `norm_sectors` no tiene `tenant_id` — un cambio ahí afecta a **todas**
las empresas. Es la misma regla que ya rige para `/catalog/norms`.

## Risks / Trade-offs

**El filtro solo vale lo que valga la clasificación** → Si nadie clasifica, el
cálculo devuelve vacío y la funcionalidad parece rota. Se mitiga con el escenario
de spec que **distingue explícitamente** "sector sin clasificar" de "sin
obligaciones", y mostrando en la pantalla de administración cuántas normas faltan
clasificar por sector.

**Una clasificación errada se propaga a todas las empresas del sector** → Por eso
`rationale` es obligatorio y queda registrado quién clasificó. Un error con autor
y fundamento se corrige; uno anónimo se discute.

**Generar la matriz puede crear miles de filas** → Una norma con 200 artículos
por 30 normas son 6.000 evaluaciones. Se mitiga generando por norma y no de una
vez, y midiendo con datos reales antes de darlo por bueno. **Si esto resulta
lento, es un problema de diseño de la generación, no de la base.**

**8 secciones CIIU pueden ser muy gruesas** → "Industria manufacturera" abarca
desde una panadería hasta una fundición, y su normativa ambiental no es la misma.
La tabla admite `parent_id`, así que se puede bajar a subclases sin migración.
Se empieza con las 8 y se profundiza si la clasificación resulta demasiado
general — decisión de negocio, con el modelo ya preparado.

## Migration Plan

1. `db/08_perfil_normativo.sql` idempotente: `tenants.sector_id` y
   `tenants.size_bracket`, más `matrix_norms.inclusion_source`. Todas
   **nullable**: las empresas existentes no tienen perfil y eso es correcto.
2. **No hace falta sembrar sectores**: `sectors` ya tiene las 8 secciones CIIU.
3. La API acepta el perfil; el frontend lo pide en el alta.
4. Clasificación de normas — la parte que puede empezar en paralelo con negocio.
5. Cálculo y generación.

**Reversión:** las columnas son nullable y nada las exige. Quitar la
funcionalidad no rompe datos existentes; la matriz sigue funcionando como hoy,
poblada a mano.

## Open Questions

- **¿Los 21 sistemas sectoriales del RETC (#103) son lo mismo que estos sectores
  o una dimensión aparte?** CIIU clasifica la actividad económica; el RETC
  clasifica ante qué sistema se reporta. Probablemente conviven, pero conviene
  confirmarlo antes de mezclarlos en la misma columna.
- **¿El tamaño se declara o se deriva del número de empleados que ya se pida en
  otro lado?** Si mañana existe nómina, el tramo podría calcularse.
