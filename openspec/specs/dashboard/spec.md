# Tablero de cumplimiento

## Purpose

Lo primero que ve un Admin Empresa al entrar: en qué estado está su cumplimiento
ambiental hoy y qué se le viene encima (S-06 y S-07, RF-47 a RF-49).

No es un módulo con datos propios. Lee de matriz legal, obligaciones y no
conformidades, y su trabajo es **agregar**: convertir miles de filas en los seis
números que permiten decidir dónde mirar primero.

Por eso las decisiones difíciles de esta capacidad son de conteo, no de
almacenamiento — qué entra en el denominador de un porcentaje y qué estado
cuenta como pendiente. Esas reglas están abajo, y cada una existe porque la
alternativa daba un número que se leía bien y era falso.

## Requirements
### Requirement: Métricas del tablero en una sola llamada
El sistema SHALL exponer todas las métricas de S-06 y S-07 en un único endpoint agregado, resolviéndolas en la base de datos y no en el navegador.

El tablero necesita conteos, no listas. Pedir las obligaciones completas para contarlas en el cliente no escala con volúmenes reales.

#### Scenario: El tablero se carga con una sola petición
- **WHEN** un usuario autenticado abre el tablero
- **THEN** el sistema responde con cumplimiento global, contadores, próximo vencimiento crítico y métricas por planta en una sola respuesta
- **AND** el tiempo de respuesta es menor a 500 ms con datos de una empresa típica

#### Scenario: El costo no crece con la cantidad de plantas
- **WHEN** una empresa tiene cinco plantas en vez de una
- **THEN** el sistema resuelve la respuesta con la misma cantidad de consultas a la base

### Requirement: Aislamiento de métricas entre empresas
El sistema SHALL calcular las métricas únicamente sobre datos de la empresa de la sesión.

#### Scenario: Dos empresas ven números distintos
- **GIVEN** la empresa A tiene 5 obligaciones y 1 no conformidad, y la empresa B no tiene ninguna
- **WHEN** cada una consulta sus métricas
- **THEN** la empresa A recibe sus 5 obligaciones y su no conformidad
- **AND** la empresa B recibe cero en todos los contadores
- **AND** ninguna de las dos ve plantas de la otra

### Requirement: Porcentaje de cumplimiento sobre artículos aplicables
El sistema SHALL calcular el porcentaje de cumplimiento excluyendo del denominador los artículos marcados como no aplicables, y manteniendo dentro los pendientes de evaluar.

Un requisito que no aplica no puede cumplirse ni incumplirse, y dejarlo dentro hunde el indicador de una empresa a la que le apliquen pocos artículos de una norma grande. Los pendientes sí cuentan: si no, una matriz con un solo artículo evaluado mostraría 100 %.

#### Scenario: Un artículo no aplicable sale del cálculo
- **GIVEN** una matriz con 6 artículos: 2 que cumplen, 1 que no cumple, 1 parcial, 1 pendiente y 1 no aplicable
- **WHEN** se consulta el cumplimiento global
- **THEN** el sistema informa 40,0 % — dos que cumplen sobre cinco evaluables
- **AND** informa 5 artículos evaluados, no 6

#### Scenario: Un cumplimiento parcial no cuenta como cumplido
- **WHEN** un artículo está marcado como parcial
- **THEN** cuenta en el denominador pero no en el numerador

### Requirement: Obligaciones pendientes por exclusión
El sistema SHALL considerar pendiente toda obligación que no esté aceptada ni cerrada.

Definirlo por exclusión y no por lista blanca evita que agregar un estado nuevo al modelo lo deje fuera del tablero en silencio.

#### Scenario: Una obligación en curso sigue contando
- **GIVEN** una obligación en la que alguien ya empezó a trabajar
- **WHEN** se consultan los contadores
- **THEN** la obligación sigue apareciendo como pendiente

#### Scenario: Una obligación aceptada deja de pesar
- **WHEN** una obligación pasa a aceptada o cerrada
- **THEN** desaparece de los contadores de pendientes

### Requirement: Días restantes redondeados hacia arriba
El sistema SHALL informar los días que faltan para un vencimiento redondeando hacia arriba, y en negativo cuando ya venció.

#### Scenario: Menos de un día todavía es un día
- **WHEN** una obligación vence en 20 horas
- **THEN** el sistema informa 1 día restante, no 0

#### Scenario: Una obligación vencida informa negativo
- **WHEN** una obligación venció hace 20 días
- **THEN** el sistema informa −20 días
- **AND** el tablero la muestra con el semáforo de vencida

### Requirement: Las plantas sin datos aparecen en el tablero
El sistema SHALL incluir en el desglose por planta a todas las plantas activas de la empresa, incluidas las que no tienen nada cargado.

Una planta vacía es justamente la que conviene ver: si se parte de las obligaciones en vez de las plantas, desaparece del tablero.

#### Scenario: Una planta recién creada aparece en cero
- **GIVEN** una empresa con cuatro plantas, de las cuales solo una tiene obligaciones
- **WHEN** se consulta el tablero
- **THEN** las cuatro plantas aparecen en el desglose
- **AND** las tres sin datos muestran 0 % y contadores en cero

### Requirement: El tablero no se cae si la API no responde
El sistema SHALL mostrar el tablero con datos de respaldo y avisar explícitamente que no son reales cuando no puede obtener las métricas.

#### Scenario: Falla la carga de métricas
- **WHEN** la petición de métricas falla
- **THEN** el tablero muestra un aviso de que no se pudo conectar y que los números son de ejemplo
- **AND** ofrece reintentar
- **AND** no queda en blanco ni lanza un error al usuario

#### Scenario: El usuario reintenta y la API responde
- **GIVEN** el tablero mostrando el aviso de sin conexión
- **WHEN** el usuario reintenta y la API responde
- **THEN** el aviso desaparece y se muestran los datos reales

