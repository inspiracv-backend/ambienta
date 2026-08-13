# Escrituras de la interfaz

## ADDED Requirements

### Requirement: Lo que la pantalla muestra corresponde a lo guardado
El sistema SHALL asegurar que un cambio visible en la interfaz esté guardado, o
que la persona se entere de que no lo está.

Una escritura que falla en silencio deja la pantalla afirmando algo falso: el
cambio se ve, y desaparece al recargar sin que nadie sepa por qué. Es peor que
un error visible, porque nadie lo investiga hasta que un cliente reclama por un
dato que "sí había guardado".

#### Scenario: El cambio se guarda
- **GIVEN** un usuario que edita un registro
- **WHEN** el sistema acepta el cambio
- **THEN** la pantalla refleja el nuevo valor
- **AND** el valor sigue ahí al volver a cargar la pantalla

#### Scenario: El cambio no se puede guardar
- **GIVEN** un usuario que edita un registro
- **WHEN** el sistema rechaza el cambio
- **THEN** la pantalla vuelve a mostrar el valor anterior
- **AND** se le explica por qué no se pudo guardar

#### Scenario: El cambio se muestra antes de confirmarse
- **WHEN** un usuario edita un registro
- **THEN** la pantalla puede mostrar el cambio de inmediato, sin esperar la confirmación
- **AND** si después se rechaza, lo revierte

#### Scenario: Una parte falla y otra no
- **GIVEN** una acción que guarda varios registros a la vez
- **WHEN** algunos se guardan y otros no
- **THEN** el sistema revierte únicamente los que fallaron
- **AND** informa cuántos quedaron sin guardar

### Requirement: Un campo editable se lee de donde se guarda
El sistema SHALL leer cada campo editable de la misma fuente donde lo escribe.

Un campo que se escribe en la base pero se lee de un valor fijo del código
produce el mismo engaño que no guardarlo: la pantalla confirma el cambio y al
recargar aparece el valor de siempre. La escritura sola no basta.

#### Scenario: El valor sobrevive a la recarga
- **GIVEN** un campo que un usuario puede editar
- **WHEN** lo cambia y vuelve a abrir la pantalla
- **THEN** ve el valor que guardó, no un valor por defecto

#### Scenario: Un campo que la aplicación no puede guardar no se ofrece como editable
- **GIVEN** un dato que el sistema no tiene dónde persistir
- **WHEN** se diseña la pantalla que lo muestra
- **THEN** no se presenta como editable

### Requirement: El motivo del rechazo llega en un formato estable
El sistema SHALL exponer el motivo de un rechazo de forma que la interfaz pueda
distinguir los casos sin interpretar el texto del mensaje.

El texto es para personas: se traduce y se reescribe. Una interfaz que ramifica
sobre él se rompe la primera vez que alguien mejora la redacción.

#### Scenario: Un valor duplicado
- **WHEN** una escritura choca con un valor que ya existe
- **THEN** la persona ve un mensaje que nombra el valor duplicado

#### Scenario: Un campo inválido
- **WHEN** una escritura se rechaza por validación
- **THEN** la persona ve qué campo falló y por qué

#### Scenario: Sin conexión con el servidor
- **WHEN** la petición no llega a destino
- **THEN** el mensaje distingue no haber podido contactar de haber sido rechazado
