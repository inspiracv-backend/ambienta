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

### Requirement: La significancia se decide con un criterio explícito
El sistema SHALL decidir si un aspecto es significativo con un criterio único y declarado —frecuencia × severidad desde 25, o un requisito legal de nivel 8 o más— y SHALL informar el motivo de cada veredicto.

En la v1.0 el criterio es el del sistema para todas las empresas (plan de cierre, §6, decisión 8 del 21-sep). Que cada empresa configure el suyo queda para después del piloto. Lo que no se negocia es el motivo: en una auditoría la pregunta no es si el aspecto es significativo sino por qué.

#### Scenario: Aspecto de magnitud baja con obligación legal
- **GIVEN** un aspecto con frecuencia × severidad bajo el umbral y un requisito legal de nivel 8
- **WHEN** se evalúa su significancia
- **THEN** el sistema lo declara significativo y dice que es por el requisito legal

#### Scenario: Faltan puntajes
- **WHEN** se pide evaluar un aspecto sin los tres puntajes
- **THEN** el sistema no lo declara ni significativo ni no significativo: queda sin evaluar

### Requirement: Cumplimiento y cobertura son indicadores distintos
El sistema SHALL informar, al lado del porcentaje de cumplimiento, qué proporción de los requisitos aplicables ya fue evaluada.

El cumplimiento se calcula sobre los requisitos aplicables, con los no evaluados en el denominador —la misma definición que el tablero y que el §6 del design—: así una matriz evaluada a medias no puede mostrar 100 %. La cobertura va al lado porque un cumplimiento bajo puede ser incumplimiento o falta de evaluación, y el número solo no lo distingue. Decidido el 21-sep (plan de cierre, §6, decisión 3).

#### Scenario: Matriz evaluada a medias
- **GIVEN** una matriz con 10 requisitos aplicables de los cuales 3 fueron evaluados y los 3 cumplen
- **WHEN** se consultan los indicadores
- **THEN** el sistema informa 30 % de cumplimiento y 30 % de cobertura, no un único número

#### Scenario: Nada evaluado todavía
- **GIVEN** una matriz con requisitos aplicables y ninguno evaluado
- **WHEN** se consultan los indicadores
- **THEN** el cumplimiento se informa como sin evaluar, no como 0 %, y la cobertura como 0 %

### Requirement: Un aspecto significativo sin tratar es visible
El sistema SHALL señalar los aspectos significativos que no tienen un riesgo u oportunidad asociado, y SHALL usar el mismo criterio en todas las pantallas y reportes.

El tratamiento pasa por el riesgo u oportunidad (§6.1.1 pide determinarlos para los aspectos, y el riesgo lleva el tratamiento y su plan de acción). Los controles de un aspecto son una lista de texto libre, sin responsable ni verificación, y el requisito legal que le aplica no es una acción sobre él: ninguno de los dos cuenta como tratamiento. Hasta el 21-sep la tabla y el panel usaban criterios distintos para el mismo aspecto.

#### Scenario: Significativo y huérfano
- **WHEN** un aspecto se marca significativo y ningún riesgo u oportunidad lo trata
- **THEN** el sistema lo muestra como pendiente de tratar, en el panel y en la tabla

#### Scenario: Con requisito legal y sin riesgo
- **GIVEN** un aspecto significativo enlazado a un requisito legal y a ningún riesgo
- **WHEN** se consulta
- **THEN** el sistema lo sigue mostrando como pendiente de tratar

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
