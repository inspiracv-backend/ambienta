# Design: la vinculación transversal

## Por qué el vínculo es polimórfico y se queda así

`entity_documents` guarda `entity_type` + `entity_id` sin clave foránea. La
alternativa —una columna nullable por cada entidad vinculable— daría trece
columnas, doce de ellas NULL en toda fila, y un CHECK para exigir que
exactamente una esté puesta. Cada entidad nueva sería una migración con
`ALTER TABLE`.

El costo del polimorfismo es exactamente el defecto que este cambio arregla: la
base **no puede** comprobar que el `entity_id` exista, así que tiene que
comprobarlo la aplicación. Se acepta el costo y se paga en un solo lugar.

## Dónde vive la comprobación

En `services/vinculos_de_documentos.py`, no en el router, y con **un mapa
explícito** de `entity_type` → modelo:

```python
ANCLAJES: dict[str, type] = {
    "obligation": Obligation,
    "audit": Audit,
    ...
}
```

Tres consecuencias de escribirlo así, todas buscadas:

1. **El mapa y el CHECK de la base tienen que coincidir**, y hay una prueba que
   lee `db/01_schema.sql` y lo exige. Es el mismo criterio que la prueba de las
   etapas del CRM y la de los Dockerfile: dos listas que deben decir lo mismo,
   comparadas por una máquina y no por la memoria de alguien.
2. **Un `entity_type` sin modelo no pasa la comprobación**, en vez de pasarla en
   silencio. Un `dict.get()` que devuelve `None` y se interpreta como «no hay
   nada que comprobar» sería una puerta abierta con forma de descuido.
3. La comprobación usa la sesión con RLS declarado, así que **la respuesta la da
   Postgres**: si la fila es de otra empresa, la consulta devuelve cero.

## Las dos negativas se ven iguales

`422` con el mismo mensaje para «no existe» y para «existe y es de otra
empresa». Distinguirlas convertiría el endpoint en un oráculo: mandando ids al
azar se podría averiguar cuáles corresponden a registros reales de otras
empresas. Es la misma decisión que se tomó en `validar_visible` y en el 403 del
gestor.

## El sentido inverso: una ruta, no trece

`GET /documents/vinculados?entity_type=obligation&entity_id=<uuid>`.

La alternativa era `GET /obligations/{id}/documentos` y su equivalente en cada
router. Serían **trece endpoints** que hacen la misma consulta, y trece lugares
donde olvidarse de la comprobación de visibilidad el día que se agregue el
catorce. Con una sola ruta, agregar una entidad vinculable es agregar una línea
al mapa.

Lo que se cede es descubribilidad: quien lea el router de obligaciones no verá
que existe. Lo compensa que el mismo mapa que valida es el que documenta.

## `legal_norm` y `process`: por qué son distintos del resto

Los once tipos que ya estaban son **todos de empresa**: llevan `tenant_id` y
RLS, así que la comprobación de visibilidad es la misma para todos.

`legal_norms` **es catálogo global**: no tiene `tenant_id`. Comprobarla con la
sesión del tenant devolvería cero filas siempre y **ninguna norma se podría
vincular** — el modo de fallo silencioso que describe CLAUDE.md §4. Se comprueba
con la sesión sin tenant, y el mapa lo dice explícitamente en vez de dejarlo
implícito en el modelo.

`processes` sí es de empresa y no tiene nada especial; faltaba y ya está.

## Lo que este cambio deliberadamente no hace

**No borra vínculos cuando se borra la entidad apuntada.** Sin clave foránea no
hay `ON DELETE`, y escribir un disparador por cada tabla sería trece
disparadores. El borrado del sistema es lógico (`deleted_at`), así que la
entidad sigue existiendo; el vínculo que quede colgando se ve como lo que es —un
apuntador a algo retirado— y eso es preferible a que un `DELETE` en cascada
haga desaparecer en silencio la prueba de que algo estuvo respaldado.
