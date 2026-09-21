# rbac Specification

## Purpose
TBD - created by archiving change sistema-actores-roles-rbac. Update Purpose after archive.
## Requirements
### Requirement: El permiso efectivo combina rol y excepción individual
El sistema SHALL resolver qué puede hacer un usuario uniendo los permisos de sus roles vigentes con las concesiones o denegaciones asignadas a él en particular, y SHALL hacer que una denegación explícita gane sobre cualquier concesión.

Es lo que permite quitarle **un** permiso a alguien sin sacarlo del rol ni inventar un rol de excepción por cada caso.

#### Scenario: Denegación individual sobre un rol que concede
- **GIVEN** un usuario cuyo rol concede un permiso
- **WHEN** se le deniega ese permiso individualmente
- **THEN** el sistema le niega la acción, sin alterar el rol ni afectar a los demás usuarios que lo tienen

#### Scenario: Concesión individual sobre un rol que no concede
- **WHEN** se le concede a un usuario un permiso que su rol no incluye
- **THEN** el sistema le permite la acción

#### Scenario: Toda excepción queda justificada
- **WHEN** se concede o deniega un permiso fuera del rol
- **THEN** el sistema registra quién lo hizo, cuándo y por qué

### Requirement: El alcance de un rol puede acotarse
El sistema SHALL permitir asignar un rol acotado a una planta o un departamento, no solo a la empresa completa.

#### Scenario: Encargado de una sola planta
- **GIVEN** un usuario con rol acotado a una planta
- **WHEN** consulta datos de otra planta de la misma empresa
- **THEN** el sistema no se los muestra

### Requirement: El permiso se verifica en el servidor
El sistema SHALL comprobar los permisos en la API, y SHALL considerar la interfaz solo como una ayuda visual.

Ocultar un botón no es un control de acceso: quien conozca la ruta la llama igual.

#### Scenario: Llamada directa sin permiso
- **WHEN** un usuario sin permiso llama directamente al endpoint correspondiente
- **THEN** el sistema la rechaza aunque la interfaz nunca le hubiera mostrado la opción

### Requirement: Un gestor accede a su cliente solo por concesión explícita
El sistema SHALL exigir una concesión de acceso registrada y acotada para que una consultora vea datos de la empresa que gestiona, y SHALL permitir revocarla.

Que exista un contrato no basta: el acceso tiene que ser un permiso concreto, auditable y reversible.

#### Scenario: Gestor sin concesión vigente
- **WHEN** una consultora intenta leer datos de un cliente sin concesión activa
- **THEN** el sistema se los niega

#### Scenario: Revocación
- **GIVEN** una consultora con acceso concedido
- **WHEN** se revoca la concesión
- **THEN** deja de ver los datos de inmediato

#### Scenario: El cliente de una consultora es una empresa real
- **GIVEN** un contrato entre una consultora y su cliente
- **THEN** el cliente es una empresa con su propio aislamiento, no una partición dentro de la consultora
- **AND** la consultora sólo la alcanza declarándola explícitamente en cada petición

**El escenario decía "una consultora crea un cliente" y eso se corrigió el
10-sep.** Crear la empresa es hoy del Admin Global, y que la consultora pueda
darla de alta ella misma es **RF-65 (#59)**, que sigue abierto — es un requisito
propio y no un detalle de éste, que trata del *acceso*.

Lo que sí se verificó, que es la garantía que importa: `parent_tenant_id` tiene
**cero filas**, así que ningún cliente existe como partición; los dos tenants
del sistema son empresas completas con su propia política de RLS.

### Requirement: Acceso de cliente invitado acotado y temporal
El sistema SHALL permitir que un tercero acceda con credenciales generadas para él, limitadas a crear y seguir sus solicitudes, y SHALL hacer que esas credenciales caduquen.

#### Scenario: Invitado intenta entrar al negocio
- **WHEN** un cliente invitado navega a una pantalla de negocio
- **THEN** el sistema lo devuelve a sus solicitudes

#### Scenario: Credenciales caducadas
- **WHEN** un invitado intenta entrar con credenciales vencidas
- **THEN** el sistema las rechaza

### Requirement: El administrador global no edita datos de las empresas
El sistema SHALL impedir que el rol de plataforma modifique contenido de negocio de un cliente.

#### Scenario: Intento de edición desde plataforma
- **WHEN** un administrador global intenta modificar una obligación de una empresa
- **THEN** el sistema lo rechaza, aunque pueda ver la empresa para administrarla

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
