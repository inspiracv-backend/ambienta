## ADDED Requirements

### Requirement: El registro de mejora es la raíz, no el hallazgo
El sistema SHALL tratar el registro de mejora como la entidad principal del ciclo de tratamiento, y SHALL admitir que nazca de una auditoría, de un hallazgo propio o de la revisión anual.

La auditoría es una de tres fuentes, no la única. La mayoría de los registros no viene de una auditoría, y colgarlos todos de ella obliga a inventar auditorías falsas para registrar un reclamo o un riesgo.

#### Scenario: Registro nacido de una auditoría
- **WHEN** se registra una mejora con origen en una auditoría
- **THEN** el sistema exige el hallazgo que la originó

#### Scenario: Registro nacido de un hallazgo propio
- **GIVEN** un encargado detecta una debilidad sin que haya auditoría de por medio
- **WHEN** la registra
- **THEN** el sistema la acepta sin exigir auditoría ni hallazgo

#### Scenario: Registro nacido de la revisión anual
- **WHEN** el origen es el análisis FODA de la revisión anual
- **THEN** el sistema la acepta sin exigir auditoría

### Requirement: El tipo del registro decide qué datos se exigen
El sistema SHALL pedir los datos que la norma exige según el tipo de registro, y SHALL rechazar un registro al que le falten los de su tipo.

#### Scenario: Salida no conforme sin producto
- **WHEN** se registra una salida no conforme sin identificar el producto y su lote
- **THEN** el sistema la rechaza

#### Scenario: Reclamo sin cliente
- **WHEN** se registra un reclamo sin identificar al cliente ni el canal
- **THEN** el sistema lo rechaza

### Requirement: No se cierra sin verificar que funcionó
El sistema SHALL exigir una verificación de eficacia afirmativa antes de permitir el cierre de un registro.

#### Scenario: Intento de cierre sin verificar
- **WHEN** alguien intenta cerrar un registro cuya eficacia no fue verificada
- **THEN** el sistema lo impide

#### Scenario: La verificación dice que no fue eficaz
- **WHEN** la verificación concluye que la acción no funcionó
- **THEN** el registro vuelve a la etapa de acción correctiva
- **AND** ese retorno queda en el historial

#### Scenario: Sin responder no es lo mismo que responder que no
- **WHEN** las preguntas de verificación quedan sin responder
- **THEN** el sistema no las interpreta como respuesta negativa ni permite cerrar

### Requirement: Las salidas reglamentarias quedan comprometidas
El sistema SHALL registrar como compromisos con responsable y plazo las salidas que la verificación deja abiertas —actualizar la matriz de riesgos, la matriz FODA o un documento del sistema de gestión— y SHALL exigir justificación para descartarlas.

Sin esto alguien marca que sí corresponde, cierra el registro, y el sistema no vuelve a mencionarlo nunca. Es exactamente el hallazgo que levanta un auditor al revisar la eficacia del propio sistema de gestión.

#### Scenario: La verificación abre una salida
- **WHEN** la verificación indica que hay que actualizar la matriz de riesgos
- **THEN** el sistema deja un compromiso pendiente sobre ese registro
- **AND** no permite cerrar el registro mientras ese compromiso no tenga responsable y fecha

El responsable y la fecha no se inventan al marcar la casilla —nadie los sabe en
ese momento— pero sin ellos no se le avisa a nadie, que es el mismo agujero con
otro nombre. El compromiso **no** bloquea por existir: tiene su propio plazo y
sobrevive al cierre del registro.

#### Scenario: Una salida se descarta
- **WHEN** alguien descarta una salida comprometida
- **THEN** el sistema exige una justificación y la conserva

#### Scenario: Las salidas pendientes son visibles
- **WHEN** se consulta el estado del sistema de gestión
- **THEN** las salidas comprometidas y no ejecutadas aparecen como pendientes, con su registro de origen, su responsable y su plazo
- **AND** siguen apareciendo aunque el registro que las originó esté cerrado

### Requirement: Cobertura de auditoría medida sobre lo aplicable
El sistema SHALL informar qué proporción de los requisitos en alcance fue efectivamente evaluada, excluyendo los no aplicables.

Una auditoría con 20 % de cobertura y cero no conformidades no es una buena noticia: es una auditoría incompleta, y hoy se ve idéntica a una completa sin hallazgos.

#### Scenario: Requisitos sin evaluar bajan la cobertura
- **GIVEN** una auditoría con requisitos evaluados, no evaluados y no aplicables
- **WHEN** se consulta su cobertura
- **THEN** los no aplicables quedan fuera del cálculo y los no evaluados la bajan

### Requirement: Un hallazgo se sostiene en evidencia
El sistema SHALL exigir evidencia objetiva, separada de su descripción, en todo registro que nazca de una auditoría.

Un hallazgo sin evidencia no es defendible ante una apelación del auditado: la
descripción dice qué está mal, la evidencia dice qué se vio, dónde y cuándo
(ISO 19011). Se exige a los registros con origen en una auditoría; un reclamo de
cliente o un riesgo de la revisión anual nacen de otra cosa.

**Que la severidad solo aplique a las no conformidades quedó fuera de este
cambio** (4-oct): hoy se pide en todo registro —la escala por empresa la decidió
#57— y hacerla opcional toca el modelo, las filas existentes y el plazo de las
etapas, que se deriva de ella. Está anotado como decisión abierta en
`docs/plan-de-cierre-v1.md`.

#### Scenario: Hallazgo de auditoría sin evidencia
- **WHEN** se registra un hallazgo con origen en una auditoría y sin evidencia objetiva
- **THEN** el sistema lo rechaza

#### Scenario: Un registro que no sale de una auditoría
- **WHEN** se registra un reclamo o un riesgo detectado en la revisión anual
- **THEN** el sistema no le exige evidencia objetiva

### Requirement: Los conteos del informe se derivan
El sistema SHALL calcular los totales del informe de auditoría a partir de sus hallazgos, y no permitir capturarlos a mano.

Guardarlos escritos a mano es la forma más rápida de que el informe y el sistema digan cosas distintas.

#### Scenario: Se agrega un hallazgo después de emitir el informe
- **WHEN** se registra un hallazgo nuevo en una auditoría con informe
- **THEN** los totales del informe reflejan el cambio

### Requirement: El vocabulario del ciclo es configurable por empresa
El sistema SHALL permitir que cada empresa defina su escala de severidad, sus metodologías de análisis de causa y los días que da cada severidad para cerrar.

Sin esto, el segundo cliente que entre obliga a un cambio de esquema.

**El orden de las etapas no se configura, y es deliberado** (4-oct): lo fija
ISO 9001 §10.2.1 —primero reaccionar y corregir, después analizar la causa, y la
verificación de eficacia al final—. Un ciclo con otro orden no es la misma norma
con otras palabras: es otro ciclo. Lo que sí varía por tipo de registro es qué
etapas corresponden (un riesgo o una oportunidad no llevan corrección ni análisis
de causa).

#### Scenario: Dos empresas con escalas distintas
- **GIVEN** dos empresas con escalas de severidad diferentes
- **WHEN** cada una registra un hallazgo
- **THEN** cada una ve su propia escala
