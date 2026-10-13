## ADDED Requirements

### Requirement: Una empresa suspendida o cerrada queda en solo lectura
El sistema SHALL rechazar toda escritura de una empresa en estado suspendido o cerrado, y SHALL seguir permitiéndole leer y exportar.

Suspender no es quitarle los datos a la empresa: tiene que poder sacar lo suyo y regularizar. El rechazo lleva un código propio, distinto del de permiso insuficiente, porque no le falta un permiso que alguien de la empresa pueda concederle.

#### Scenario: Escritura en una empresa suspendida
- **GIVEN** una empresa suspendida
- **WHEN** alguien de esa empresa intenta crear, modificar o borrar un registro
- **THEN** el sistema lo rechaza con el código de empresa en solo lectura

#### Scenario: Lectura en una empresa suspendida
- **GIVEN** una empresa suspendida
- **WHEN** alguien de esa empresa consulta o exporta sus registros
- **THEN** el sistema responde como a una empresa activa

#### Scenario: Un gestor y su cliente
- **GIVEN** un gestor activo que actúa por un cliente suspendido, o un gestor suspendido que actúa por un cliente activo
- **WHEN** intenta escribir
- **THEN** el sistema lo rechaza en los dos casos

#### Scenario: Reactivación desde la plataforma
- **WHEN** el administrador global reactiva una empresa suspendida
- **THEN** el sistema lo permite

### Requirement: Los avisos de una empresa en solo lectura se pausan
El sistema SHALL dejar de generar y de despachar avisos para una empresa suspendida o cerrada, y SHALL informarlo en el resultado de la corrida.

#### Scenario: Corrida con una empresa suspendida
- **GIVEN** una empresa suspendida con vencimientos dentro de las ventanas de aviso
- **WHEN** corre la tarea de avisos
- **THEN** no se generan ni despachan avisos para esa empresa
- **AND** la corrida informa cuántas empresas quedaron en pausa
