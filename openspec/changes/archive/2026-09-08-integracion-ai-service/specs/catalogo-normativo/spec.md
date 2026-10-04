## ADDED Requirements

### Requirement: El catálogo se puede sincronizar de forma incremental
El sistema SHALL permitir listar únicamente los registros modificados después de una fecha y hora dadas, conservando el comportamiento actual cuando no se indique ninguna.

#### Scenario: Sólo lo que cambió
- **GIVEN** un catálogo con registros modificados en distintos momentos
- **WHEN** se listan las normas indicando una fecha de corte
- **THEN** el sistema devuelve sólo las modificadas después de esa fecha

#### Scenario: Sin fecha de corte
- **WHEN** se listan las normas sin indicar fecha
- **THEN** el sistema responde como lo hacía antes

#### Scenario: Junto con la paginación
- **WHEN** se combina la fecha de corte con los parámetros de paginación
- **THEN** el sistema aplica ambos

### Requirement: El historial de versiones de una norma es consultable
El sistema SHALL exponer las versiones de una norma, indicando su vigencia y cuál rige actualmente.

#### Scenario: Las versiones de una norma
- **WHEN** se consultan las versiones de una norma
- **THEN** el sistema devuelve cada una con su inicio de vigencia, su término cuando exista, y si es la vigente

### Requirement: El articulado se puede pedir a una fecha pasada
El sistema SHALL devolver el articulado que regía en una fecha determinada, y no sólo el vigente.

Sin esto no se puede responder con qué texto se evaluó el cumplimiento en un período ya cerrado, que es lo que revisa una auditoría.

#### Scenario: El texto de una fecha pasada
- **GIVEN** una norma con más de una versión
- **WHEN** se pide su articulado a una fecha cubierta por una versión anterior
- **THEN** el sistema devuelve los artículos de esa versión

#### Scenario: Una fecha sin texto vigente
- **WHEN** se pide el articulado a una fecha anterior a toda versión
- **THEN** el sistema devuelve una lista vacía, no un error

### Requirement: El enlace de descarga permite verificar el archivo
El sistema SHALL entregar, junto al enlace de descarga de una revisión, la huella que permite comprobar la integridad de lo descargado.

#### Scenario: Descarga verificable
- **WHEN** se pide el enlace de descarga de una revisión que tiene huella registrada
- **THEN** el sistema la incluye en la respuesta

#### Scenario: Una revisión sin huella
- **WHEN** la revisión no tiene huella registrada
- **THEN** el sistema lo informa como ausente en vez de entregar un valor inventado

### Requirement: El contrato declara cómo se pagina y cómo se identifica la empresa
El sistema SHALL documentar en su contrato las cabeceras de paginación que emite, y SHALL describir la cabecera de empresa como el mecanismo de desarrollo que es.

#### Scenario: Un cliente generado desde el contrato
- **WHEN** se lee el contrato de un endpoint paginado
- **THEN** aparecen declaradas las cabeceras que informan el tope y si quedaron registros fuera
