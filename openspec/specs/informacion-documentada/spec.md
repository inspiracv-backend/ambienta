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

