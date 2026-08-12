## ADDED Requirements

### Requirement: La cadena de ISO 14001 se recorre completa
El sistema SHALL enlazar proceso, aspecto ambiental, impacto, requisito legal y riesgo, de modo que se pueda recorrer desde una actividad hasta el plan de acción que la trata.

#### Scenario: Desde un aspecto hasta su tratamiento
- **GIVEN** un aspecto ambiental significativo derivado de un proceso
- **WHEN** se consulta ese aspecto
- **THEN** el sistema muestra su impacto, el requisito legal que le aplica y el riesgo u oportunidad que generó

### Requirement: Un aspecto se evalúa en sus tres condiciones de operación
El sistema SHALL registrar los aspectos ambientales distinguiendo operación normal, anormal y de emergencia.

Un derrame no es lo mismo en operación normal que durante una emergencia, y evaluarlos juntos borra justamente el caso que importa.

#### Scenario: El mismo aspecto en emergencia
- **WHEN** se evalúa un aspecto en condición de emergencia
- **THEN** el sistema lo trata como una evaluación distinta de la de operación normal

### Requirement: La significancia se decide con los criterios de la empresa
El sistema SHALL permitir que cada empresa configure sus criterios de significancia y el umbral a partir del cual un aspecto es significativo.

#### Scenario: Cambio de umbral
- **WHEN** una empresa modifica su umbral de significancia
- **THEN** el sistema recalcula qué aspectos son significativos con el criterio nuevo

### Requirement: Cumplimiento y cobertura son indicadores distintos
El sistema SHALL informar por separado qué proporción de los requisitos evaluados se cumple y qué proporción del total fue evaluada.

Un 100 % de cumplimiento sobre el 30 % evaluado no es un buen resultado, y hoy se muestra igual que un 100 % sobre el total.

#### Scenario: Matriz evaluada a medias
- **GIVEN** una matriz con 10 requisitos de los cuales 3 fueron evaluados y los 3 cumplen
- **WHEN** se consultan los indicadores
- **THEN** el sistema informa 100 % de cumplimiento y 30 % de cobertura, no un único número

### Requirement: Un aspecto significativo sin tratar es visible
El sistema SHALL señalar los aspectos significativos que no tienen riesgo, control ni plan de acción asociado.

#### Scenario: Significativo y huérfano
- **WHEN** un aspecto se marca significativo y no tiene tratamiento
- **THEN** el sistema lo muestra como pendiente de tratar

### Requirement: Equipos regulados con habilitación vigente
El sistema SHALL alertar cuando un equipo regulado no tenga operador con certificación vigente o su inscripción esté vencida.

#### Scenario: Certificación vencida
- **WHEN** vence la certificación del único operador habilitado de una caldera
- **THEN** el sistema marca el equipo como sin operador habilitado

### Requirement: La entrega es reversible
El sistema SHALL mantener esta capacidad detrás de una bandera, de modo que apagarla devuelva el comportamiento anterior sin migración de datos.

#### Scenario: Bandera apagada
- **WHEN** la bandera está apagada
- **THEN** el sistema se comporta exactamente como antes de este cambio
