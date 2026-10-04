# Catálogo normativo

## Purpose

La ley que aplica, igual para todas las empresas: normas, sus versiones con
fecha, su articulado, sus relaciones con otras normas y de dónde salió cada dato.
Se alimenta de la fuente oficial (la BCN) y deja registro de cada
sincronización, porque la primera pregunta de una auditoría es cómo se sabe que
el catálogo está completo y vigente.

Lo que cada empresa responde sobre esas normas no vive acá: vive en su matriz
legal. Y la API expone el catálogo a otros sistemas (el servicio de IA) con un
contrato estable de paginación e identificación.

## Requirements
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

### Requirement: El catálogo se alimenta de la fuente oficial
El sistema SHALL poder incorporar normas desde la fuente oficial de legislación
chilena, conservando el identificador con que esa fuente las reconoce.

Hoy el catálogo se llena a mano. Eso no responde la primera pregunta de una
auditoría: cómo se determinó que estas normas aplican y cómo se sabe que no
falta ninguna. Conservar el identificador de origen es lo que permite volver a
la fuente después sin adivinar a qué norma corresponde cada fila.

#### Scenario: Se incorpora una norma que no estaba
- **WHEN** el sistema sincroniza una norma que el catálogo no tiene
- **THEN** la agrega con su título, número, tipo, fechas y organismo
- **AND** guarda el identificador con que la fuente oficial la reconoce

#### Scenario: Se vuelve a sincronizar una norma ya incorporada
- **GIVEN** una norma que ya está en el catálogo
- **WHEN** el sistema la sincroniza otra vez
- **THEN** actualiza los datos de los que la fuente es dueña
- **AND** no crea una segunda fila

#### Scenario: La fuente devuelve la misma norma varias veces
- **GIVEN** una fuente que representa una norma en más de una forma
- **WHEN** el sistema la incorpora
- **THEN** queda una sola norma en el catálogo

#### Scenario: Lo que decidió una persona no se pierde
- **GIVEN** una norma cuyo alcance o responsables fijó alguien en el sistema
- **WHEN** una sincronización posterior actualiza esa norma
- **THEN** los datos que vienen de la fuente se refrescan
- **AND** las decisiones tomadas en el sistema se conservan

### Requirement: Las relaciones entre normas se leen de la fuente
El sistema SHALL registrar qué normas modifican, reglamentan, refunden,
rectifican o concuerdan con cuáles, tomándolo de la fuente oficial, y SHALL
registrar cada relación una sola vez aunque la fuente la declare desde las dos
normas.

Que una norma modifique a otra lo declara la ley, no quien carga el catálogo.
Sostenerlo de memoria es como se llega a evaluar el cumplimiento de un texto que
ya cambió. La fuente no publica las derogaciones como relación: que una norma ya
no rige se sabe por su vigencia, que el catálogo también conserva.

#### Scenario: Se incorpora una relación entre dos normas
- **WHEN** la fuente declara que una norma modifica a otra
- **THEN** el sistema registra la relación con su tipo
- **AND** queda consultable desde cualquiera de las dos

#### Scenario: Una relación apunta a una norma que no está en el catálogo
- **WHEN** la fuente declara una relación hacia una norma que el catálogo no tiene
- **THEN** el sistema no inventa la norma faltante
- **AND** deja registro en la bitácora de la sincronización de que esa relación quedó sin resolver

#### Scenario: La misma relación declarada desde las dos normas
- **GIVEN** una norma que la fuente declara modificada por otra, y la otra que se declara modificándola
- **WHEN** el sistema sincroniza las dos
- **THEN** queda una sola relación, de la norma que modifica a la modificada

### Requirement: Se conserva qué versión de una norma estaba vigente
El sistema SHALL registrar las versiones de una norma con su fecha, de modo que
una evaluación de cumplimiento pueda decir contra qué texto se hizo.

Una evaluación firmada contra el texto de 2016 no dice lo mismo si la norma
cambió en 2024. Sin versiones, el historial de cumplimiento afirma algo que no
puede sostener.

#### Scenario: Se incorporan las versiones de una norma
- **WHEN** el sistema sincroniza una norma con varias versiones
- **THEN** registra cada versión con su fecha
- **AND** distingue cuál es la vigente

### Requirement: Toda sincronización deja registro
El sistema SHALL registrar cada ejecución de la sincronización, con su resultado,
y ese registro SHALL ser solo de lectura para las personas.

Sin bitácora la ingesta es una caja negra: una corrida que no trae nada porque la
consulta se rompió se ve igual que una que no tenía nada nuevo. Y editarla sería
falsificar el registro de qué se sincronizó.

#### Scenario: Una sincronización que termina bien
- **WHEN** una sincronización termina
- **THEN** queda registrado cuándo corrió, cuántas normas revisó, cuántas agregó y cuántas actualizó

#### Scenario: La fuente no responde
- **WHEN** la fuente oficial no está disponible
- **THEN** la sincronización termina sin dejar el catálogo a medias
- **AND** queda registrado el fallo con su motivo

#### Scenario: La sincronización no trae nada
- **WHEN** una sincronización no encuentra ninguna norma
- **THEN** el resultado lo distingue de una corrida exitosa sin novedades

#### Scenario: Nadie puede editar la bitácora
- **WHEN** alguien intenta modificar o borrar un registro de sincronización
- **THEN** el sistema no se lo permite

