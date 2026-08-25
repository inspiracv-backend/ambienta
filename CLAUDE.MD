# CLAUDE.md - Contexto del Proyecto Ambienta

## Visión General
Ambienta es un sistema multi-tenant para la gestión de cumplimiento ambiental de empresas industriales en Chile.
Objetivo: Centralizar declaraciones ambientales (RETC, residuos peligrosos, Ley REP, etc.), alertar vencimientos y generar reportes de auditoría.

## Reglas Obligatorias de Desarrollo (NO NEGOCIABLES)

### 1. Spec-Driven Development con OpenSpec

Usamos **OpenSpec** de verdad: el framework, no una imitación.

La versión está fijada en `package.json`, así que `npx openspec ...` funciona
tras `npm install` sin instalar nada más. Para que las skills de `.claude/`
lo invoquen directo hace falta además el global:

```bash
npm install -g @fission-ai/openspec@1.8.0
```

El contexto del proyecto y las reglas por artefacto viven en
`openspec/config.yaml`; el CLI se las muestra a la IA al generar artefactos.

#### 1.1 Los dos directorios

| Directorio | Qué contiene |
|---|---|
| `openspec/specs/<capacidad>/spec.md` | **Cómo se comporta el sistema hoy.** La fuente de verdad |
| `openspec/changes/<nombre>/` | Un cambio propuesto: `proposal.md`, `design.md`, `tasks.md` y `specs/` con los **deltas** |
| `openspec/changes/archive/` | Cambios terminados, con fecha. Sus deltas ya se fundieron en `specs/` |

`openspec/analisis/` es nuestro (secciones del Análisis Funcional) y no forma
parte del framework. Sirve como fuente, no como spec.

#### 1.2 El ciclo: proponer → aplicar → archivar

1. **Proponer** — `/opsx:propose`. Genera los 4 artefactos. **Solo planificación:
   no se escribe código en este paso**, aunque el pedido diga "arregla" o "haz".
2. **Aplicar** — `/opsx:apply`. Se implementa siguiendo `tasks.md`, marcando cada
   checkbox. Si el modelo real contradice la spec, se corrige el `design.md`
   antes de seguir.
3. **Archivar** — `/opsx:archive`. Los deltas se funden en `openspec/specs/` y el
   cambio se mueve a `archive/` con fecha.

**El paso 3 no es opcional.** Sin archivar, `specs/` nunca refleja el sistema
real y cada spec nueva se escribe contra un estado imaginado. Así llegamos a
tener código que leía columnas inexistentes (`compliance_answer`, `is_active`)
sin que nada lo detectara.

#### 1.3 Formato

Un spec es **un contrato de comportamiento, no un plan de implementación**. Qué
hace el sistema, no cómo. El cómo va en `design.md`.

```markdown
### Requirement: Nombre del requisito
El sistema SHALL <comportamiento observable>.

#### Scenario: Caso concreto
- **GIVEN** un estado previo
- **WHEN** ocurre algo
- **THEN** el sistema responde así
```

Los deltas van bajo `## ADDED Requirements`, `## MODIFIED Requirements` o
`## REMOVED Requirements`. Los encabezados y las palabras `SHALL`, `GIVEN`,
`WHEN`, `THEN` son estructura que el CLI parsea: van en inglés. La prosa va en
español.

#### 1.4 Antes de implementar

Leer el cambio completo (`proposal`, `design`, `tasks`, `specs/`), el spec vivo
de la capacidad en `openspec/specs/` si existe, y las fuentes en `fuentes/`.

#### 1.5 Verificación

```bash
npm run spec        # cambios activos y su avance
npm run spec:check  # los 4 artefactos y el formato de los deltas
npx openspec status --change <nombre>
npx openspec list --specs   # capacidades con spec vivo
```

Un cambio sin `specs/` no valida. Si de verdad no toca comportamiento
(herramientas, documentación), va `skip_specs: true` en su `.openspec.yaml`.

**Referencia de calidad:** `openspec/specs/dashboard/spec.md` es el ejemplo de
spec vivo; `openspec/changes/archive/2026-08-08-dashboard-metricas-api/` muestra
el ciclo completo.

### 2. Arquitectura Backend Separado
- Frontend (Next.js) y Backend (FastAPI, Python) completamente separados.
- 4 deployables previstos: web, api, worker, ai-service — **hoy solo existen
  los dos primeros**. Ver "Estructura del monorepo" más abajo.
- Nunca mezclar lógica de negocio en el frontend. El frontend presenta; el
  backend decide.

### 3. API First + OpenAPI
- Todo endpoint nuevo debe definirse primero en el contrato OpenAPI.
- Usar `packages/shared` para tipos y validadores compartidos.
- Validación automática desde el contrato (Pydantic en la API; Zod en el frontend).

### 4. Seguridad Multi-Tenant (Crítica)

**RLS no es la segunda barrera: es la única.** Ninguna consulta de la
aplicación filtra por `tenant_id` — ni `CRUDBase` ni un solo router. Lo que
separa a una empresa de otra es enteramente PostgreSQL, así que conviene que
sea sólido.

La API se conecta con **`ambienta_app`, que no puede saltarse RLS**. Eso pone
la barrera en la conexión: un endpoint mal escrito devuelve cero filas en vez
de todas las empresas. Hasta el 10-ago-2026 se conectaba con el dueño de la
base —superusuario con `BYPASSRLS`— y todo dependía de un `SET LOCAL ROLE` por
transacción que se perdía en cada `commit`:

| conexión | olvidando todo | con tenant | tras commit |
|---|---|---|---|
| dueño (antes) | **6** = todas las empresas | 4 | **6** |
| `ambienta_app` (ahora) | 0 | 4 | 0 |

- Usar **siempre** `get_tenant_db` para datos de empresa. `get_db` sí tiene la
  barrera —usa el mismo rol— pero no declara tenant, así que sobre una tabla de
  empresa devuelve cero filas. Sirve para el catálogo global y para `tenants`,
  que no llevan `tenant_id`.
- **No consultar después de `db.commit()`.** El commit cierra la transacción y
  con ella se va el tenant declarado: lo que venga después ve cero filas.
  Molesto, pero ya no peligroso.
- `get_admin_db` **sí** cruza empresas. Sólo el webhook de Clerk y el health
  del esquema. Cualquier uso nuevo hay que justificarlo.
- RBAC verificado siempre en la API (nunca solo en frontend).
- Admin Global NO puede editar contenido de tenants.

Lo protegen `apps/api/tests/test_aislamiento.py` y el smoke test de `db/`.

### 5. Roles
- **Admin Global**: Dueño del software (gestión de tenants, catálogo maestro).
- **Admin Empresa**: Gestiona su empresa y empleados.
- **Encargado**: Operativo - crea/envía declaraciones.

### 6. Desarrollo con IA (Claude Code)
- Solo implementar Features que tengan spec aprobada en `openspec/`.
- Revisión humana obligatoria de todo PR generado por IA.
- Seguir convenciones del monorepo y este archivo.

---

## Estructura del monorepo

```
apps/web          Next.js 14 · App Router · Atomic Design · 40 pantallas
apps/api          FastAPI · 95 endpoints · routers → services → crud → models
apps/worker       CARPETA VACIA. Un archivo. Vuelve con Notificaciones
apps/ai-service   CARPETA VACIA. Un archivo. LangGraph, post-MVP
packages/shared   18 schemas Zod compartidos por el frontend
db/               Esquema SQL numerado. Ver db/README.md
openspec/         Specs vivos y cambios propuestos. Ver §1
docs/arquitectura Los 5 ADR y el modelo entidad-relacion
```

`worker` y `ai-service` **existen como carpetas, no como servicios**. La
arquitectura los contempla; el repo todavia no. Conviene decirlo asi y no
"4 deployables", porque el worker es el que hara falta apenas entren las
notificaciones con vencimientos.

## Estilo arquitectonico

**Monolito modular**, no microservicios. Una sola base de datos, un solo
`SessionLocal`, sin bus de eventos ni HTTP interno. Los 13 dominios comparten
las 52 tablas y hay FKs cruzando entre ellos: 40 apuntan a `tenants` y 33 a
`users`.

Los limites entre dominios existen **en el codigo y por convencion**, no
forzados por infraestructura. Esa es la diferencia con microservicios, y es
deliberada: el aislamiento multi-tenant se garantiza hoy con RLS en la base, y
repartido en cinco bases pasaria a ser cinco implementaciones que mantener
coherentes a mano.

Los 4 deployables se separan por **preocupacion de runtime** —navegador, HTTP,
trabajos en segundo plano, inferencia— no por dominio de negocio.

## Como levantarlo

```bash
docker compose up -d      # postgres + api + web
```

- Web http://localhost:3000 · API http://localhost:8000 · Swagger `/docs`
- La base se inicializa sola con los 6 scripts de `db/`, en orden, la primera
  vez que se crea el volumen
- Para recrearla: `docker compose down -v && docker compose up -d`

No hace falta cuenta de Clerk: sin `CLERK_JWKS_URL` la API acepta el header
`X-Tenant-Id` y el frontend muestra el DevRoleSwitcher.

## Estado del proyecto

**Actualizado 21-ago-2026.** Si esto lleva meses sin tocarse, verificar antes
de confiar: `npm run spec`, `docker compose up -d`, `npx openspec list --specs`.

| Area | Estado |
|---|---|
| Base de datos | **Completa y verificada.** 52 tablas, 38 con RLS, 9 smoke tests en verde |
| API | **109 rutas, 225 operaciones.** Swagger con titulo y explicacion en **las 223 de negocio, sin excepciones**. 37 recursos con lectura y escritura completas, borrado logico y errores uniformes |
| Auth | **Funcionando de punta a punta** (Clerk fases 1 a 4), verificado en el navegador el 10-ago. Sin `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` sigue el DevRoleSwitcher |
| Auth — Google SSO | **Verificado en local el 17-ago.** Entrada con `oauth_google`, el claim `tenant_id` viaja y la API responde 200. **Falta para produccion:** credenciales propias (hoy usa las compartidas de Clerk) y el webhook. Ver abajo |
| Auth — Microsoft SSO | **Sin configurar.** Exige registro en Entra ID, y ahi el tipo de cuenta tiene que ser *cualquier directorio + cuentas personales*: con "solo este directorio" ningun cliente puede entrar |
| Frontend — lecturas | **Conectadas.** Las pantallas leen de la API, no de `mocks/` |
| Frontend — escrituras | **74 %.** 29 de 39 acciones llegan a la base. Las 10 restantes tienen causa documentada en su propio docstring. El conteo anterior (26 de 37) estaba mal por dentro: decia 10 pendientes y listaba 11 — ver `docs/escrituras-del-frontend.md` |
| RBAC | **Funcionando.** Permiso efectivo (rol + excepcion individual, la denegacion gana), guarda derivada de la ruta en los 18 routers de negocio, y rol `servicio_lectura` para integraciones. Falta la pantalla de administracion |
| Catalogo normativo | **Se alimenta de la BCN.** Normas, versiones y articulado reales. La Ley 19.300 entra con sus 151 partes y su version vigente de 2024-04-10. Falta decidir **que normas importar** y la pantalla de admin para revisar versiones — ver abajo |
| Normativa aplicable | **Funcionando de punta a punta y verificado con datos reales.** La empresa declara sector CIIU y tramo, el check propone obligatorias y recomendadas, y sincronizar la matriz agrega sin borrar. Lo que falta es **declarar el sector de las empresas sembradas** — ver abajo |
| Registro de actividades | **Se escribe solo desde el 24-ago.** Un observador del `flush` de la sesion anota `create`, `update` y `delete` de todo lo que pasa por la ORM, sin que los routers llamen a nada. Antes: `audit_log` con **cero filas** y ningun camino para llenarla — ver abajo |
| Auth — clave local con RUT (RF-06) | **Funcionando desde el 25-ago.** Quien entro por SSO fija RUT y clave en su perfil y despues entra con ellos. **La clave la guarda Clerk, no nosotros** (D1). El RUT viaja como `username` con prefijo `rut`, porque Clerk rechaza los que son solo digitos — y un RUT lo es salvo cuando el verificador es K |
| Acceso Cliente Invitado | **Completo y verificado en el navegador el 25-ago.** RUT y clave los emite la API, no el navegador; token propio de 30 dias; la solicitud queda ligada a la credencial y el invitado ve solo las suyas. Con tope de peticiones en las dos rutas publicas |
| Reportabilidad RETC | **Modelo y API desde el 25-ago** (ADR-004). `retc_systems` dice que portales existen; `facility_retc_reporting` cual le toca a cada planta, con los 5 estados del ADR. **El catalogo esta sin confirmar:** trae los 12 sistemas de la Ventanilla Unica con su fuente, y NO los 9 de la SMA — ver abajo |
| Perfil Empresa obligatorio (RF-10) | **Real desde el 25-ago.** Antes la marca la calculaba el navegador como `giro && rut`, y como el RUT es `NOT NULL` eso daba `true` para todas: **el gate no bloqueaba a nadie**. Ahora el criterio lo decide el servidor —giro + planta + departamento + sector— y la API **rechaza con 409** las escrituras de Matriz Legal y Obligaciones del Admin Empresa con el perfil incompleto |
| Usuario Interno con departamento (RF-11) | **Exigido por la base desde el 25-ago.** CHECK condicionado al tipo: solo `internal` y `tenant_admin`, porque un Admin Global no pertenece a un departamento de una empresa cliente. Borrar un departamento con gente dentro responde **409** hasta reasignarla |
| worker · ai-service | Sin implementar |

**El CORE devuelve `sin_perfil`, y la causa NO es la que parece.** Conviene
leerlo con cuidado porque son dos estados distintos con arreglos opuestos:

| Estado | Que falta | Quien lo arregla |
|---|---|---|
| `sin_perfil` | La empresa no declaro su sector | La empresa, en Perfil Empresa |
| `sector_sin_clasificar` | Nadie clasifico normas para ese sector | Nosotros |

**Ojo: esta entrada envejece.** Se escribio cuando las dos empresas del seed
tenian `tenants.sector_id` en NULL, y **ya no es asi** — el sector de la primera
se declaro despues. Una prueba de `test_perfil_empresa.py` fallo por asumirlo, y
por eso ahora las pruebas ponen el estado que quieren medir en vez de confiar en
el seed. `norm_sectors` **no esta vacia** —tiene 10 filas y
las 8 normas del catalogo estan clasificadas sobre 4 sectores— asi que basta
declarar el sector de una empresa para que el CORE proponga normativa. Ya se
comprobo: con `sector_id = 3` la empresa recibe una norma obligatoria.

Lo que si es trabajo pendiente de clasificacion: **17 de los 21 sectores CIIU
estan en cero**. Una empresa de construccion, comercio o transporte entra y no
recibe nada. Eso limita a que rubros se le puede vender, no impide demostrar el
sistema. La pantalla `/clasificacion-normativa` (solo Superadmin) lo muestra
sector por sector.

**Esta entrada estuvo mal escrita hasta el 20-ago** y decia que `norm_sectors`
estaba vacia. Es el error que este mismo archivo advierte dos secciones mas
abajo: un dato afirmado sin medirlo, que despues se cita como un hecho.

**El catalogo ya no es inventado, pero hay que elegir que traer.** La BCN tiene
**748.000 normas** y la enorme mayoria son nombramientos y concesiones de
acuicultura. Hoy se busca por titulo; falta un criterio —una lista, o los
organismos que importan— acordado con negocio. Traerlas todas no es
exhaustividad: es ruido que despues alguien tiene que clasificar a mano.

**Lo que hay que saber al tomar el repo:** conectar una escritura **no es
agregar un `PATCH`**. Es un viaje de ida y vuelta, y hacer solo un lado engana
igual: `tenants` leia `limiteUsuarios: 50` escrito a mano, asi que guardarlo sin
tocar la lectura daba un "guardado" que se deshacia al recargar.

Queda **un store que pide datos y descarta la respuesta**: `plan-accion` con
las tareas, que ademas no existen en el modelo. `audits` y `legal-matrix` ya
mapean lo suyo desde el 17-ago. Ver `docs/escrituras-del-frontend.md`.

**El SSO no deja un usuario utilizable por si solo.** Entrar con Google crea la
sesion en Clerk, pero el `tenant_id` sale de `publicMetadata` —lo inyecta el
JWT Template— y la fila en `users` la escribe el webhook. En local **el webhook
no llega a `localhost`**, asi que ambas cosas se hacen a mano:

1. Clerk → Users → Public metadata: `{"tenant_id": "<uuid de la empresa>"}`
2. `UPDATE users SET clerk_id = 'user_xxx' WHERE email = '...'`

Sin el paso 1 la persona entra y recibe `403 sesion_sin_empresa` en todo. El
paso 2 solo hace falta en local; en el VPS el webhook lo resuelve. Ver
`docs/development/setup-local.md`.

**El registro de actividades se engancha en un solo lugar, y ese lugar importa.**
`app/services/auditoria_automatica.py` escucha `before_flush` de `SessionLocal`
y `get_tenant_db` le deja en `db.info` quien hace el request. Consecuencias que
conviene saber antes de tocarlo:

- **Se anota en `before_flush` y no despues** porque es el ultimo momento en que
  la ORM todavia tiene el valor anterior de cada atributo. En `after_flush` el
  historial ya se limpio y `before_data` saldria vacio.
- **Lo que no pasa por la ORM no se audita.** Hoy eso es `guest_credentials`,
  que anota su `login` a mano. Cualquier `INSERT`/`UPDATE` nuevo por SQL crudo
  entra en esa categoria **sin que nada avise**.
- **Sin `get_tenant_db` no hay registro.** Un endpoint escrito con `get_db` no
  solo devuelve cero filas (§4): tampoco deja rastro.
- El id de una fila nueva se genera en Python, no en Postgres, para que
  `entity_id` no salga vacio en las creaciones.

**El invitado es el segundo emisor de identidad, y esta acotado a proposito.**
`app/routers/acceso_invitado.py` tiene **tres rutas y ninguna mas**, dos de
ellas publicas porque RF-02 pide que alguien sin cuenta abra una solicitud. Lo
que contiene el dano no es una lista de permisos —un invitado no tiene rol—
sino que su token es de otro tipo: `SesionDeInvitado`, que ningun endpoint de
negocio sabe leer. Tres cosas que hay que saber si se toca:

- **La firma del token no basta.** Cada peticion vuelve a mirar la credencial en
  la base. Sin eso, revocar una credencial filtrada no haria nada durante los 30
  dias que dura el token.
- **Sin `TOKEN_INVITADO_SECRETO` el ingreso responde 503**, no firma con una
  llave por defecto. Un secreto en el codigo es un secreto publicado.
- **El tope de peticiones vive en el proceso y cuenta por IP.** Corta el abuso
  trivial y que un script recorra las claves de 6 caracteres; **no** para un
  ataque distribuido, y con varios trabajadores el tope efectivo se multiplica
  por la cantidad de procesos.
- **El registro de actividades de este router se escribe a mano.** El observador
  del `flush` solo actua con el contexto que pone `get_tenant_db`, y aca no hay
  Clerk. Un endpoint nuevo en este router que se olvide de `_anotar()` **no deja
  rastro y nada avisa**.

**Un 403 tampoco es siempre autenticacion, y ya van dos.** La Backend API de
Clerk esta detras de Cloudflare, que responde **`403 error code: 1010`** a quien
no se identifica como navegador. Se lee como "la clave secreta no sirve" y no
tiene nada que ver — es exactamente lo mismo que paso con Ley Chile, ahi con un
401. La constante `NAVEGADOR` de `app/services/clave_local.py` es lo unico que
hace falta, y hay una prueba que impide que alguien la "limpie".

**Un sistema sectorial del RETC NO es un sector CIIU, y el repo usa "21" para
los dos.** Son dimensiones ortogonales:

| Tabla | Que responde | Ejemplo |
|---|---|---|
| `sectors` | a que se dedica la empresa (CIIU) | mineria, energia |
| `retc_systems` | ante quien declara | SIDREP, SINADER |

Una minera y una termoelectrica pueden compartir sistema sin compartir rubro.
Cruzarlos en la misma columna —que es la tentacion, porque las dos "clasifican"—
haria que el CORE propusiera normativa por el criterio equivocado.

**Y el catalogo del RETC esta a medias, a proposito.** ADR-004 dice 21 portales
(12 sectoriales + 9 de la SMA) y cita una fuente que **no existe en el
repositorio**. Se sembraron los 12 de la Ventanilla Unica desde el portal
oficial, cada uno con su `fuente`, y **todos con `active = false`**: es un
borrador que negocio tiene que firmar. Los 9 de la SMA no se inventaron. Hay
pruebas que fijan las dos cosas y que **deben fallar** el dia que aparezca la
lista completa.

La `periodicidad` va vacia por el mismo motivo: el portal lista los sistemas
pero no sus plazos, y las fechas cambian por resolucion cada ano. Un calendario
inventado genera **vencimientos falsos**, que en este dominio es el peor error
posible — la empresa cree que declaro a tiempo.

## Trampas conocidas

Cosas que ya costaron tiempo. Vale leerlas antes de tocar lo que mencionan.

**`db/01_schema.sql` no es una migracion.** Editarlo solo afecta a bases
nuevas. Todo cambio de esquema necesita ademas un `db/NN_*.sql` idempotente, y
ese archivo tiene que declarar **su propia politica RLS y sus GRANT**: el bucle
de politicas y el `GRANT ON ALL TABLES` de `01_schema` corren una sola vez, asi
que una tabla nacida en una migracion no los hereda y queda visible entre
empresas.

**La lista de archivos vive en CINCO lugares que deben coincidir**, y el quinto
es el que se olvida: `docker-compose.yml`, `docker-compose.prod.yml`,
`db/run.sh`, `db/README.md` y **el bucle de `.github/workflows/ci.yml`**. Este
ultimo tiene su propia enumeracion, asi que olvidarlo no rompe nada en local
—donde Docker ya aplico el archivo— y hace fallar CI con
`column ... does not exist`, que se lee como un error del codigo y no de la
configuracion.

**El modelo esta escrito dos veces.** `packages/shared` lo define en Zod y
`apps/api/schemas` en Pydantic, en dos lenguajes que no pueden importarse. Hoy
la sincronia es manual y ya se rompio: hubo codigo leyendo `compliance_answer`
e `is_active`, columnas que no existen, sin que nada lo detectara. **Contrastar
contra `db/01_schema.sql` y los modelos antes de escribir cualquier mapeo.**

**Los tests pueden ser vacuos.** Romper a proposito lo que un test dice
proteger y confirmar que falla. Es rutina en este repo y sigue encontrando
cosas: una prueba del historial afirmaba `Array.isArray(...)` —que pasa con
cualquier cosa— y al escribirla de verdad aparecio que sin sesion
`useRegistrarAuditoria` sale temprano, asi que comprobaba un no-op.

**Los medidores tambien pueden mentir, y es peor.** Un test falso falla una vez;
un numero falso se cita despues como un hecho. Ya paso con el "62 % conectado"
que era 57 %, con la cobertura de Swagger que reporto 206 titulos derivados
cuando eran 0, y con tres versiones seguidas de un script que conto las
escrituras del frontend y dio tres cifras distintas y falsas. **Un medidor nuevo
tiene que reproducir casos ya verificados a mano antes de que se publique su
resultado.**

**El aislamiento falla en silencio, pero ahora falla cerrado.** Un endpoint
escrito con `get_db` en vez de `get_tenant_db`, o una consulta puesta despues
de un `db.commit()`, no lanza ninguna excepcion: devuelve **cero filas**. Da
una pantalla vacia inexplicable, no una fuga. Antes daba lo contrario. Ver §4.

**Un 401 no siempre es autenticacion.** El sitio de Ley Chile responde 401 a
todo —incluida su propia pagina de documentacion— a quien no se identifica como
navegador. Se perdio tiempo diagnosticandolo como una clave sin habilitar, que
era la explicacion obvia; la pista estaba a la vista y no se miro. La constante
`NAVEGADOR` en `app/services/bcn.py` es lo unico que hace falta.

**Dos fuentes de la BCN, y no dicen lo mismo.** SPARQL (`datos.bcn.cl`) da el
historial de versiones y sirve para descubrir normas; el XML de Ley Chile da el
texto **y manda sobre la vigencia**. Para la Ley 19.300 SPARQL dice que la
version vigente es de 2010-11-13 y el XML dice **2024-04-10**: catorce anos.
Confiar en SPARQL para eso le diria a una empresa que cumple con un texto que ya
no rige.

Ademas SPARQL **devuelve filas duplicadas** y **marca mas de una version como
vigente** —en la Ley 19.300, la de 1994 y la de 2010 a la vez—. Ninguna de las
dos cosas se ve leyendo la documentacion.

**Sincronizar la BCN adopta la norma sembrada, no crea una al lado.** Las normas
de ejemplo tienen el mismo numero que las reales, y `norm_sectors` —la
clasificacion por sector, **el trabajo humano que hace funcionar el CORE**— esta
pegada a la fila sembrada. Duplicar dejaria la clasificacion en la copia falsa y
la norma real sin nada: **las matrices de las empresas se vaciarian sin ningun
error a la vista**.

**PowerShell, no bash.** El entorno del usuario es Windows: `&&` y `<` no
funcionan en la terminal. Un comando por linea.

## Verificacion

```bash
npm run spec:check                      # los 4 artefactos de cada cambio
cd apps/api && python -m pytest         # 474 pruebas, 34 archivos
cd apps/web && npx vitest run           # 331 pruebas, 26 archivos
bash db/run.sh --with-tests             # 9 comprobaciones del esquema
```

Las pruebas marcadas `red` **salen a internet y se saltan por defecto**: una
prueba que depende de un servicio ajeno falla cuando ellos tienen mantenimiento,
y eso es ruido. Existen igual porque son las unicas que verifican que la
consulta a la BCN se siga entendiendo del otro lado:

```bash
cd apps/api && python -m pytest -m red
```

`db/run.sh` necesita `psql` en el PATH del host. Sin el, las mismas
comprobaciones corren dentro del contenedor:

```bash
docker compose exec -T postgres psql -U ambienta -d ambienta -v ON_ERROR_STOP=1 -f /dev/stdin < db/02_smoke_test.sql
```

