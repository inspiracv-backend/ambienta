## MODIFIED Requirements

### Requirement: Toda norma en la matriz registra el origen de su inclusión
El sistema SHALL registrar, por cada norma de la matriz de una empresa, si entró
por el cálculo automático, si la agregó una persona —y en ese caso quién—, o si
es **normativa propia de la empresa**: su RCA o una norma que compró.

El origen decide qué puede hacer un recálculo con esa fila, así que tres casos
distintos no pueden quedar en dos categorías. Hasta ahora bastaba distinguir el
cálculo de la decisión de una persona. Con normativa propia dentro ya no: una RCA
tampoco entró "a mano" en el sentido de una decisión revisable —la impuso la
autoridad al titular del proyecto— y guardarla como tal deja abierta la puerta a
que un cambio de criterio en el manejo de lo manual se la lleve por delante.

#### Scenario: Norma agregada a mano
- **WHEN** alguien agrega una norma a la matriz que el cálculo no incluyó
- **THEN** el sistema la registra como agregada manualmente, con su responsable
- **AND** un recálculo posterior **no la quita**

Que el cálculo no la haya encontrado no significa que no aplique: puede ser una
norma que la empresa cumple por contrato.

#### Scenario: Normativa propia de la empresa
- **GIVEN** una empresa que cargó su RCA
- **WHEN** esa norma entra a su matriz
- **THEN** el sistema la registra con origen **propia de la empresa**
- **AND** un recálculo posterior no la quita

#### Scenario: El origen se conserva al recalcular
- **WHEN** se recalcula la normativa aplicable de una empresa
- **THEN** el origen registrado de cada norma que permanece no cambia

### Requirement: La matriz de cumplimiento se genera desde la normativa aplicable
El sistema SHALL crear la matriz de cumplimiento de una empresa a partir de su
normativa aplicable, incorporando los artículos de la **versión vigente** de cada
norma, en estado sin evaluar.

#### Scenario: Generación inicial
- **WHEN** se genera la matriz de una empresa que no tenía
- **THEN** el sistema crea una entrada por cada norma aplicable
- **AND** incorpora los artículos de la versión vigente de cada una
- **AND** ninguno queda como incumplido: entran **sin evaluar**

No haber evaluado no es incumplir. Contarlo como incumplimiento hundiría el
porcentaje de la empresa el día que se le carga la matriz.

#### Scenario: Regenerar no pisa lo evaluado
- **GIVEN** una empresa que ya evaluó parte de su matriz
- **WHEN** se vuelve a calcular su normativa aplicable
- **THEN** el sistema conserva las evaluaciones existentes
- **AND** agrega solo las normas que no estaban

#### Scenario: Una norma deja de aplicar
- **GIVEN** una norma en la matriz de una empresa que ya no corresponde a su sector
- **WHEN** se recalcula
- **THEN** el sistema la marca como **ya no aplicable** y conserva su historial
- **AND** no la borra

Borrarla eliminaría la evidencia de que en su momento sí se evaluó, que es
justamente lo que un fiscalizador pide al revisar un periodo pasado.

#### Scenario: La normativa propia no se marca como ya no aplicable
- **GIVEN** una empresa con su RCA en la matriz
- **WHEN** se recalcula la normativa aplicable y el cálculo no propone esa norma
- **THEN** el sistema la deja aplicable y en la matriz

Que el cálculo por sector no la encuentre es lo esperado: la aplicabilidad de una
RCA no se deduce de un sector CIIU, se la impuso el Estado a ese titular.
Marcarla "ya no aplicable" sacaría de la vista los compromisos que la autoridad
fiscaliza primero.

#### Scenario: Cambiar de sector no afecta a lo propio
- **GIVEN** una empresa con su RCA en la matriz
- **WHEN** la empresa cambia su sector declarado y se recalcula
- **THEN** la RCA sigue aplicable en la matriz con sus evaluaciones
