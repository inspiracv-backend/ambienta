# Autenticación

## MODIFIED Requirements

### Requirement: Inicio de sesión con cuenta corporativa
El sistema SHALL permitir iniciar sesión con correo y contraseña, con Microsoft
y con Google, y SHALL redirigir al inicio de sesión a quien intente entrar a una
pantalla sin sesión.

Autenticarse con un proveedor corporativo demuestra **quién es** la persona, no
que pertenezca a una empresa del sistema. Son dos hechos distintos y el sistema
los trata por separado.

#### Scenario: Acceso sin sesión
- **WHEN** alguien sin sesión abre una pantalla del sistema
- **THEN** se le redirige al inicio de sesión

#### Scenario: Ingreso con proveedor corporativo
- **GIVEN** una persona ya dada de alta en una empresa
- **WHEN** entra con Microsoft o con Google
- **THEN** accede al tablero de su empresa con los mismos datos que si hubiera
  entrado con correo y contraseña

#### Scenario: La misma persona alterna entre proveedores
- **GIVEN** una persona dada de alta con un correo determinado
- **WHEN** entra unas veces con Microsoft y otras con Google usando ese mismo correo
- **THEN** el sistema la reconoce como la misma persona
- **AND** no se crea un segundo registro con el mismo correo

#### Scenario: Autenticación válida de alguien sin empresa
- **GIVEN** una persona que el proveedor autentica correctamente
- **WHEN** su correo no corresponde a ninguna persona dada de alta
- **THEN** el sistema no le muestra datos de ninguna empresa
- **AND** le explica que su cuenta no está asociada a ninguna empresa

## ADDED Requirements

### Requirement: El alta la hace la empresa, no la persona
El sistema SHALL impedir que alguien se dé de alta por su cuenta, de modo que
pertenecer a una empresa sea siempre consecuencia de que alguien de esa empresa
lo haya decidido.

Con registro abierto, cualquiera con un correo válido queda dentro del sistema.
El proveedor de identidad comprueba que el correo es suyo, no que la persona
tenga nada que ver con la empresa.

#### Scenario: Intento de registro propio
- **WHEN** alguien intenta crear una cuenta por su cuenta desde el sistema
- **THEN** el sistema no se lo permite
- **AND** le indica que el acceso lo habilita la empresa

#### Scenario: Autenticarse no es darse de alta
- **GIVEN** una persona con una cuenta corporativa válida y sin alta en el sistema
- **WHEN** se autentica con su proveedor
- **THEN** el sistema no la incorpora a ninguna empresa

#### Scenario: Alguien dado de alta entra por primera vez
- **GIVEN** una persona a la que un Admin Empresa dio de alta
- **WHEN** entra por primera vez con su proveedor corporativo
- **THEN** el sistema la reconoce como parte de esa empresa
- **AND** su acceso queda activo

### Requirement: Sesión válida sin empresa asignada
El sistema SHALL distinguir una sesión que no puede verificarse de una que se
verificó correctamente pero no tiene empresa asociada, y SHALL informar el
segundo caso en pantalla en vez de mostrar un sistema vacío.

Son dos fallos con causas y remedios opuestos: uno se arregla volviendo a
entrar, el otro solo lo arregla un administrador. Tratarlos igual produce un
sistema que parece funcionar y no muestra nada, sin decir por qué — y quien lo
sufre no tiene forma de saber a quién pedirle ayuda.

#### Scenario: Se explica el motivo
- **GIVEN** una persona con sesión válida y sin empresa asignada
- **WHEN** abre cualquier pantalla del sistema
- **THEN** el sistema le explica que su cuenta no está asociada a ninguna empresa
- **AND** le indica que debe pedir el acceso a un administrador de su empresa

#### Scenario: No se la manda a iniciar sesión otra vez
- **GIVEN** una persona con sesión válida y sin empresa asignada
- **WHEN** el sistema detecta que no puede mostrarle datos
- **THEN** no la redirige al inicio de sesión
- **AND** no queda alternando entre el inicio de sesión y el sistema

#### Scenario: Puede cerrar sesión
- **GIVEN** una persona con sesión válida y sin empresa asignada
- **WHEN** decide salir
- **THEN** el sistema le permite cerrar la sesión

#### Scenario: No alcanza datos de ninguna empresa
- **GIVEN** una persona con sesión válida y sin empresa asignada
- **WHEN** intenta acceder a un dato de negocio conociendo su dirección exacta
- **THEN** el sistema se lo niega

#### Scenario: Recupera el acceso al ser dada de alta
- **GIVEN** una persona con sesión válida y sin empresa asignada
- **WHEN** un Admin Empresa la da de alta y ella vuelve a entrar
- **THEN** accede al tablero de esa empresa con normalidad
