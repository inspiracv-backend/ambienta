# Catálogo normativo

## ADDED Requirements

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
El sistema SHALL registrar qué normas modifican, derogan, rectifican o regulan a
cuáles, tomándolo de la fuente oficial.

Que una norma derogue a otra lo declara la ley, no quien carga el catálogo.
Sostenerlo de memoria es como se llega a evaluar el cumplimiento de una norma que
ya no rige.

#### Scenario: Se incorpora una relación entre dos normas
- **WHEN** la fuente declara que una norma modifica a otra
- **THEN** el sistema registra la relación con su tipo
- **AND** queda consultable desde cualquiera de las dos

#### Scenario: Una relación apunta a una norma que no está en el catálogo
- **WHEN** la fuente declara una relación hacia una norma que el catálogo no tiene
- **THEN** el sistema no inventa la norma faltante
- **AND** deja registro de que esa relación quedó sin resolver

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
