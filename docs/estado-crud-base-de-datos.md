# Estado del CRUD sobre la base de datos

**11-ago-2026.** Todas las cifras de este documento se midieron consultando la
base y el contrato OpenAPI en ejecución, no leyendo código.

---

## 1. El estado previo

### El número que engañaba

Al cerrar el CRUD de los recursos ya expuestos quedó en **17 de 26 recursos
completos**. Es cierto, y es un número que se ve mejor de lo que es: mide *lo
que estaba expuesto*, no *lo que faltaba por exponer*.

La base tiene **52 tablas**. La API exponía **26 recursos**. El cruce real:

| | Tablas |
|---|---|
| Total en la base | **52** |
| Con alguna API | 31 |
| **Sin ninguna API** | **21** |

O sea: **el 40 % de las tablas no tenía forma de tocarse desde la aplicación.**

### De dónde venía el CRUD

Antes de esta tanda de trabajo el estado era peor que "incompleto":

| Operación | Recursos que la tenían |
|---|---|
| Crear | 24 de 26 |
| Listar | 22 de 26 |
| Leer uno | 12 de 26 |
| Actualizar | 15 de 26 |
| **Borrar** | **0 de 26** |

**Ningún recurso tenía borrado.** Y el problema no era solo que faltara el
endpoint: `CRUDBase.remove()` hacía `db.delete()` —borrado **físico**— mientras
el esquema estaba diseñado para borrado **lógico** con `deleted_at` e índices
parciales `WHERE deleted_at IS NULL`. Al mismo tiempo, `get()` y `get_multi()`
no filtraban `deleted_at`.

Las dos mitades estaban mal y se tapaban entre sí, porque ningún router
exponía el borrado. Exponerlo directo lo habría hecho nacer roto: una fila
borrada habría seguido apareciendo en los listados.

También había un endpoint devolviendo **500**: `POST /support/tickets`. Su
columna `ticket_number` es `NOT NULL UNIQUE` y nadie la generaba. Era el único
roto de los 91 — y justo el que sostiene el flujo del Cliente Invitado, cuyo
único propósito es crear solicitudes.

---

## 2. La capa SQLAlchemy

### Cómo está armada

```
routers/   →  reciben el request, validan, responden
crud/      →  CRUDBase genérico, una instancia por modelo
models/    →  SQLAlchemy 2.0, tipado con Mapped[]
```

**Las tablas NO se crean desde SQLAlchemy.** No hay `Base.metadata.create_all()`
en ninguna parte. El esquema vive en `db/01_schema.sql` y se aplica por
migración, porque incluye Row Level Security, triggers y constraints que un ORM
no genera. SQLAlchemy se usa **para consultar, no para definir**.

### El punto de apalancamiento

Los 26 recursos son **instancias directas de `CRUDBase`, sin sobreescribir
nada**:

```python
crud_department = CRUDBase[Department, DepartmentCreate, DepartmentUpdate](Department)
```

Eso significa que arreglar `CRUDBase` arregla los 26 desde un solo archivo — y
que un error ahí se propaga igual de rápido.

### Qué se corrigió

**El borrado pasó a ser lógico.** `remove()` marca `deleted_at` con `func.now()`
—la hora la pone la base, no Python, para que sea comparable con `created_at`— y
las lecturas excluyen lo borrado desde un único punto:

```python
def _visibles(self):
    stmt = select(self.model)
    if self.usa_borrado_logico:
        stmt = stmt.where(self.model.deleted_at.is_(None))
    return stmt
```

**`get()` pasó de `db.get()` a `select()`.** No fue estilo: `db.get()` resuelve
por clave primaria y por el mapa de identidad, así que nunca pasa por un `WHERE`
donde filtrar `deleted_at`. No había forma de agregarle la condición.

**Borrar dos veces no es error** ni mueve la fecha original. `get()` ya no la
encuentra, el segundo intento devuelve `None` y el router responde 404. Desde
afuera, borrar algo ya borrado y borrar algo que nunca existió son el mismo
hecho.

**Aparecieron dos fallos latentes:**

- `EquipmentOperator` tiene clave compuesta (`equipment_id`, `user_id`) y no
  columna `id`. Ningún router lo usaba, pero conectarlo habría dado un
  `AttributeError` a mitad de una consulta. Ahora falla con un mensaje que dice
  qué hacer.
- `expire_on_commit` venía en `True`, así que leer cualquier atributo al
  serializar la respuesta de un POST disparaba un `SELECT` de refresco **en una
  transacción nueva, sin rol y sin tenant**. Apagado.

### Lo que la capa todavía no hace

- **`created_by` y `updated_by` nunca se llenan.** `CRUDBase.create` solo
  inyecta `tenant_id`; `update()` solo copia los campos del esquema. Las
  columnas existen y RNF-08 pide trazabilidad, pero hoy se puede cambiar la
  estructura organizacional sin dejar autor.
- **`get_multi` no filtra por ninguna columna**, así que cualquier listado
  acotado por padre hay que escribirlo a mano — y ahí es fácil olvidar
  `deleted_at`.
- **`X | None = None` en los `Update` no distingue** "no enviado" de "enviado
  como null". En una columna `NOT NULL` eso puede intentar escribir null.

---

## 3. Las tablas no bloqueadas

De las 21 sin API, **11 no dependían de ninguna decisión pendiente**. Medido
antes de empezar:

| Tabla | Modelo | Create | Read | Update | CRUD | Clave |
|---|---|---|---|---|---|---|
| `departments` | sí | sí | sí | sí | sí | simple |
| `processes` | sí | sí | sí | sí | sí | simple |
| `contracts` | sí | sí | sí | sí | sí | simple |
| `integration_accounts` | sí | sí | sí | — | sí | simple |
| `entity_documents` | sí | sí | sí | — | sí | simple |
| `facility_norm_assignments` | sí | sí | sí | — | sí | simple |
| `obligation_templates` | sí | — | sí | — | sí | simple |
| `declaration_templates` | sí | — | sí | — | sí | simple |
| `audit_participants` | sí | sí | sí | — | — | **compuesta** |
| `equipment_operators` | sí | sí | sí | — | sí | **compuesta** |
| `facility_processes` | sí | sí | sí | — | — | **compuesta** |

**20 de las 21 ya tenían su modelo escrito.** Solo faltaba `user_permissions`.

### Entregado

**Ocho de las once**, todas con CRUD completo y verificadas contra la API real:

| Recurso | Ruta | Nota |
|---|---|---|
| `departments` | `/departments` | Plana: `facility_id` es nullable |
| `processes` | `/processes` | |
| `integration_accounts` | `/integrations` | `secret_reference` nunca se devuelve |
| `audit_participants` | `/audits/{id}/participants/{user_id}` | Clave compuesta |
| `equipment_operators` | `/iso14001/equipment/{id}/operators/{user_id}` | Clave compuesta |
| `facility_processes` | `/facilities/{id}/processes/{process_id}` | Clave compuesta |
| `entity_documents` | `/documents/{id}/entities/{vinculo_id}` | Atadura hijo-padre |
| `facility_norm_assignments` | `/facilities/{id}/norms/{asignacion_id}` | Atadura hijo-padre |

Antes de escribir los routers se corrió un análisis con **revisión
adversarial** sobre las 11 tablas. Encontró **30 problemas, 6 graves**. Dos
cambian cómo hay que exponer *cualquier* tabla con clave foránea editable:

#### Las FK de Postgres no pasan por RLS

`fk_departments_facility` solo exige que exista una fila en `facilities` con ese
id. **No mira el tenant.** Un `PATCH` con la planta de otra empresa pasa la
restricción y deja la fila apuntando fuera.

El daño no es solo la fila incoherente. Es un **oráculo de existencia**: quien
prueba identificadores al azar distingue "no existe" (falla la FK) de "existe
pero es de otro" (pasa), y con eso enumera identificadores ajenos sin verlos
nunca.

Se resuelve leyendo el destino con la sesión del tenant: si RLS no lo ve, para
esta empresa no existe. Devuelve **422 en los dos casos**, deliberadamente —
distinguirlos reabriría el oráculo.

#### Nada impedía ciclos en las jerarquías

No hay `CHECK` contra `parent = id` propio ni contra A→B→A. Un ciclo **no rompe
el `INSERT`**: cuelga a quien recorra el árbol después, que es la peor forma de
enterarse.

Las dos validaciones corren en **POST y en PATCH**. El análisis las proponía
solo para el PATCH, pero un POST puede plantar la fila incoherente desde el
principio.

### `contracts`: tenía todo listo y no se expuso

`ContractCreate` acepta `client_tenant_id` del cuerpo, validado solo por la FK.
Una empresa podría crear un contrato **nombrando a otra sin su consentimiento**.
Un contrato bilateral necesita que la contraparte acepte, y ese flujo no existe.

Preferible dejarlo fuera con el motivo escrito que exponer algo que parece
funcionar.

### Pendientes de las 11

`entity_documents` y `facility_norm_assignments` necesitan **atadura hijo-padre**:
anidar la ruta no basta, porque `CRUDBase.get` resuelve por id a secas y
devolvería una fila de otro documento.

Las tres de **clave compuesta** van anidadas bajo su padre —`CRUDBase` lanza
`NotImplementedError` a propósito— y necesitan su propio manejo.

Las **dos plantillas** no tienen `tenant_id`: son catálogo global. Escribirlas
afecta a todas las empresas y `exigir_admin_global` no sirve, porque depende del
tenant. Necesitan un guard distinto.

### Las 5 bloqueadas por RBAC

`roles`, `permissions`, `role_permissions`, `user_roles`, `user_permissions`
pertenecen al change `sistema-actores-roles-rbac`: **0 de 33 tareas y sin
aprobar**. Exponerlas antes de esa decisión es escribir código para tirarlo.

---

## 4. Las tablas que no deberían tener CRUD

Cinco tablas **no deben exponerse como recurso editable**, y conviene que esté
escrito para que nadie lo lea como un olvido.

| Tabla | Por qué no |
|---|---|
| `countries` | Catálogo estático de referencia. Se consulta, no se administra |
| `norm_sectors` | Unión del catálogo normativo: qué normas aplican a qué sector. Se sincroniza desde la fuente oficial |
| `legal_relations` | Relaciones entre normas (deroga, modifica, complementa). Las declara la ley, no el usuario |
| `norm_sync_runs` | Bitácora del sincronizador. La escribe el sistema; editarla sería falsificar el registro de qué se sincronizó |
| `entity_status_history` | Historial *append-only* de cambios de estado. La base **revoca** `UPDATE` y `DELETE` sobre ella |

A ellas se suman, ya expuestas pero **deliberadamente sin CRUD completo**:

| Recurso | Operación que falta | Motivo |
|---|---|---|
| `catalog/*` | crear, editar, borrar | La ley no se edita a mano: se sincroniza desde la BCN |
| `documents/versions` | borrar | Es la evidencia que respalda el cumplimiento; borrarla dejaría sin sustento a las evaluaciones que la citan |
| `support/*/messages` | borrar | Borrar un mensaje suelto vuelve engañosa la conversación con el cliente |
| `audit_log` | editar, borrar | Inmutable por RNF-08 y RNF-25. Lo sostiene la base, no la aplicación |
| `tenants` | borrar | Sin resolver qué significa: marcar la empresa no impide entrar a sus usuarios, así que hoy sería una baja que miente |

### Cómo se sostiene la distinción

No está solo en este documento. `apps/api/tests/test_crud_cobertura.py` **falla
si alguien agrega un recurso a medias sin declarar por qué**:

```python
SIN_CRUD_COMPLETO = {
    "/catalog/norms": "la ley no se borra ni se edita a mano: se sincroniza desde la BCN",
    ...
}
```

Ya sirvió: al escribirlo encontró que a notificaciones, plantillas y reglas les
faltaba el `PATCH` — algo que no estaba en la lista de quien lo escribió.

---

## Dónde está el CRUD hoy

| | Antes | Ahora |
|---|---|---|
| Recursos con CRUD completo | **0 de 26** | **20 de 29** |
| Endpoints | 91 | **138** |
| Recursos con borrado | 0 | 21 |
| Tests de la API | 57 | **91** |

Los 9 recursos incompletos que quedan tienen su motivo declarado y verificado
por test.

## Lo que falta para cubrir las 52 tablas

- **2 tablas**: `obligation_templates` y `declaration_templates`. Son catálogo
  **global sin `tenant_id`**: escribirlas afecta a todas las empresas, y el
  guard de Admin Global resuelve el rol contra el tenant de la sesión. Necesitan
  una autorización que no dependa de empresa
- **`contracts`**: requiere decidir el flujo de consentimiento bilateral
- **5 tablas de RBAC**: requieren que se apruebe `sistema-actores-roles-rbac`
- **5 tablas** que no llevan CRUD por diseño

## Advertencia sobre contar tablas

El plan hablaba de "50 tablas, hacerlas rápido". **No todas las tablas son
recursos de API.** Las de unión se administran desde su padre, las bitácoras las
escribe el sistema, y los catálogos de referencia se consultan. Contarlas todas
infla la estimación y después el número no cuadra con la realidad — que es
exactamente lo que pasó con el "17 de 26".

---

## Apéndice · Dos trampas que aparecieron al implementar

Ninguna estaba en el plan. Las dos las encontró el código al ejecutarse, no la
lectura.

### Las claves únicas no son parciales sobre `deleted_at`

La clave primaria de una tabla de asociación es `(padre, hijo)`. **No excluye
las filas borradas**, así que una fila dada de baja sigue ocupando la clave.
Volver a insertar la misma pareja choca contra una fila que el usuario no puede
ver, y como la API no tiene manejador de `IntegrityError`, sale **500**.

Y en una tabla de asociación volver a agregar algo que se quitó **es lo
normal**: una persona se reincorpora a una auditoría, un proceso vuelve a una
planta. Por eso `CRUDAsociacion.crear()` reinstala la fila existente en vez de
rechazar — y con los datos nuevos, porque quien la vuelve a agregar está
declarando las condiciones de ahora.

El mismo riesgo existe en `uq_departments_tenant_code` y otras únicas por
código: borrar `DEP-MED` y volver a crearlo daría 500. Está sin resolver.

### Anidar la ruta no ata el hijo al padre

`CRUDBase.get` resuelve por id a secas. Sin una comprobación explícita,
`/documents/{A}/entities/{X}` devuelve X **aunque X pertenezca al documento B**:
la jerarquía de la URL sería decorativa. `verificar_padre()` compara y responde
404 — bajo ese padre, ese hijo no existe.

Verificado: pedir una asignación de norma bajo la planta equivocada devuelve
404, no la fila.
