# Diseño: CRUD completo de los recursos de negocio

## 1. Dónde está la palanca

Los recursos son **instancias directas de `CRUDBase`, sin sobreescribir nada**:

```python
crud_department = CRUDBase[Department, DepartmentCreate, DepartmentUpdate](Department)
```

Veintiséis instanciaciones idénticas. Eso significa que arreglar `CRUDBase`
arregla los veintiséis desde un solo archivo — y que un error ahí se propaga
igual de rápido. Toda la estrategia de este cambio descansa en esa simetría: se
corrigió el genérico primero y recién después se expusieron los routers.

**Las tablas no se crean desde SQLAlchemy.** No hay `Base.metadata.create_all()`
en ninguna parte. El esquema vive en `db/01_schema.sql` porque incluye RLS,
triggers y constraints que un ORM no genera. SQLAlchemy se usa para consultar,
no para definir.

## 2. Borrado lógico

### La decisión

`remove()` marca `deleted_at` y las lecturas excluyen lo marcado desde un único
punto.

**Por qué la fecha la pone la base y no Python:** para que sea comparable con
`created_at`, que también sale del reloj del servidor. Con dos relojes distintos
un registro puede aparecer borrado antes de existir, y ese desorden solo se
descubre auditando.

### `get()` tuvo que dejar de usar `db.get()`

No fue estilo. `db.get()` resuelve por clave primaria y por el mapa de
identidad de la sesión, así que **nunca pasa por un `WHERE`** donde filtrar
`deleted_at`. No había forma de agregarle la condición: había que cambiar a
`select()`.

**Qué se pierde:** `db.get()` puede resolver desde el mapa de identidad sin
tocar la base. Con `select()` siempre hay consulta. A cambio, la fila borrada
deja de verse, que es el punto.

### Borrar dos veces

No es error ni mueve la fecha original. `get()` ya no encuentra la fila, el
segundo intento devuelve `None` y el router responde 404.

**Por qué 404 y no 204:** desde fuera, borrar algo ya borrado y borrar algo que
nunca existió son el mismo hecho, y responder distinto delataría cuál de los dos
es. La alternativa —204 idempotente— es más amable con clientes que reintentan,
pero convierte el endpoint en un detector de identificadores válidos.

## 3. Referencias cruzadas: el hallazgo que cambió el resto

### Las FK de Postgres no pasan por RLS

`fk_departments_facility` solo exige que exista una fila en `facilities` con ese
identificador. **No mira el tenant.** Un `PATCH` apuntando a la planta de otra
empresa satisface la restricción y deja la fila apuntando fuera.

El daño no es solo la fila incoherente. Es un **oráculo de existencia**: quien
prueba identificadores al azar distingue "no existe" (falla la FK) de "existe
pero es de otro" (pasa), y con eso enumera identificadores ajenos sin verlos
nunca.

### El contrato

Leer el destino con la sesión del tenant: si RLS no lo ve, para esta empresa no
existe. **422 en los dos casos, deliberadamente.**

**Qué se pierde:** un mensaje de error menos útil para quien se equivocó de
buena fe. Es el precio de cerrar el oráculo, y es barato comparado con permitir
la enumeración.

Esto aplica a **cualquier tabla con clave foránea editable**, no solo a las de
este cambio. Es la regla que más lejos llega de todo lo decidido acá.

### Ciclos en las jerarquías

No hay `CHECK` contra `parent = id` propio ni contra A→B→A. Un ciclo **no rompe
el `INSERT`**: cuelga a quien recorra el árbol después.

Se valida en la aplicación antes de escribir, recorriendo la cadena de padres.

**Qué se pierde frente a resolverlo en la base:** una validación en la
aplicación no protege de escrituras manuales por `psql`. Un `CHECK` no puede
expresar el ciclo indirecto; haría falta un trigger con recursión, y eso paga
costo en cada escritura de todas las jerarquías para un caso que en la práctica
llega por la API.

## 4. Tablas de asociación

Tres tablas tienen clave compuesta y **no columna `id`**:
`audit_participants`, `equipment_operators`, `facility_processes`.

Eran un fallo latente: `CRUDBase` asume una columna `id` y habría dado un
`AttributeError` a mitad de consulta el día que alguien las conectara. Ningún
router las usaba, así que nadie lo sabía.

### Dirección del recurso

`/padres/{padre_id}/hijos/{hijo_id}` — los dos identificadores forman la
dirección. **Qué se pierde frente a inventar un `id` sintético:** habría que
migrar el esquema y la clave compuesta ya expresa exactamente la regla de
unicidad que se quiere.

### Revivir en vez de duplicar

Recrear una asociación borrada la **revive**. Sin eso, quitar un proceso de una
planta y volver a ponerlo choca contra la clave única —la fila borrada sigue
ahí— y deja al usuario ante un 409 del que no puede salir desde la interfaz.

**La alternativa** —hacer la clave única parcial sobre `deleted_at IS NULL`—
funcionaría, pero exige migrar los índices de las tres tablas y deja el historial
con filas repetidas. Revivir conserva una sola fila con su fecha de creación
original.

## 5. Errores

`IntegrityError` se traduce por **tipo de excepción, no por el texto del
mensaje**:

| Restricción violada | Respuesta |
|---|---|
| Unicidad | 409 |
| `CHECK`, `NOT NULL`, clave foránea | 422 |

**Por qué no por el texto:** las cadenas de PostgreSQL cambian entre versiones y
con el idioma del servidor. Un mapeo por subcadena se rompe en una actualización
menor sin que ninguna prueba lo note, y el síntoma es un 500 donde antes había
un 409.

## 6. El contrato OpenAPI

Las respuestas de error **se derivan de la forma de la ruta**:

- el **401** sale de que la operación declare `security`
- el **404** sale de que la ruta tenga un `{parámetro}` de path

**Qué se pierde:** control fino sobre casos particulares, que hay que agregar a
mano cuando aparezcan. A cambio, una ruta nueva nace documentada; declararlas
una por una en casi cien rutas garantiza que se desincronicen.

## 7. Dos fallos de sesión que aparecieron por el camino

**`expire_on_commit` venía en `True`.** Leer cualquier atributo al serializar la
respuesta de un `POST` disparaba un `SELECT` de refresco **en una transacción
nueva, sin rol y sin tenant declarado**. Con el rol acotado eso devuelve cero
filas; con el dueño de la base habría devuelto las de todas las empresas.
Apagado.

**El tenant muere con la transacción.** `SET LOCAL` se va en cada `commit`, así
que cualquier consulta posterior ve cero filas. No hay arreglo elegante: es una
regla de escritura —no consultar después de `commit`— y está en `CLAUDE.md`.

## 8. Lo que la capa todavía no hace

- **`created_by` y `updated_by` nunca se llenan.** `create` solo inyecta
  `tenant_id`; `update` copia los campos del esquema. RNF-08 pide trazabilidad.
- **`get_multi` no filtra por ninguna columna**, así que cada listado acotado por
  padre se escribe a mano — y ahí es fácil olvidar `deleted_at`.
- **`X | None = None` en los `Update` no distingue** "no enviado" de "enviado
  como null". Sobre una columna obligatoria eso intenta escribir null.
