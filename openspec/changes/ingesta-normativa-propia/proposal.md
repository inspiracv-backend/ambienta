## Why

Una empresa no cumple solo la ley general: cumple **su RCA** —la Resolución de
Calificación Ambiental que el Estado le impuso a su proyecto— y, si se
certifica, **la norma ISO que compró**. Hoy el sistema no tiene por dónde
entrarlas. El catálogo se alimenta de la BCN, que trae leyes y decretos: los
mismos para todos.

Eso deja fuera lo que un fiscalizador de la SMA revisa primero. Una RCA trae
compromisos concretos —caudales máximos, monitoreos con su frecuencia, planes de
contingencia, informes a entregar— y cada uno es una obligación con fecha y
responsable. Hoy se llevan en una planilla aparte, o no se llevan.

El resto de la cadena ya está construido: norma → artículos → matriz por empresa
→ evaluación → obligaciones → avisos de vencimiento → reportes. **Lo único que
falta es la puerta de entrada.**

## What Changes

- **Normativa propia de la empresa.** `legal_norms` y `legal_articles` pasan a
  admitir un `tenant_id` opcional: `NULL` = catálogo global (la ley, igual para
  todos), con valor = propia de esa empresa (su RCA, su ISO comprada).
- **BREAKING (aislamiento):** las dos tablas pasan a tener Row Level Security.
  Hoy no la tienen porque el catálogo es público; con normativa propia dentro,
  una RCA cargada sin esta barrera **la verían todas las empresas del sistema, y
  nada fallaría**. La política admite lo global y lo propio:
  `tenant_id IS NULL OR tenant_id = current_tenant_id()`.
- **Ingesta del documento.** El PDF entra por el control documental que ya
  existe (sube a B2 con el `tenant_id` en la ruta) y la norma queda colgada de
  esa versión del documento. No se guarda un archivo suelto sin trazabilidad.
- **Extracción de candidatos.** Un parser lee el PDF y propone artículos: para
  una RCA, sus considerandos con compromiso y su capítulo de condiciones; para
  una ISO, sus cláusulas numeradas. **Escribe propuestas, no artículos.**
- **Revisión humana obligatoria.** Una pantalla muestra cada candidato junto al
  fragmento original del que salió. Se acepta, se edita o se descarta. Solo al
  confirmar se crean los `legal_articles` y su `article_compliance`.
- **Enganche con lo que ya existe.** Confirmada la norma, entra a la matriz
  legal de la empresa como cualquier otra y hereda evaluación, obligaciones,
  calendario, avisos y reportes sin código nuevo.

**Lo que este cambio NO hace:** no crea obligaciones automáticamente desde el
parser. Un compromiso que el parser se salte deja a la empresa creyendo que
cumplió todo, y ese es el error más caro posible en este dominio — el mismo
criterio por el que `declaration_templates` está vacía a propósito y la
`periodicidad` del RETC no se inventó.

## Capabilities

### New Capabilities

- `normativa-propia`: cómo una empresa incorpora normativa que solo le aplica a
  ella —su RCA, su ISO comprada—, cómo se aísla del catálogo global y de las
  demás empresas, y cómo el contenido de un PDF se convierte en artículos
  evaluables **pasando siempre por una confirmación humana**.

### Modified Capabilities

- `normativa-aplicable`: hoy el perfil normativo propone normas del catálogo
  global según sector y tramo. Pasa a distinguir dos orígenes en la matriz de
  una empresa —lo que el CORE propone y lo que la empresa cargó como propio— y
  la normativa propia **no se propone ni se retira por sector**: nadie decide
  por la empresa si su RCA le aplica.

## Impact

### Qué exige este cambio del resto del sistema

| Área | Qué hay que tocar | Por qué |
|---|---|---|
| `db/` migración nueva | `tenant_id` en `legal_norms` y `legal_articles`, con RLS y sus GRANT propios | Sin esto una RCA queda visible entre empresas, y falla abierto |
| `db/` las cinco listas | `docker-compose.yml`, `docker-compose.prod.yml`, `db/run.sh`, `db/README.md` y el bucle de `ci.yml` | La quinta es la que se olvida y rompe CI, no local |
| `services/bcn.py` | Que la sincronización **no toque** filas con `tenant_id` | Adoptar una RCA como si fuera una norma de la BCN la destruiría |
| `services/normativa_aplicable.py` | Excluir la normativa propia del cálculo por sector | Su aplicabilidad no la decide un sector CIIU |
| `services/sincronizar_matriz.py` | No retirar de la matriz lo cargado por la empresa | Sincronizar borraría la RCA de su propia matriz |
| `routers/catalog.py` | Rutas de carga y revisión, con el permiso `catalog.write` que ya existe | Está sembrado como «Cargar RCAs e ISO del tenant» y nadie lo usa |
| Control documental | Colgar la norma de una `document_version` | El PDF es la evidencia ante un fiscalizador |
| `apps/web` | Pantalla de carga y pantalla de revisión de candidatos | Sin revisión no se puede confirmar nada |
| Dependencia nueva | Un extractor de texto de PDF en la API | Hoy no hay ninguno |

### Decisiones que necesita el equipo

1. **¿Se guarda el texto completo de las normas ISO?** Son documentos con
   licencia del INN, típicamente por usuario o por sitio y no redistribuibles.
   Guardar el texto íntegro en un SaaS multi-tenant tiene implicancias de
   licenciamiento reales. La alternativa es guardar **la estructura** (número y
   título de cláusula) y **las tareas que la empresa define**, que es lo que se
   gestiona de verdad. **Con las RCA no se plantea**: son actos administrativos
   públicos que el SEA publica.

2. **¿Qué secciones de una RCA cuentan como obligación exigible?** Los
   considerandos con compromiso y el capítulo de condiciones y exigencias, o
   algo más. Tratar el documento entero como obligaciones produce cientos de
   tareas falsas y vuelve el módulo inservible. El criterio lo tiene que fijar
   alguien que sepa leer RCAs.

3. **¿Qué pasa cuando una RCA se modifica?** El SEA emite RCAs modificatorias
   que cambian compromisos de la original. ¿Se carga como norma nueva, como
   versión de la anterior, o se enlazan? Afecta a qué ve la matriz y a qué pasa
   con las evaluaciones ya hechas.

4. **¿Hace falta el parser en la primera entrega?** La carga manual —una persona
   escribe los compromisos leyendo el PDF— entrega valor completo y sin riesgo
   de omisión silenciosa. El parser ahorra tiempo y agrega un modo de fallar.
   Se puede entregar en ese orden.

### Insumos que hacen falta antes de escribir el parser

Dos o tres **RCAs reales** y, si entra ISO, una norma comprada de ejemplo. Un
parser escrito contra documentos imaginados funciona con los imaginados.
