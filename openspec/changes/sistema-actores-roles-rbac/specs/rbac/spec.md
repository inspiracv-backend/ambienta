## ADDED Requirements

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

#### Scenario: El sub-tenant es una empresa real
- **WHEN** una consultora crea un cliente a partir de un contrato
- **THEN** ese cliente queda aislado como cualquier otra empresa, no como una partición dentro de la consultora

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
