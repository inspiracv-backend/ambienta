# Plan de acción — tareas

## ADDED Requirements

### Requirement: Una tarea puede pertenecer a un plan de acción
El sistema SHALL permitir que una tarea quede asociada a un plan de acción, y
SHALL conservar esa asociación entre sesiones.

Hoy marcar una tarea se ve en pantalla y se pierde al recargar, porque no existe
ningún campo donde guardarla.

#### Scenario: Se crea una tarea dentro de un plan
- **GIVEN** un plan de acción de la empresa
- **WHEN** se crea una tarea indicando ese plan
- **THEN** la tarea queda asociada al plan
- **AND** aparece al volver a consultar las tareas de ese plan

#### Scenario: El estado sobrevive a la recarga
- **GIVEN** una tarea de un plan, sin completar
- **WHEN** se marca como completada
- **AND** se vuelve a consultar el plan
- **THEN** la tarea sigue completada

### Requirement: Una tarea cuelga de una sola cosa
El sistema SHALL rechazar una tarea que referencie a la vez una obligación y un
plan de acción.

Con las dos referencias, la misma tarea aparecería dos veces en la lista de lo
que le toca a una persona y contaría dos veces en la tasa de cierre del informe.

#### Scenario: Se rechaza la tarea con dos padres
- **GIVEN** una obligación y un plan de acción de la misma empresa
- **WHEN** se intenta crear una tarea que referencia a las dos
- **THEN** el sistema la rechaza indicando que una tarea cuelga de una sola cosa

#### Scenario: Una tarea sin ningún padre se acepta
- **GIVEN** una empresa
- **WHEN** se crea una tarea sin obligación ni plan de acción
- **THEN** el sistema la acepta

Una tarea suelta es legítima: alguien anota algo que hay que hacer antes de saber
de qué cuelga. Prohibirlo obligaría a inventar un padre.

### Requirement: Cada tarea puede tener su propia persona responsable
El sistema SHALL permitir asignar cada tarea de un plan a una persona distinta.

Es lo que RF-97 pide al hablar de cinco etapas **con responsable por etapa**: sin
esto, un plan entero tiene un solo dueño y las etapas no se pueden repartir.

#### Scenario: Dos tareas del mismo plan, dos responsables
- **GIVEN** un plan de acción con dos tareas
- **WHEN** se asigna cada una a una persona distinta de la empresa
- **THEN** cada tarea queda con su responsable
- **AND** el responsable del plan no cambia

#### Scenario: Una tarea sin responsable se acepta
- **GIVEN** un plan de acción
- **WHEN** se crea una tarea sin indicar responsable
- **THEN** el sistema la acepta

Exigir responsable al crear haría que una tarea que alguien todavía no sabe a
quién asignar se anote en un papel, que es lo que este módulo existe para evitar.

### Requirement: Lo que le toca a una persona se consulta entre planes
El sistema SHALL permitir consultar las tareas asignadas a una persona sin
indicar de qué plan u obligación cuelgan.

Es la consulta que una lista embebida en el plan no permite: hoy habría que abrir
plan por plan para saber qué le toca a alguien.

#### Scenario: Una persona con tareas en dos planes distintos
- **GIVEN** dos planes de acción, cada uno con una tarea asignada a la misma persona
- **WHEN** se consultan las tareas de esa persona
- **THEN** el resultado incluye las dos

#### Scenario: Las tareas de otra persona no aparecen
- **GIVEN** dos personas de la empresa, cada una con una tarea asignada
- **WHEN** se consultan las tareas de la primera
- **THEN** el resultado no incluye la de la segunda

### Requirement: Una empresa no ve ni toca las tareas de otra
El sistema SHALL impedir que una empresa lea, cree o modifique tareas asociadas
a planes de acción de otra empresa.

#### Scenario: No se ven las tareas de otra empresa
- **GIVEN** un plan de acción con tareas en la empresa A
- **WHEN** la empresa B consulta las tareas de ese plan
- **THEN** el sistema no devuelve ninguna

#### Scenario: No se puede colgar una tarea del plan de otra empresa
- **GIVEN** un plan de acción de la empresa A
- **WHEN** la empresa B intenta crear una tarea indicando ese plan
- **THEN** el sistema rechaza la operación

#### Scenario: Un plan inexistente y uno ajeno responden igual
- **GIVEN** la empresa B
- **WHEN** intenta crear una tarea indicando un identificador de plan inventado
- **AND** cuando lo intenta indicando el identificador real de un plan de la empresa A
- **THEN** el sistema responde lo mismo en los dos casos

Respuestas distintas permitirían distinguir «no existe» de «existe pero es de
otro», y con eso enumerar identificadores ajenos sin verlos nunca.

### Requirement: Retirar un plan no borra el rastro de sus tareas
El sistema SHALL conservar las tareas de un plan de acción retirado.

Un plan de acción es la respuesta de la empresa ante un hallazgo, y sus tareas
son la evidencia de lo que se hizo. Borrarlas al retirar el plan destruiría lo
que una auditoría del periodo va a pedir.

#### Scenario: Las tareas sobreviven al retiro del plan
- **GIVEN** un plan de acción con tareas
- **WHEN** se retira el plan
- **THEN** las tareas siguen existiendo asociadas a él
