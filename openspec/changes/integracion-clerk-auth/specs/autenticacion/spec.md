## ADDED Requirements

### Requirement: La identidad se verifica, no se declara
El sistema SHALL determinar la empresa de la sesión a partir de una credencial firmada por el proveedor de identidad, y SHALL rechazar cualquier valor de empresa que llegue sin firmar.

Es el requisito que justifica todo el cambio: mientras la empresa se declare en una cabecera, cualquiera puede leer datos de otra fabricándola, y el aislamiento de la base no sirve de nada porque el dato de entrada es mentira.

#### Scenario: Una cabecera no puede sobreescribir la credencial
- **GIVEN** un usuario con credencial válida de la empresa A
- **WHEN** envía además una cabecera declarando la empresa B
- **THEN** el sistema opera sobre la empresa A y ignora la cabecera

#### Scenario: Una credencial de otro emisor no sirve
- **WHEN** llega una credencial firmada por una instancia distinta del proveedor
- **THEN** el sistema la rechaza con 401

#### Scenario: Una credencial vencida o alterada se rechaza
- **WHEN** la credencial está expirada, mal firmada o le falta la empresa
- **THEN** el sistema responde 401 sin distinguir el motivo hacia afuera

### Requirement: Modo de desarrollo sin proveedor
El sistema SHALL permitir levantar el proyecto sin cuenta del proveedor de identidad, y SHALL gobernar ese modo con una única variable de configuración.

Una sola variable y no un interruptor por endpoint: con criterios distintos en cada uno de los 94 endpoints habría 94 formas de dejar un hueco.

#### Scenario: Sin configurar el proveedor se acepta la cabecera
- **GIVEN** el proveedor de identidad sin configurar
- **WHEN** un desarrollador consulta la API declarando su empresa por cabecera
- **THEN** el sistema la acepta y responde con los datos de esa empresa

#### Scenario: Con el proveedor configurado no queda camino sin firma
- **GIVEN** el proveedor configurado
- **WHEN** llega una petición sin credencial
- **THEN** el sistema responde 401 aunque venga la cabecera

#### Scenario: Producción no arranca sin el proveedor
- **WHEN** se despliega a producción sin configurar el proveedor
- **THEN** el despliegue falla al arrancar en vez de quedar sin autenticación

### Requirement: No poder verificar es distinto de no estar autenticado
El sistema SHALL responder 503 cuando no puede comprobar una credencial por razones propias, y reservar el 401 para credenciales que efectivamente no son válidas.

Un 401 en ese caso mandaría a re-autenticarse a gente cuya sesión está bien, y el re-login tampoco funcionaría porque el problema no es la sesión.

#### Scenario: El proveedor está caído y no hay copia local
- **WHEN** el sistema no puede obtener las llaves públicas y no tiene copia previa
- **THEN** responde 503, no 401

#### Scenario: El proveedor está caído pero hay copia local
- **GIVEN** una copia de las llaves obtenida antes, aunque esté vencida
- **WHEN** el proveedor deja de responder
- **THEN** el sistema sigue verificando credenciales con esa copia

### Requirement: Los usuarios del proveedor se reflejan en el sistema
El sistema SHALL mantener sus usuarios sincronizados con el proveedor de identidad mediante eventos firmados, y SHALL rechazar los eventos cuya firma no pueda comprobar.

#### Scenario: Un usuario nuevo aparece en el sistema
- **WHEN** llega un evento firmado de alta de usuario con su empresa
- **THEN** el sistema crea el usuario con su correo, nombre y empresa

#### Scenario: Un evento con firma inválida no cambia nada
- **WHEN** llega un evento sin firma, con firma de otro secreto, o con el cuerpo alterado después de firmarse
- **THEN** el sistema lo rechaza y no modifica ningún usuario

#### Scenario: Un evento que no interesa no se reintenta para siempre
- **WHEN** llega un evento de un tipo que el sistema no usa
- **THEN** responde con éxito y lo ignora

#### Scenario: Un evento incompleto no se reintenta para siempre
- **WHEN** llega un evento firmado pero sin la empresa del usuario
- **THEN** el sistema lo rechaza como petición inválida, no como error propio

### Requirement: Un usuario ya existente se adopta, no se duplica
El sistema SHALL vincular un usuario del proveedor con el registro que ya exista para ese mismo correo, en vez de crear uno nuevo.

Sin esto, la primera entrada de alguien que ya estaba en la base choca contra la unicidad del correo y la sincronización queda fallando en bucle.

#### Scenario: Alguien que estaba antes del proveedor entra por primera vez
- **GIVEN** un usuario creado directamente en el sistema, sin vínculo con el proveedor
- **WHEN** esa persona entra por primera vez con el proveedor
- **THEN** el sistema vincula ambos registros y no crea un duplicado
- **AND** si estaba invitado, pasa a activo

### Requirement: Lo que configuró un administrador no lo pisa el proveedor
El sistema SHALL conservar la empresa y el rol asignados localmente cuando el proveedor informa una actualización del usuario.

#### Scenario: Un cambio de perfil en el proveedor no revierte permisos
- **GIVEN** un usuario al que un administrador le cambió el rol en el sistema
- **WHEN** esa persona cambia su foto o su nombre en el proveedor
- **THEN** el sistema actualiza nombre y correo pero mantiene su rol y su empresa

### Requirement: Eliminar en el proveedor no borra el historial
El sistema SHALL retirar el acceso de un usuario eliminado en el proveedor conservando su registro y todo lo que tenga asociado.

El registro de auditoría referencia al usuario. Borrarlo dejaría huérfano el historial que el sistema está obligado a conservar (RNF-08).

#### Scenario: Un usuario eliminado en el proveedor
- **WHEN** el proveedor informa que un usuario fue eliminado
- **THEN** el sistema le retira el acceso
- **AND** su registro sigue existiendo y su historial sigue siendo consultable

### Requirement: Inicio de sesión con cuenta corporativa
El sistema SHALL permitir iniciar sesión con correo y contraseña, con Microsoft y con Google, y SHALL redirigir al inicio de sesión a quien intente entrar a una pantalla sin sesión.

#### Scenario: Acceso sin sesión
- **WHEN** alguien sin sesión abre una pantalla del sistema
- **THEN** se le redirige al inicio de sesión

#### Scenario: Ingreso con proveedor corporativo
- **WHEN** un usuario entra con Microsoft o con Google
- **THEN** accede al tablero de su empresa con los mismos datos que si hubiera entrado con correo y contraseña
