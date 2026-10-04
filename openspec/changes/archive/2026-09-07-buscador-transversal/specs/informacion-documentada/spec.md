## ADDED Requirements

### Requirement: La búsqueda atraviesa documentos, comentarios y registros
El sistema SHALL responder, dado un texto, las coincidencias encontradas en documentos, comentarios y registros de negocio, agrupadas por tipo.

#### Scenario: Una palabra que aparece en varios lados
- **GIVEN** una norma y un documento que mencionan el mismo término
- **WHEN** se busca ese término
- **THEN** el sistema devuelve ambos, cada uno identificado por su tipo

#### Scenario: Sin coincidencias
- **WHEN** se busca un término que no aparece en ningún registro
- **THEN** el sistema devuelve una lista vacía, y la interfaz la distingue de no haber podido buscar

### Requirement: La búsqueda ignora los acentos
El sistema SHALL encontrar un término escrito sin acentos en textos que lo contienen acentuado.

Los títulos del catálogo normativo están en mayúsculas con tilde; una búsqueda que los distinga devuelve cero resultados y ningún error, que se lee como que esa norma no existe.

#### Scenario: Un término sin tilde
- **GIVEN** una norma cuyo título contiene una palabra acentuada
- **WHEN** se busca esa palabra sin acento
- **THEN** el sistema devuelve esa norma

### Requirement: La búsqueda sólo devuelve lo que quien busca puede leer
El sistema SHALL excluir de los resultados los registros cuyo tipo la persona no tiene permiso de leer.

Sin esta regla el buscador es un oráculo: revela la existencia y el título de registros que esa persona no puede abrir.

#### Scenario: Alguien sin permiso sobre un tipo
- **GIVEN** una persona sin permiso de lectura sobre las auditorías
- **WHEN** busca un término que aparece en el título de una auditoría
- **THEN** el sistema no devuelve esa auditoría

### Requirement: La búsqueda declara sus límites
El sistema SHALL informar cuando un grupo de resultados fue recortado, y SHALL rechazar una consulta demasiado corta explicando el mínimo.

#### Scenario: Una consulta de un carácter
- **WHEN** se busca un único carácter
- **THEN** el sistema lo rechaza indicando el mínimo, en vez de devolver una lista vacía
