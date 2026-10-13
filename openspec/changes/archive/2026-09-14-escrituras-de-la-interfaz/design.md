# Diseño: Escrituras de la interfaz

## 1. Una escritura no es un `PATCH`: es un viaje de ida y vuelta

Es la lección que costó dos estimaciones equivocadas. Conectar un campo editable
tiene **dos lados**, y hacer solo uno produce un engaño distinto pero igual de
malo:

| Lado | Si falta |
|---|---|
| Escribir | La pantalla confirma un cambio que la base nunca recibió |
| Leer | La base guarda el cambio y la pantalla sigue mostrando el valor de siempre |

`tenants` estaba en el segundo caso sin que nadie lo notara: el mapper trae
`limiteUsuarios: 50` y `modulosActivos: []` **escritos a mano**. Escribirlos sin
tocar la lectura habría dado un "guardado" que se deshace al recargar.

**Por eso la unidad de trabajo de este cambio es el campo, no la función.**

## 2. Optimista con reversión

La pantalla muestra el cambio de inmediato y, si la API lo rechaza, vuelve atrás
y lo dice.

**Por qué no pesimista** (esperar la confirmación antes de pintar): en las
acciones de esta tanda —marcar leído, cambiar visibilidad, mover una etapa— el
usuario espera respuesta inmediata, y un botón que tarda 200 ms en reaccionar se
siente roto. Es además lo que ya hacían los stores conectados; cambiar de patrón
a mitad de camino dejaría dos formas conviviendo.

**Qué se pierde:** con una conexión lenta hay parpadeo, y el usuario ve el
cambio aplicarse y deshacerse. Es un costo real y es el precio de la respuesta
inmediata.

**La alternativa descartada** —optimista sin reversión, que es lo que había— no
es más simple: es simplemente incorrecta.

## 3. Reversión total o parcial

Depende de la forma del dato, y la distinción importa:

| Caso | Qué se revierte | Por qué |
|---|---|---|
| Un campo de un registro | Ese campo | No hay nada más que deshacer |
| Varios registros a la vez | **Solo los que fallaron** | Si de diez se guardaron ocho, decir que no se guardó ninguno es falso |
| Una lista que se reemplaza entera | Toda la lista | Dejarla a medias mostraría una composición que la base no tiene |

Marcar notificaciones como leídas es el segundo caso; cambiar en qué plantas
aplica una norma es el tercero.

## 4. Dónde viven los campos que la API no modela

Tres campos de empresa —límite de usuarios, módulos activos y logo— no tienen
columna propia: van en `settings`, el jsonb del tenant.

**Qué se gana:** no hace falta migrar el esquema para algo que todavía está
tomando forma.

**Qué se pierde, y hay que decirlo:** un jsonb sin esquema declarado es un
cajón. Si tres pantallas escriben claves distintas ahí, nadie va a saber qué
contiene ni podrá validarlo. Se escribe **fusionando**, nunca reemplazando el
objeto entero, para que dos pantallas no se pisen los valores.

Cuando alguno de estos campos se estabilice, merece columna propia. Queda como
decisión abierta.

## 5. Lo que no se conecta, se dice en su sitio

Cada función que no puede persistir lleva **en su propio docstring** la causa
concreta: qué endpoint falta, qué campo no acepta la API, qué dato no existe
aguas arriba.

**Por qué ahí y no en un documento aparte:** un documento se desactualiza y nadie
lo lee antes de tocar la función. El comentario lo lee quien va a intentar
arreglarlo, en el momento exacto en que lo va a intentar.

Nueve funciones quedan así. Dos se descubrieron al implementar este cambio:

- **`completarPerfilEmpresa`** — el perfil se considera completo cuando hay giro
  y RUT, y `TenantUpdate` **no acepta `rut_tax_id`**. La pantalla ofrece marcar
  como completo algo que la API no deja completar.
- **`toggleTarea`** — las tareas de un plan de acción **no existen en el modelo**:
  el mapper las arma vacías y no hay campo donde guardarlas.

Las dos son el mismo síntoma: **la interfaz se diseñó antes que el modelo**, y
recién al conectarlos se ve dónde no se hablan.

## 6. El mensaje de error

Se deriva del cuerpo que devuelve la API, no del código de estado a secas.

FastAPI manda `detail` en dos formas: una cadena cuando rechaza un router, y una
**lista de errores por campo** cuando rechaza la validación. Leer solo la primera
deja los 422 —los más frecuentes al conectar una pantalla— mostrando
`[object Object]`.

Cuando ni siquiera se llegó a la API, el mensaje lo dice: "no se pudo contactar"
y "el servidor rechazó" son problemas distintos y llevan a acciones distintas.
