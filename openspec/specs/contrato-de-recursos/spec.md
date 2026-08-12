# Contrato de recursos de la API

## Purpose

Las reglas que cumple **todo** recurso de negocio de la API, para no tener que
volver a decidirlas recurso por recurso.

No describe ningún dominio en particular: describe la forma que comparten todos.
Cómo se borra, qué pasa al apuntar a un registro de otra empresa, qué significa
cada código de error, cómo se direcciona una tabla que vincula dos entidades.
Un recurso nuevo hereda esto entero, y si necesita apartarse conviene que sea
una decisión escrita, no un olvido.

Casi todo lo de aquí existe porque la alternativa se probó y falló:

- El borrado era **físico** sobre un esquema diseñado para borrado lógico, y las
  lecturas no filtraban lo borrado. Las dos mitades estaban mal y se tapaban
  entre sí, porque ningún recurso exponía el borrado todavía.
- Las claves foráneas de PostgreSQL **no pasan por RLS**: comprueban existencia,
  no pertenencia. Sin validar el destino contra la sesión, un endpoint queda
  convertido en un detector de identificadores ajenos.
- Los errores mapeados por el texto del mensaje del motor sobreviven hasta la
  primera actualización de PostgreSQL.

**El aislamiento entre empresas descansa entero en RLS.** Ninguna consulta de la
aplicación filtra por `tenant_id`, así que estas reglas son lo que impide que un
recurso mal escrito abra un hueco — y por qué un endpoint que se equivoca
devuelve cero filas en vez de todas.

Qué *puede hacer* cada rol dentro de su empresa es otra capacidad, y todavía no
existe.

## Requirements
### Requirement: Contrato uniforme por recurso
El sistema SHALL exponer cada recurso de negocio con el mismo conjunto de
operaciones —crear, listar, leer uno, actualizar y borrar— de modo que conocer
un recurso baste para saber usar los demás.

La uniformidad no es estética: el frontend escribe un adaptador por recurso y
cualquier hueco obliga a un caso especial que después nadie recuerda.

#### Scenario: Un recurso recién expuesto se comporta como los demás
- **GIVEN** un recurso de negocio disponible en la API
- **WHEN** un cliente consulta el contrato del recurso
- **THEN** encuentra las cinco operaciones sobre la colección y sobre el elemento
- **AND** las respuestas de error siguen el mismo esquema que el resto de la API

#### Scenario: Leer un elemento que no existe
- **GIVEN** un identificador que la empresa de la sesión no puede ver
- **WHEN** el cliente pide ese elemento
- **THEN** el sistema responde 404
- **AND** no revela si el identificador existe en otra empresa

### Requirement: Borrado lógico
El sistema SHALL conservar las filas borradas y ocultarlas de toda lectura, en
vez de eliminarlas de la base.

El esquema fue diseñado con `deleted_at` e índices parciales, y el cumplimiento
ambiental exige poder reconstruir qué se declaró y cuándo. Un borrado físico
destruye la evidencia que el sistema existe para custodiar.

#### Scenario: Lo borrado desaparece de los listados
- **GIVEN** un elemento visible en el listado de su recurso
- **WHEN** un usuario lo borra
- **THEN** deja de aparecer en el listado
- **AND** deja de poder leerse por su identificador
- **AND** la fila sigue en la base con la fecha de borrado registrada

#### Scenario: Borrar dos veces no es un error distinto
- **GIVEN** un elemento ya borrado
- **WHEN** un usuario intenta borrarlo otra vez
- **THEN** el sistema responde 404, igual que si nunca hubiera existido
- **AND** la fecha del borrado original no se modifica

#### Scenario: La fecha de borrado la pone la base
- **WHEN** el sistema marca un elemento como borrado
- **THEN** la fecha proviene del reloj de la base de datos
- **AND** es comparable con la fecha de creación de la misma fila

### Requirement: Referencias cruzadas acotadas a la empresa
El sistema SHALL aceptar una referencia a otro registro únicamente si ese
registro es visible para la empresa de la sesión, y SHALL responder igual
cuando el destino no existe que cuando pertenece a otra empresa.

Las claves foráneas de PostgreSQL comprueban existencia, no pertenencia: una
referencia a la planta de otra empresa satisface la restricción y deja la fila
apuntando fuera. Distinguir los dos rechazos convertiría el endpoint en un
**oráculo de existencia**, con el que se enumeran identificadores ajenos sin
llegar a verlos nunca.

#### Scenario: Referencia a un registro de otra empresa
- **GIVEN** un usuario de la empresa A
- **WHEN** crea o actualiza un registro apuntando a un elemento de la empresa B
- **THEN** el sistema rechaza la operación
- **AND** el mensaje es idéntico al de un identificador inexistente

#### Scenario: Referencia a un registro inexistente
- **WHEN** un usuario apunta a un identificador que no existe en ninguna empresa
- **THEN** el sistema rechaza la operación con el mismo mensaje del caso anterior

#### Scenario: Referencia a un registro borrado
- **GIVEN** un elemento que fue borrado lógicamente
- **WHEN** otro registro intenta apuntar a él
- **THEN** el sistema lo rechaza, porque para la aplicación ya no es visible

### Requirement: Jerarquías sin ciclos
El sistema SHALL rechazar cualquier cambio que deje a un registro como
ascendiente de sí mismo.

La base no lo impide: un ciclo no rompe la escritura y solo se manifiesta más
tarde, colgando a quien recorra el árbol. Es la peor forma de enterarse, porque
el síntoma aparece lejos de la causa.

#### Scenario: Un registro como padre de sí mismo
- **WHEN** un usuario fija el padre de un registro apuntando al propio registro
- **THEN** el sistema rechaza la operación

#### Scenario: Ciclo indirecto
- **GIVEN** un registro B cuyo padre es A
- **WHEN** un usuario fija el padre de A apuntando a B
- **THEN** el sistema rechaza la operación

### Requirement: Asociaciones de clave compuesta
El sistema SHALL exponer las tablas que vinculan dos entidades usando ambos
identificadores como dirección del recurso, y SHALL permitir volver a crear una
asociación previamente borrada.

Sin lo segundo, quitar un vínculo y volver a ponerlo choca contra la clave única
—la fila borrada sigue ahí— y deja al usuario ante un conflicto sin salida
posible desde la interfaz.

#### Scenario: Crear y borrar una asociación
- **GIVEN** dos entidades visibles para la empresa de la sesión
- **WHEN** un usuario las asocia y luego deshace la asociación
- **THEN** el vínculo deja de aparecer entre las asociaciones de la entidad padre

#### Scenario: Volver a asociar lo que se había quitado
- **GIVEN** una asociación borrada entre dos entidades
- **WHEN** un usuario vuelve a crearla
- **THEN** el sistema la acepta y el vínculo vuelve a estar activo
- **AND** no se produce un conflicto de duplicado

#### Scenario: Asociar entidades de otra empresa
- **WHEN** un usuario intenta asociar una entidad que su empresa no puede ver
- **THEN** el sistema lo rechaza igual que cualquier otra referencia cruzada

### Requirement: Errores uniformes de escritura
El sistema SHALL traducir cada violación de restricción de la base a una
respuesta estable, determinada por el tipo de restricción y no por el texto del
mensaje del motor.

El texto de los errores de PostgreSQL cambia entre versiones y con el idioma del
servidor. Un mapeo que dependa de esas cadenas se rompe en una actualización sin
que ninguna prueba lo advierta.

#### Scenario: Valor duplicado en una clave única
- **WHEN** una escritura viola una restricción de unicidad
- **THEN** el sistema responde 409
- **AND** indica qué valor está duplicado sin exponer la fila existente

#### Scenario: Violación de una regla de dominio
- **WHEN** una escritura viola una comprobación, una columna obligatoria o una clave foránea
- **THEN** el sistema responde 422
- **AND** describe qué regla no se cumplió

### Requirement: Contrato descubrible y consistente
El sistema SHALL documentar cada operación con las respuestas de error que
realmente puede devolver, derivándolas de la forma de la ruta en vez de
declararlas una por una.

Con casi un centenar de rutas, declarar los errores a mano garantiza que se
desincronicen: basta que alguien agregue una ruta y olvide el bloque.

#### Scenario: Una ruta autenticada documenta el rechazo por sesión
- **GIVEN** una operación que exige sesión
- **WHEN** se consulta el contrato de la API
- **THEN** la operación declara la respuesta de no autenticado

#### Scenario: Una ruta con identificador documenta el no encontrado
- **GIVEN** una operación que recibe un identificador en la dirección
- **WHEN** se consulta el contrato de la API
- **THEN** la operación declara la respuesta de no encontrado

#### Scenario: Las operaciones están agrupadas por dominio
- **WHEN** una persona abre la documentación interactiva
- **THEN** las operaciones aparecen agrupadas por área de negocio, con una descripción por grupo

