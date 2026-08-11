# Credenciales de acceso

## ADDED Requirements

### Requirement: Invitación de usuario interno
El sistema SHALL crear la identidad en el proveedor y la fila en la base como
un solo acto, de modo que la empresa de la persona invitada quede determinada
por quien invita y no por una configuración manual posterior.

#### Scenario: Un Admin Empresa invita a alguien de su empresa
- **GIVEN** un Admin Empresa autenticado en la empresa A
- **WHEN** invita a una persona indicando correo, nombre y rol
- **THEN** el sistema crea una invitación en el proveedor de identidad con la
  empresa A y el rol ya asociados
- **AND** crea la fila del usuario en la empresa A con estado `invited`
- **AND** la persona recibe un correo para fijar su clave

#### Scenario: La persona invitada entra por primera vez
- **GIVEN** una persona con invitación pendiente
- **WHEN** completa el alta en el proveedor
- **THEN** su fila pasa a estado `active`
- **AND** el sistema la reconoce como parte de la empresa A sin que nadie
  haya escrito la empresa a mano en el proveedor

#### Scenario: El alta en el proveedor falla
- **GIVEN** un Admin Empresa que invita a alguien
- **WHEN** el proveedor de identidad rechaza la invitación o no responde
- **THEN** el sistema no deja creada la fila del usuario
- **AND** informa que la invitación no se pudo emitir

#### Scenario: Alguien sin permiso intenta invitar
- **GIVEN** un usuario autenticado que no es Admin Empresa ni Admin Global
- **WHEN** intenta invitar a otra persona
- **THEN** el sistema rechaza la operación
- **AND** no se crea identidad ni fila

#### Scenario: Un Admin Empresa intenta invitar a otra empresa
- **GIVEN** un Admin Empresa de la empresa A
- **WHEN** intenta invitar indicando la empresa B
- **THEN** el sistema rechaza la operación

### Requirement: Clave local con RUT
El sistema SHALL permitir que un usuario interno que ya entra con un proveedor
externo se fije una clave local y desde entonces ingrese con su RUT, sin
perder el acceso que ya tenía.

#### Scenario: Fijar la clave local
- **GIVEN** un usuario interno autenticado que entró con un proveedor externo
- **WHEN** registra su RUT y una clave
- **THEN** el sistema acepta el RUT solo si su dígito verificador es válido
- **AND** desde ese momento el usuario puede ingresar con RUT y clave

#### Scenario: Ingresar con RUT
- **GIVEN** un usuario con clave local fijada
- **WHEN** ingresa su RUT y su clave
- **THEN** obtiene la misma sesión y los mismos permisos que si hubiera
  entrado con el proveedor externo

#### Scenario: El RUT se escribe en cualquier formato
- **GIVEN** un usuario cuyo RUT es 12.345.678-9
- **WHEN** lo escribe como `12.345.678-9`, `12345678-9` o `123456789`
- **THEN** el sistema lo reconoce como el mismo RUT

#### Scenario: RUT con dígito verificador inválido
- **GIVEN** un usuario fijando su clave local
- **WHEN** registra un RUT cuyo dígito verificador no corresponde
- **THEN** el sistema lo rechaza antes de enviarlo
- **AND** explica que el RUT no es válido

#### Scenario: RUT ya usado por otra persona
- **GIVEN** un RUT ya registrado por otro usuario
- **WHEN** una segunda persona intenta registrarlo
- **THEN** el sistema rechaza el registro
- **AND** no revela de quién es la cuenta existente

#### Scenario: Conservar el acceso anterior
- **GIVEN** un usuario que fijó clave local
- **WHEN** vuelve a ingresar con su proveedor externo
- **THEN** el ingreso sigue funcionando

### Requirement: Acceso temporal del Cliente Invitado
El sistema SHALL entregar al Cliente Invitado credenciales reales, verificables
y de vigencia acotada, sin exigirle una cuenta previa y sin darle acceso a los
datos de negocio de la empresa.

#### Scenario: Generar el acceso desde el link público
- **GIVEN** una persona sin cuenta que abre el acceso de invitado de una empresa
- **WHEN** solicita generar su acceso
- **THEN** el sistema le entrega un RUT y una clave que quedan registrados
- **AND** le indica hasta cuándo son válidos

#### Scenario: Volver con credenciales de una visita anterior
- **GIVEN** un Cliente Invitado con credenciales vigentes
- **WHEN** ingresa su RUT y su clave
- **THEN** accede al seguimiento de sus propias solicitudes

#### Scenario: Credenciales vencidas
- **GIVEN** un Cliente Invitado cuyas credenciales caducaron
- **WHEN** intenta ingresar
- **THEN** el sistema le niega el acceso
- **AND** le ofrece generar un acceso nuevo

#### Scenario: Credenciales inventadas
- **GIVEN** cualquier persona
- **WHEN** ingresa un RUT y una clave que el sistema nunca emitió
- **THEN** el sistema le niega el acceso

#### Scenario: El invitado no alcanza los datos de negocio
- **GIVEN** un Cliente Invitado con credenciales vigentes
- **WHEN** intenta acceder a cualquier pantalla o dato de negocio de la empresa
- **THEN** el sistema se lo niega, aunque conozca la dirección exacta

#### Scenario: El invitado no ve las solicitudes de otros
- **GIVEN** dos Clientes Invitados de la misma empresa
- **WHEN** uno intenta ver una solicitud del otro
- **THEN** el sistema se lo niega

#### Scenario: Un invitado no cruza de empresa
- **GIVEN** un Cliente Invitado con acceso a la empresa A
- **WHEN** intenta usar sus credenciales contra la empresa B
- **THEN** el sistema se lo niega
