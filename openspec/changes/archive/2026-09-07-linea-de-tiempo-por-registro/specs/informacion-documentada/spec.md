## ADDED Requirements

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
