## ADDED Requirements

### Requirement: Una empresa registra su propia normativa
El sistema SHALL permitir que una empresa registre normas propias —su Resolución de Calificación Ambiental y sus normas internas— con su articulado.

#### Scenario: Se carga una RCA
- **WHEN** una empresa registra una norma propia con sus artículos
- **THEN** el sistema la guarda y queda disponible para su matriz legal

### Requirement: La normativa propia no se comparte
El sistema SHALL impedir que una empresa vea la normativa propia de otra.

Las condiciones de una Resolución de Calificación Ambiental describen la operación de una planta; son de esa empresa y de nadie más.

#### Scenario: Otra empresa consulta el catálogo
- **GIVEN** una norma propia registrada por una empresa
- **WHEN** otra empresa lista las normas disponibles
- **THEN** el sistema no incluye esa norma ni su articulado

### Requirement: El catálogo público sigue siendo de todos
El sistema SHALL seguir mostrando las normas sin dueño a todas las empresas, y SHALL impedir que una empresa cree una norma sin dueño.

Escribir una norma pública desde una empresa sería escribirle la ley a las demás.

#### Scenario: Se intenta registrar una norma sin dueño
- **WHEN** una empresa intenta registrar una norma que no le pertenezca
- **THEN** el sistema rechaza la escritura

#### Scenario: El catálogo compartido se sigue viendo
- **WHEN** una empresa consulta las normas públicas
- **THEN** el sistema las devuelve como antes

### Requirement: La normativa propia se evalúa como cualquier otra
El sistema SHALL permitir incorporar una norma propia a la matriz legal y evaluar su cumplimiento artículo por artículo.

#### Scenario: Una RCA en la matriz
- **GIVEN** una norma propia registrada
- **WHEN** se agrega a la matriz legal de la empresa
- **THEN** sus artículos se pueden evaluar igual que los de una norma pública
