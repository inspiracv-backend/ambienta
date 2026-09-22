## ADDED Requirements

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
