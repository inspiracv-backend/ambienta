## Purpose
Permitir que una empresa incorpore la normativa que solo le aplica a ella —su
Resolución de Calificación Ambiental y las normas ISO que compró—, mantenerla
aislada del catálogo compartido y de las demás empresas, y convertir el contenido
de un documento en artículos evaluables sin que ninguna omisión del sistema pase
por cumplimiento verificado.

## ADDED Requirements

### Requirement: Una norma pertenece al catálogo compartido o a una empresa
El sistema SHALL distinguir dos orígenes de norma: las del **catálogo
compartido**, que son las mismas para todas las empresas, y las **propias de una
empresa**, que solo existen para ella.

Una RCA es un acto administrativo dirigido a un titular concreto y su texto trae
caudales, ubicaciones, capacidades y compromisos del proyecto. Una norma ISO
comprada es una licencia que pagó una empresa. Ninguna de las dos es "la misma
para todos", que es el supuesto sobre el que se construyó el catálogo.

#### Scenario: Norma propia visible solo para su empresa
- **GIVEN** la empresa A cargó su RCA
- **WHEN** la empresa B consulta el catálogo de normas
- **THEN** el sistema no le devuelve la RCA de la empresa A
- **AND** tampoco le devuelve sus artículos

#### Scenario: El catálogo compartido sigue siendo de todos
- **GIVEN** una norma del catálogo compartido
- **WHEN** cualquier empresa consulta el catálogo
- **THEN** el sistema se la devuelve

#### Scenario: Una empresa no puede reclamar una norma compartida
- **WHEN** se intenta convertir una norma del catálogo compartido en propia de
  una empresa
- **THEN** el sistema lo rechaza

### Requirement: La normativa propia no se propone ni se retira por sector
El sistema SHALL excluir la normativa propia de una empresa del cálculo de
aplicabilidad por sector, y SHALL conservarla en la matriz de esa empresa cuando
la matriz se sincroniza.

Que una RCA le aplica a la empresa no es una deducción del sistema: se lo dijo el
Estado. Y una sincronización que la retire por no encontrarla clasificada en
ningún sector borraría de la matriz justamente lo que la autoridad fiscaliza
primero.

#### Scenario: El perfil normativo no propone la RCA de nadie
- **WHEN** el sistema calcula la normativa aplicable de una empresa por su sector
- **THEN** no incluye normativa propia de ninguna empresa en la propuesta

#### Scenario: Sincronizar la matriz conserva lo propio
- **GIVEN** una empresa con su RCA en la matriz
- **WHEN** se sincroniza la matriz con el perfil normativo
- **THEN** la RCA sigue en la matriz
- **AND** sus evaluaciones se conservan

#### Scenario: La sincronización del catálogo externo no toca lo propio
- **WHEN** se sincroniza el catálogo con la fuente externa de normativa
- **THEN** el sistema no modifica ni adopta ninguna norma propia de una empresa

### Requirement: Toda norma propia queda respaldada por su documento
El sistema SHALL exigir que una norma propia esté vinculada a la versión de
documento de la que proviene, y SHALL permitir llegar desde la norma al archivo
original.

Ante un fiscalizador, el compromiso que la empresa dice cumplir tiene que poder
mostrarse en la resolución que lo impuso. Un texto transcrito sin su fuente no es
evidencia de nada.

#### Scenario: No se admite una norma propia sin documento
- **WHEN** se intenta registrar una norma propia sin la versión de documento de
  la que sale
- **THEN** el sistema la rechaza

#### Scenario: Desde la norma se llega al documento
- **GIVEN** una norma propia registrada
- **WHEN** se consulta su ficha
- **THEN** el sistema entrega la referencia al documento y su versión

### Requirement: La extracción produce candidatos, nunca artículos
El sistema SHALL registrar lo que extrae de un documento como **candidatos** en
revisión, y SHALL NO crear artículos evaluables ni obligaciones a partir de una
extracción sin confirmación de una persona.

Un compromiso que la extracción se salte deja a la empresa creyendo que cumplió
todo. En este dominio ese es el error más caro: no se nota, y se descubre en una
fiscalización.

#### Scenario: Extraer no crea artículos
- **WHEN** se procesa el documento de una norma propia
- **THEN** el sistema registra candidatos en estado de revisión
- **AND** la norma no tiene todavía ningún artículo evaluable

#### Scenario: Confirmar es lo que crea el artículo
- **GIVEN** un candidato en revisión
- **WHEN** una persona lo confirma
- **THEN** el sistema crea el artículo evaluable correspondiente

#### Scenario: Un candidato descartado no deja artículo
- **GIVEN** un candidato en revisión
- **WHEN** una persona lo descarta
- **THEN** el sistema no crea ningún artículo
- **AND** conserva el candidato descartado con su motivo

### Requirement: Cada candidato muestra de dónde salió
El sistema SHALL conservar, junto a cada candidato, el fragmento del documento
del que se obtuvo y su ubicación dentro de él.

Quien revisa tiene que poder contrastar la propuesta contra el texto original sin
abrir el PDF en otra ventana y buscar a mano. Sin eso la revisión se vuelve un
trámite de aceptar todo, y entonces la confirmación humana no protege nada.

#### Scenario: El candidato trae su fragmento
- **WHEN** se consulta un candidato en revisión
- **THEN** el sistema entrega el fragmento original y la página o sección donde
  aparece

#### Scenario: Se puede corregir antes de confirmar
- **GIVEN** un candidato cuyo texto extraído está incompleto
- **WHEN** una persona lo edita y lo confirma
- **THEN** el artículo se crea con el texto corregido
- **AND** el fragmento original se conserva sin modificar

### Requirement: La carga manual no depende de la extracción automática
El sistema SHALL permitir registrar los artículos de una norma propia
escribiéndolos directamente, sin pasar por una extracción automática.

Las resoluciones varían de formato entre años y organismos, y un documento
escaneado puede no dejar extraer nada. Que el módulo dependa del parser lo
volvería inservible justo en los casos difíciles.

#### Scenario: Norma propia cargada a mano
- **WHEN** una persona registra una norma propia y escribe sus artículos
- **THEN** el sistema los crea como artículos evaluables
- **AND** la norma queda utilizable en la matriz sin haber ejecutado ninguna
  extracción

#### Scenario: Documento del que no se puede extraer texto
- **WHEN** se procesa un documento del que no se obtiene texto
- **THEN** el sistema lo informa como tal
- **AND** deja la norma disponible para carga manual

### Requirement: Una norma propia confirmada se comporta como cualquier otra
El sistema SHALL tratar los artículos de una norma propia confirmada igual que a
los del catálogo compartido para efectos de matriz legal, evaluación de
cumplimiento, obligaciones, calendario, avisos de vencimiento y reportes.

#### Scenario: Se evalúa como cualquier artículo
- **GIVEN** una norma propia con artículos confirmados en la matriz
- **WHEN** se evalúa uno de sus artículos
- **THEN** el sistema registra la evaluación con su estado y fundamento

#### Scenario: Genera obligaciones con vencimiento
- **GIVEN** la evaluación de un artículo de una norma propia
- **WHEN** se le crea una obligación con fecha de vencimiento
- **THEN** el sistema la incluye en el calendario y en los avisos de vencimiento

#### Scenario: Aparece en los reportes de cumplimiento
- **GIVEN** una empresa con normativa propia evaluada
- **WHEN** se genera un reporte de cumplimiento
- **THEN** la normativa propia aparece junto a la del catálogo compartido
