# normativa-aplicable Specification

## Purpose
Determinar qué normas del catálogo compartido le corresponden a una empresa según
su perfil, distinguir lo que debe cumplir de lo que se le recomienda revisar, y
convertir esa determinación en una matriz de cumplimiento que registre **por qué**
entró cada norma.
## Requirements
### Requirement: La empresa declara un perfil normativo estructurado
El sistema SHALL registrar de cada empresa el **sector económico** al que
pertenece y su **tramo de tamaño**, como valores de un catálogo cerrado, y SHALL
conservar aparte la descripción libre de su giro.

Un texto libre no se puede cruzar con nada. "Fabricación de envases plásticos" y
"envases plásticos" son la misma industria y dos cadenas distintas.

#### Scenario: Alta de empresa sin perfil
- **WHEN** se crea una empresa sin declarar sector
- **THEN** el sistema la acepta, y la deja marcada como **sin perfil normativo**
- **AND** no le calcula normativa aplicable hasta que se complete

#### Scenario: El giro no reemplaza al sector
- **GIVEN** una empresa con descripción de giro escrita
- **WHEN** no tiene sector declarado
- **THEN** el sistema la sigue tratando como sin perfil normativo

### Requirement: Una norma se clasifica por sector con nivel y fundamento
El sistema SHALL permitir declarar que una norma aplica a un sector, indicando su
**nivel de aplicabilidad** y el **fundamento** de esa decisión, y SHALL registrar
quién la declaró y cuándo.

El fundamento no es opcional: una clasificación sin explicación es indistinguible
de un error de carga cuando alguien la revisa un año después.

#### Scenario: Clasificación sin fundamento
- **WHEN** se intenta clasificar una norma sin escribir el fundamento
- **THEN** el sistema la rechaza

#### Scenario: Solo la plataforma clasifica
- **WHEN** un usuario de una empresa intenta clasificar una norma
- **THEN** el sistema lo rechaza
- **AND** la razón es que la clasificación es del catálogo compartido: cambiarla
  afectaría a todas las empresas

#### Scenario: Clasificación a nivel de artículo
- **WHEN** solo algunos artículos de una norma aplican a un sector
- **THEN** el sistema permite acotar la clasificación a esos artículos

### Requirement: El sistema calcula la normativa aplicable a una empresa
El sistema SHALL determinar, a partir del perfil de una empresa, qué normas le
corresponden, y SHALL entregarlas separadas en **obligatorias** y
**recomendadas** según su nivel de aplicabilidad.

#### Scenario: Empresa de un sector con normas clasificadas
- **GIVEN** una empresa con sector declarado
- **WHEN** se consulta su normativa aplicable
- **THEN** el sistema devuelve las normas clasificadas para ese sector
- **AND** las de aplicabilidad directa figuran como obligatorias
- **AND** las de aplicabilidad indirecta o referencial figuran como recomendadas

#### Scenario: Sector sin ninguna norma clasificada
- **WHEN** se consulta la normativa aplicable de una empresa cuyo sector todavía
  no tiene normas clasificadas
- **THEN** el sistema devuelve una lista vacía **y lo dice explícitamente**
- **AND** no se interpreta como que la empresa no tiene obligaciones

Una lista vacía por falta de clasificación y una lista vacía por no tener
obligaciones son cosas opuestas, y confundirlas le haría creer a una empresa que
está en regla.

#### Scenario: Cada norma dice por qué está
- **WHEN** el sistema devuelve la normativa aplicable
- **THEN** cada norma incluye el sector y el nivel que la hicieron entrar

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

### Requirement: Toda norma en la matriz registra el origen de su inclusión
El sistema SHALL registrar, por cada norma de la matriz de una empresa, si entró
por el cálculo automático o si la agregó una persona, y en el segundo caso quién.

#### Scenario: Norma agregada a mano
- **WHEN** alguien agrega una norma a la matriz que el cálculo no incluyó
- **THEN** el sistema la registra como agregada manualmente, con su responsable
- **AND** un recálculo posterior **no la quita**

Que el cálculo no la haya encontrado no significa que no aplique: puede ser una
norma que la empresa cumple por contrato o por su RCA.

### Requirement: El sistema avisa cuando una norma tiene una versión más nueva
El sistema SHALL permitir consultar qué normas del catálogo tienen una versión
vigente distinta de la que se usó para evaluar en alguna matriz.

#### Scenario: Versión nueva publicada
- **GIVEN** una empresa que evaluó los artículos de la versión anterior de una norma
- **WHEN** el catálogo pasa a tener una versión más nueva como vigente
- **THEN** el sistema señala esa norma como desactualizada en la matriz de la empresa
- **AND** mantiene visibles las evaluaciones hechas sobre la versión anterior

Las evaluaciones viejas no se invalidan solas: se hicieron sobre el texto que
regía entonces, y esa es la respuesta correcta ante una auditoría de ese periodo.

