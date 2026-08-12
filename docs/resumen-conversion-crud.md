# Conversión a CRUD — resumen

**11-ago-2026.** Todas las cifras se midieron contra la API y la base en
ejecución, no leyendo código.

## Dónde empezó y dónde terminó

| | Antes | Ahora |
|---|---|---|
| Recursos con CRUD completo | **0 de 26** | **38 de 39** |
| Endpoints | 91 | **211** |
| Recursos con borrado | **0** | 38 |
| Tests de la API | 57 | **103** |

Lo único incompleto es `tenants`, sin borrado, por un motivo escrito: marcar
una empresa como dada de baja **no impide entrar a sus usuarios**, porque nada
consulta `tenant.deleted_at` al autenticar. Sería una baja que miente.

## El punto de partida real

El número "0 de 26" no era exageración. **Ningún recurso tenía borrado**, y el
problema iba más hondo que un endpoint faltante:

- `CRUDBase.remove()` hacía `db.delete()` — borrado **físico** — mientras el
  esquema estaba diseñado para borrado **lógico** con `deleted_at`.
- `get()` y `get_multi()` **no filtraban** `deleted_at`.

Las dos mitades estaban mal y se tapaban entre sí, porque ningún router exponía
el borrado. Exponerlo directo lo habría hecho nacer roto: una fila borrada
habría seguido apareciendo en los listados.

Además un endpoint devolvía **500**: `POST /support/tickets` no generaba su
`ticket_number`. Era el único roto de los 91 — y justo el que sostiene el flujo
del Cliente Invitado.

## Las cuatro tandas

### 1 · Arreglar los cimientos

Los 26 recursos son instancias directas de `CRUDBase` **sin sobreescribir
nada**, así que arreglarlo alcanzó a todos desde un archivo.

- Borrado lógico de verdad: `remove()` marca `deleted_at` con `func.now()` —la
  hora la pone la base, para que sea comparable con `created_at`— y las lecturas
  excluyen lo borrado desde un solo punto.
- `get()` pasó de `db.get()` a `select()`. No fue estilo: `db.get()` resuelve
  por clave primaria y por el mapa de identidad, así que **nunca pasa por un
  `WHERE`** donde filtrar.
- `ticket_number` lo genera ahora una secuencia de Postgres, no Python: la
  unicidad es global, y calcular `max()+1` en la aplicación abriría una carrera
  entre peticiones de tenants distintos.

### 2 · Los recursos simples

`departments`, `processes`, `integrations`, y el borrado en 18 recursos.

### 3 · Los anidados

Tres tablas de **clave compuesta** —participantes de auditoría, operadores de
equipo, procesos por planta— van bajo su padre. `CRUDBase` no las direcciona y
lanza `NotImplementedError` a propósito; se agregó `CRUDAsociacion`.

Dos vínculos —`entity_documents`, `facility_norm_assignments`— necesitaban
atadura hijo-padre.

### 4 · Las que dependían de una decisión

- **Plantillas**: router propio con guard de Admin Global. No llevan
  `tenant_id`, así que lo que se crea ahí lo ven **todas** las empresas.
- **Contratos**: desbloqueado forzando `manager_tenant_id` desde la sesión.
- **Catálogo**: expuesto con el mismo guard, con la advertencia en el código.

---

## Los seis hallazgos que cambiaron el trabajo

Ninguno estaba en el plan. Todos aparecieron al ejecutar, no al leer.

### 1. Las FK de Postgres no pasan por RLS

`fk_departments_facility` solo exige que exista la fila. **No mira el tenant.**
Un `PATCH` con la planta de otra empresa pasaba la restricción.

El daño no es la fila incoherente: es un **oráculo de existencia**. Probando
identificadores al azar se distingue "no existe" (falla la FK) de "existe pero
es de otro" (pasa). Por eso ambos devuelven **422**, no errores distintos.

### 2. El aislamiento se perdía en cada `commit`

`SET LOCAL` muere con la transacción. Medido, con 6 usuarios en la base:

| Conexión | Olvidando todo | Tras commit |
|---|---|---|
| Dueño (antes) | **6** = todas las empresas | **6** |
| `ambienta_app` (ahora) | 0 | 0 |

Y **ya estaba pasando**: `expire_on_commit` disparaba un `SELECT` de refresco
sin rol y sin tenant en cada POST. La API ahora se conecta con un rol que no
puede saltarse RLS: el modo de fallo se invirtió de "ve todo" a "no ve nada".

### 3. `/tenants/` estaba abierto sin autenticación

Devolvía la cartera completa de clientes —RUT, razón social, giro— a cualquiera,
y permitía crear y editar empresas. `tenants` es la única tabla sin `tenant_id`,
así que RLS no la cubre y `get_tenant_db` no le servía: quedó sin ninguna
protección.

### 4. Una restricción violada salía como error del servidor

Mandar un valor fuera de un `CHECK` devolvía **500**. Le pasaba a toda la API —
no había manejador de `IntegrityError`. Un 500 no le dice a quien integra qué
corregir, y un cliente con reintentos reintentaría algo que nunca va a funcionar.

Ahora: unicidad → **409**, CHECK / NOT NULL / FK → **422**, con el nombre de la
restricción en la respuesta.

### 5. Las claves únicas no son parciales sobre `deleted_at`

Una fila borrada sigue ocupando la clave. Reinsertar la misma pareja chocaba
contra una fila invisible → **500**. Y en tablas de asociación volver a agregar
algo que se quitó **es lo normal**: alguien se reincorpora a una auditoría, un
proceso vuelve a una planta. Ahora se reinstala con los datos nuevos.

> **Sigue vivo** en `uq_departments_tenant_code` y otras únicas por código:
> borrar `DEP-MED` y recrearlo daría 500. Sin resolver.

### 6. Anidar la ruta no ata el hijo al padre

`CRUDBase.get` resuelve por id a secas, así que `/documents/{A}/entities/{X}`
devolvía X **aunque X perteneciera al documento B**. La jerarquía era
decorativa. Verificado: ahora da 404.

---

## Evidencia

Ciclo completo ejecutado contra la API corriendo, no con tests:

| Recurso | Crear | Listar | Leer | Editar | Borrar | Releer |
|---|---|---|---|---|---|---|
| `departments` | 201 | 200 | 200 | 200 | 204 | **404** |
| `processes` | 201 | 200 | 200 | 200 | 204 | **404** |
| `facilities` | 201 | 200 | 200 | 200 | 204 | **404** |
| `documents` | 201 | 200 | 200 | 200 | 204 | **404** |
| `contracts` | 201 | 200 | 200 | 200 | 204 | **404** |
| `declarations` | 201 | 200 | 200 | 200 | 204 | **404** |
| `audits/{id}/items` | 201 | 200 | 200 | 200 | 204 | **404** |
| `iso14001/aspects` | 201 | 200 | 200 | 200 | 204 | **404** |
| `support/tickets` | 201 | 200 | 200 | 200 | 204 | **404** |
| `integrations` | 201 | 200 | 200 | 200 | 204 | **404** |

El **404 final** es la prueba del borrado lógico: la fila queda marcada en la
base y desaparece de la API.

Protecciones, verificadas:

| Prueba | Resultado |
|---|---|
| Auto-padre en una jerarquía | **422** |
| FK que no existe en la empresa | **422** |
| Hijo pedido bajo el padre equivocado | **404** |
| Escribir plantillas sin ser Admin Global | **403** |
| Escribir catálogo sin ser Admin Global | **403** |
| Leer plantillas autenticado | **200** |
| Código duplicado | **409** |
| Valor fuera de un `CHECK` | **422** |
| Reinstalar tras borrar | **201** |

## Lo que se sostiene solo

`tests/test_crud_cobertura.py` **falla si alguien agrega un recurso a medias**
sin declarar por qué. Ya sirvió dos veces: encontró que a notificaciones les
faltaba el `PATCH`, y que a los cinco anidados les faltaba el `GET` por id.

Las propiedades de aislamiento y de borrado están fijadas por tests contra
Postgres real, comprobados **por mutación** — rompiendo a propósito lo que dicen
proteger y confirmando que fallan.

## Lo que queda fuera, y por qué

| Tablas | Motivo |
|---|---|
| `audit_log`, `entity_status_history` | **La base revoca `UPDATE` y `DELETE`.** No es criterio: es RNF-25, el registro de auditoría es inmutable |
| `roles`, `permissions`, `role_permissions`, `user_roles`, `user_permissions` | Pertenecen al change `sistema-actores-roles-rbac`, **sin aprobar**. `user_permissions` ni siquiera tiene modelo. Exponerlas ahora pre-empta su diseño |
| `tenants` (borrado) | Marcar la empresa no impide entrar a sus usuarios |

## Advertencia sobre contar tablas

El plan decía "50 tablas, hacerlas rápido". Son **52**, pero **no todas son
recursos de API**: las de unión se administran desde su padre, las bitácoras las
escribe el sistema, los catálogos de referencia se consultan. Contarlas todas
infla la estimación y después el número no cuadra con la realidad.

## Pendiente del plan original

**Cablear el CRUD al frontend no se empezó.** De 21 pantallas, solo el tablero
consume la API; las otras 20 leen datos de ejemplo.
