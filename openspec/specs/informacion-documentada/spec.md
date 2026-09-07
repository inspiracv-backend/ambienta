# informacion-documentada Specification

## Purpose
TBD - created by archiving change vinculacion-transversal-de-documentos. Update Purpose after archive.
## Requirements
### Requirement: Un documento se vincula sólo a registros de la propia empresa
El sistema SHALL rechazar la vinculación de un documento con una entidad que no sea visible para la empresa que la solicita.

Sin clave foránea que lo sostenga, un vínculo a un identificador inventado deja escrito que un documento respalda algo que no existe — una afirmación falsa en el registro que se muestra ante una fiscalización.

#### Scenario: Un identificador que no existe
- **WHEN** se vincula un documento con un `entity_id` que no corresponde a ninguna fila
- **THEN** el sistema rechaza la escritura y no queda vínculo

#### Scenario: Un identificador real de otra empresa
- **GIVEN** una obligación que pertenece a otra empresa
- **WHEN** se intenta vincular un documento propio con ella
- **THEN** el sistema responde con el mismo código y el mismo mensaje que ante un identificador inexistente

### Requirement: Un documento se puede colgar de una norma y de un proceso
El sistema SHALL admitir la vinculación de un documento con una norma del catálogo y con un proceso, además de las entidades de empresa que ya admitía.

#### Scenario: Un procedimiento y el proceso que describe
- **WHEN** se vincula un procedimiento con un proceso de la empresa
- **THEN** el sistema registra el vínculo

### Requirement: Desde un registro se ve qué documentos lo respaldan
El sistema SHALL responder, dada una entidad, la lista de documentos vinculados a ella.

La pregunta de un fiscalizador señala un requisito y pide su evidencia; el sentido inverso —qué respalda este documento— no contesta eso.

#### Scenario: La evidencia de una obligación
- **GIVEN** un documento vinculado a una obligación
- **WHEN** se consultan los documentos de esa obligación
- **THEN** el sistema devuelve ese documento

#### Scenario: Un registro sin documentos
- **WHEN** se consultan los documentos de una entidad que no tiene ninguno
- **THEN** el sistema devuelve una lista vacía, y la interfaz la distingue de no haber podido preguntar

### Requirement: Cualquier registro admite comentarios con hilo
El sistema SHALL permitir comentar sobre las mismas entidades a las que se puede vincular un documento, y responder a un comentario existente.

#### Scenario: Una respuesta cuelga de su comentario
- **GIVEN** un comentario sobre una obligación
- **WHEN** se responde a ese comentario
- **THEN** la respuesta queda asociada a él

#### Scenario: El hilo no anida más de un nivel
- **GIVEN** una respuesta a un comentario
- **WHEN** se intenta responder a esa respuesta
- **THEN** el sistema lo rechaza e indica cuál es el comentario raíz

#### Scenario: Una entidad que no admite comentarios
- **WHEN** se comenta sobre un tipo de entidad desconocido
- **THEN** el sistema lo rechaza

### Requirement: Un comentario tiene autor identificado
El sistema SHALL rechazar la creación de un comentario cuando la sesión no identifica a una persona.

Atribuirlo a alguien que no lo escribió deja en el registro una afirmación falsa sobre quién dijo qué, y ese registro se exporta a un auditor.

#### Scenario: Sesión sin persona
- **WHEN** se comenta desde una sesión que no identifica al usuario
- **THEN** el sistema rechaza la escritura y no queda comentario

### Requirement: Mencionar a alguien lo notifica
El sistema SHALL registrar a las personas mencionadas en un comentario y encolarles una notificación.

#### Scenario: Una mención
- **WHEN** se publica un comentario mencionando a un compañero de la empresa
- **THEN** esa persona queda registrada como mencionada y recibe una notificación

#### Scenario: Mencionarse a uno mismo
- **WHEN** el autor se menciona en su propio comentario
- **THEN** el sistema no le encola una notificación

#### Scenario: Alguien de otra empresa
- **WHEN** se menciona a un usuario que pertenece a otra empresa
- **THEN** el sistema responde igual que ante un usuario inexistente

### Requirement: Editar un comentario queda a la vista
El sistema SHALL informar si un comentario fue editado después de publicado.

#### Scenario: Un comentario corregido
- **WHEN** se edita un comentario ya publicado
- **THEN** el sistema expone la marca de edición junto al comentario

### Requirement: Borrar la cabeza de un hilo no borra las respuestas
El sistema SHALL conservar las respuestas de un comentario eliminado.

Eliminarlas haría que la decisión de una persona borrara lo que escribieron otras.

#### Scenario: Se retira el comentario raíz
- **GIVEN** un comentario con respuestas
- **WHEN** se elimina el comentario raíz
- **THEN** las respuestas siguen disponibles

### Requirement: La historia de un registro reúne sus distintas fuentes
El sistema SHALL responder, dada una entidad, sus eventos de actividad, sus comentarios y sus adjuntos en una sola secuencia ordenada del más reciente al más antiguo.

#### Scenario: Un registro con actividad y conversación
- **GIVEN** un registro que fue modificado y comentado
- **WHEN** se consulta su historia
- **THEN** el sistema devuelve ambos hechos en una sola lista ordenada por fecha

#### Scenario: Un registro sin historia
- **WHEN** se consulta la historia de un registro sobre el que no ocurrió nada
- **THEN** el sistema devuelve una lista vacía, y la interfaz la distingue de no haber podido preguntar

### Requirement: La historia declara qué fuentes la componen y cuáles faltan
El sistema SHALL informar, junto a la historia, qué orígenes de información la alimentan y cuáles todavía no están disponibles.

Una historia sin correos que no lo advierte hace concluir que sobre ese registro no hubo correos, cuando lo que ocurre es que el sistema aún no los captura.

#### Scenario: La captura de correos no existe todavía
- **WHEN** se consulta la historia de cualquier registro
- **THEN** el sistema declara que el correo es una fuente pendiente

### Requirement: La historia se corta con aviso
El sistema SHALL indicar cuando la historia devuelta está incompleta por alcanzar su tope.

#### Scenario: Un registro con mucha historia
- **GIVEN** un registro con más eventos que el tope
- **WHEN** se consulta su historia
- **THEN** el sistema devuelve los más recientes e informa que hay más

