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
| Catalogo normativo | **Se alimenta de la BCN de verdad desde el 26-ago, y hasta ese dia esta entrada era falsa.** Decia lo mismo que ahora mientras las 8 normas tenian `last_source_sync_at = NULL` y la Ley 19.300 dos articulos: `bcn.sincronizar()` estaba escrita, probada y **sin un solo llamador**. Medido hoy: **24 normas, 23 con identificador de la BCN, 689 articulos**, y la Ley 19.300 con sus **153 partes** y su version vigente de 2024-04-10. La sincronizacion se corre con `python -m app.tareas.sincronizar_bcn`. Falta decidir **que normas importar** y la pantalla de admin para revisar versiones — ver abajo |
| Normativa aplicable | **Funcionando de punta a punta y verificado con datos reales.** La empresa declara sector CIIU y tramo, el check propone obligatorias y recomendadas, y sincronizar la matriz agrega sin borrar. Lo que falta es **declarar el sector de las empresas sembradas** — ver abajo |
| Registro de actividades | **Se escribe solo desde el 24-ago.** Un observador del `flush` de la sesion anota `create`, `update` y `delete` de todo lo que pasa por la ORM, sin que los routers llamen a nada. Antes: `audit_log` con **cero filas** y ningun camino para llenarla — ver abajo |
| Auth — clave local con RUT (RF-06) | **Funcionando desde el 25-ago.** Quien entro por SSO fija RUT y clave en su perfil y despues entra con ellos. **La clave la guarda Clerk, no nosotros** (D1). El RUT viaja como `username` con prefijo `rut`, porque Clerk rechaza los que son solo digitos — y un RUT lo es salvo cuando el verificador es K |
| Acceso Cliente Invitado | **Completo y verificado en el navegador el 25-ago.** RUT y clave los emite la API, no el navegador; token propio de 30 dias; la solicitud queda ligada a la credencial y el invitado ve solo las suyas. Con tope de peticiones en las dos rutas publicas |
| Reportabilidad RETC | **Modelo y API desde el 25-ago** (ADR-004). `retc_systems` dice que portales existen; `facility_retc_reporting` cual le toca a cada planta, con los 5 estados del ADR. **El catalogo esta sin confirmar:** trae los 12 sistemas de la Ventanilla Unica con su fuente, y NO los 9 de la SMA — ver abajo |
| Perfil Empresa obligatorio (RF-10) | **Real desde el 25-ago.** Antes la marca la calculaba el navegador como `giro && rut`, y como el RUT es `NOT NULL` eso daba `true` para todas: **el gate no bloqueaba a nadie**. Ahora el criterio lo decide el servidor —giro + planta + departamento + sector— y la API **rechaza con 409** las escrituras de Matriz Legal y Obligaciones del Admin Empresa con el perfil incompleto |
| Usuario Interno con departamento (RF-11) | **Exigido por la base desde el 25-ago.** CHECK condicionado al tipo: solo `internal` y `tenant_admin`, porque un Admin Global no pertenece a un departamento de una empresa cliente. Borrar un departamento con gente dentro responde **409** hasta reasignarla |
| Matriz Legal ↔ Obligaciones | **Cerrado el 26-ago (#110), y era mas que un vinculo que faltaba.** La obligacion se cuelga de la **evaluacion** del articulo y no del articulo del catalogo, que es global. Los dos sentidos existen y la norma, la planta y el responsable se derivan de la evaluacion. Al medirlo aparecio que `POST /obligations/` aceptaba `article_compliance_id` sin mirarlo: **la empresa B podia colgar su obligacion de la evaluacion de la empresa A** — ver abajo |
| Declaraciones y calendario RETC | **Cerrada el 26-ago (epica #21).** El flujo de RF-31 completo —presentar, aceptar, rechazar con motivo— con las transiciones declaradas en un solo lugar, el folio del portal exigido para aceptar, la urgencia calculada en el servidor y el recordatorio que adjunta la plantilla del sistema. **`fulfill` respondia 422 en el 100 % de los casos** desde siempre: escribia un estado que el CHECK no admite. Lo que NO entra: el repositorio de plantillas Excel esta vacio a proposito — ver abajo |
| Dashboard ejecutivo | **Corregido el 26-ago (#125).** Dos de las tres plantas del seed no tienen una sola evaluacion y el tablero las mostraba **en rojo con 0 %** — cuarta vez que aparece el mismo error en esta serie. Ahora `null` es `Sin evaluar`, y esas plantas van al **final** de la tabla en vez de encabezarla como si fueran las peores |
| Incumplimientos (#126) | **Nueva el 26-ago.** `/incumplimientos` lista articulos incumplidos y declaraciones vencidas, **con lo que no tiene evidencia primero**. Al construirla aparecio que `evidence_url` se perdia en silencio con respuesta 200: la columna no existia — ver abajo |
| Avisos de vencimiento | **Rehechos el 26-ago (#119, #120, #123).** El generador anterior **duplicaba** —tres corridas, tres avisos—, **se saltaba en silencio las obligaciones sin responsable** (3 de 8 en el seed) y tenia las ventanas escritas a mano mientras `notification_rules` existia vacia. Ahora: clave unica en la base, escalamiento a los administradores, y ventanas por empresa con defecto 15/7/3/1. **Falta el cron que lo llame** (#119) — ver abajo |
| Control documental (RF-102 a RF-106) | **Modelo, ciclo de vida y subida de archivos desde el 27-ago** (epica #31). La capa de evidencias ya existia; **lo que faltaba era el control**: sin codigo no se puede citar un documento en una auditoria, y sin aprobacion registrada **nada impedia usar un borrador como evidencia**. El ciclo vive en la **revision**, no en el documento. Dos restricciones con dientes: aprobado exige quien y cuando, y una sola revision vigente por documento. La subida va por **enlace firmado** directo a B2, con la ruta del objeto llevando el `tenant_id`. **La pantalla `/documentos` existe desde el 27-ago** y con ella el ciclo de vida salio por la API: `control_documental.py` estaba escrito, probado y **sin ningun llamador** — ver abajo |
| worker · ai-service | Sin implementar |
| Avisos de vencimiento | **Cerrados el 27-ago (epica #22).** El generador anterior **duplicaba** —tres corridas, tres avisos—, **se saltaba en silencio las obligaciones sin responsable** (3 de 8 en el seed) y tenia las ventanas escritas a mano mientras `notification_rules` existia vacia. Ahora: clave unica en la base, escalamiento a los administradores, y ventanas por empresa con defecto 15/7/3/1. El 27-ago se cerro el resto: la cola sabe **reintentar** (`db/19`), hay un cron (`python -m app.tareas avisos`), el correo sale por **Resend**, y las plantillas de la empresa se rellenan en Python. Al enchufarlas aparecio que el generador **nunca creaba notificaciones de correo** — se podia configurar Resend entero y no salia un solo mensaje — ver abajo |
| Control documental (RF-102 a RF-106) | **Modelo, ciclo de vida y subida de archivos desde el 27-ago** (epica #31). La capa de evidencias ya existia; **lo que faltaba era el control**: sin codigo no se puede citar un documento en una auditoria, y sin aprobacion registrada **nada impedia usar un borrador como evidencia**. El ciclo vive en la **revision**, no en el documento. Dos restricciones con dientes: aprobado exige quien y cuando, y una sola revision vigente por documento. La subida va por **enlace firmado** directo a B2, con la ruta del objeto llevando el `tenant_id` — ver abajo |
| worker | **No existe como servicio, a proposito.** El trabajo en segundo plano vive en `apps/api/app/tareas/` y lo dispara cron. Ver `apps/worker/README.md` |
| ai-service | Sin implementar |

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

**La BCN devuelve la misma norma varias veces, y el `LIMIT` no la protege.**
SPARQL cuenta filas, no normas: pedir 5 puede traer 5 filas de 2 normas. `buscar()`
pide de mas y deduplica por codigo, quedandose con la fila que **mas campos
resueltos** trae — no con la primera, porque las filas de una misma norma no dicen
todas lo mismo y la primera suele ser la mas pobre.

**Y la busqueda distingue acentos.** `emision` no encuentra `EMISION` con tilde:
devuelve **cero resultados y ningun error**, que se lee como "esa norma no esta en
la BCN". Los terminos de `app/tareas/sincronizar_bcn.py` van sin acentos a
proposito, y hay una prueba que lo fija.

**"Sin evaluar" no es "no cumple", y el codigo los daba iguales.**
`computeNormCompliance` devuelve `0` tanto cuando todo se evaluo y todo salio NO
como cuando **no se evaluo nada**, y `normSemaforo(0)` es `no_cumple`. Con el
catalogo sembrado no se veia; con el articulado de la BCN, una norma recien
importada llega entera en `N_E` y la pantalla mostraba **"No cumple · 0 %"** —
una acusacion contra la empresa, en la vista que se exporta a un auditor.

Para la pantalla existe `computeNormComplianceOrNull`, que devuelve `null`
cuando no hay nada que medir. **Los reportes tambien lo usan desde el 26-ago**
(#205): el CSV y el PDF imprimen "Sin evaluar" en vez de `0%`, y el promedio por
planta deja fuera las normas sin evaluar en lugar de contarlas como ceros — una
planta con dos normas, una al 100 % y otra sin revisar, salia en 50 %.

`computeNormCompliance` **se queda igual**: es el espejo de
`resumen_cumplimiento.py`. Y al medirlo aparecio que **la API ya lo hacia bien**
—devuelve `None`, no cero, y su docstring lo explica— asi que el acoplamiento
que se temia no existia: el `0%` lo ponia solo el frontend.

Y una leccion sobre las pruebas: **habia una que fijaba `toBe(0)` sin preguntar
que significaba ese cero**, y el `normSemaforo(0) === 'no_cumple'` estaba en otro
`describe`. Las dos en verde y el error entre las dos. Por eso
`NormDetailView.test.tsx` afirma sobre **texto visible** y no sobre funciones.

**Una clave foranea aceptada del cuerpo es una fuga, no un descuido de estilo.**
Ya paso y se midio: `POST /obligations/` recibia `article_compliance_id` y lo
escribia sin comprobarlo. Como **las claves foraneas no pasan por RLS**, la
restriccion solo exige que la fila exista — no que sea de esta empresa. Desde la
empresa B:

| lo que se manda | antes | ahora |
|---|---|---|
| un id inventado | 422 | 422 |
| un id real de la empresa A | **201, y la fila quedaba escrita** | 422 |

Dos sintomas distintos y el segundo es el grave: no solo se distinguia "no
existe" de "existe pero es de otro" —un oraculo para enumerar identificadores
ajenos— sino que la escritura se completaba.

`routers/_comun.py::validar_visible` es el arreglo y ya existia. **Cualquier
endpoint nuevo que acepte un id en el cuerpo tiene que llamarlo**, y las dos
respuestas deben ser identicas: mismo codigo y mismo mensaje.

**El repositorio de plantillas Excel esta vacio, y es deliberado.**
`declaration_templates` tiene **cero filas**. El mecanismo existe y esta probado
—el recordatorio busca la plantilla vigente del sistema ante el que se declara y
la adjunta al aviso— pero las plantillas mismas son **contenido oficial que hay
que descargar de cada portal del Estado**, no codigo.

Inventar una estructura de pestanas seria peor que no tenerla: la empresa
prepararia su declaracion en un formato que el portal rechaza, y se entera
cuando le devuelven el archivo y ya no hay plazo. Es el mismo criterio que la
`periodicidad` vacia de `retc_systems`.

Lo que si esta fijado por pruebas: una plantilla **caducada o inactiva no se
adjunta**. Una marcada activa cuyo `valid_to` ya paso corresponde a una
estructura que el portal dejo de aceptar.

**Y la urgencia se calcula en un solo lado desde el 26-ago.** Estaba escrita dos
veces y **ya separada**: el navegador avisaba a 30 dias y el servidor no tenia
criterio. Ahora vive en `services/declaracion.py` (`DIAS_CRITICO`,
`DIAS_PROXIMO`) y el navegador la consume. Ojo con confundirla con las ventanas
de aviso 15/7/3/1 de #120: esas dicen **cuando escribirle a alguien**, la
urgencia dice **de que color se ve**.

**Los reportes salen en PDF por defecto, y el PDF no necesita una libreria.**
La pantalla exportaba solo CSV y avisaba que *"la generacion de PDF queda
pendiente de una libreria aprobada"*. **La frase era falsa desde hacia rato**:
`ReportePdf` produce un PDF de verdad con el motor de impresion del navegador
—texto seleccionable, enlaces vivos, el papel de quien lo emite— reutilizando el
HTML de la aplicacion. Lo que faltaba no era la dependencia: era que el selector
lo ofreciera y que existiera el documento para los otros tipos de reporte.

El defecto es PDF porque un reporte de cumplimiento casi siempre se pide para
**entregarlo** a un fiscalizador o un certificador. Una planilla no se entrega,
se procesa. **El CSV no se quito**: esta a un clic en el mismo selector.

Lo que se cede eligiendo el motor del navegador es el control fino de los saltos
de pagina. Si algun dia hace falta control tipografico, `ReportePdf` es el unico
punto donde enchufar la libreria.

**Y los dos formatos salen del mismo `Reporte`** (`lib/reports.ts`): `headers` y
`rows` se calculan una vez, el CSV se deriva y el PDF los pinta. Construirlos por
separado serian dos reportes con el mismo nombre, y agregar una columna a uno
dejaria al otro diciendo otra cosa sobre la misma empresa.

**El typecheck del frontend no cazaba errores de `null`, y ahora si.**
`apps/web` tenia **`"strict": false`**. Al arreglar el tablero cambie un tipo a
`number | null` y `npx tsc` no dijo nada: sin `strictNullChecks`,
`number | null` se asigna a `number` y `Math.round(null * 100)` compila. Hubo
que encontrar cada sitio a mano.

Medido antes de encenderlo: `strict` completo cuesta **cero errores** — el
codigo ya era estricto, la bandera estaba apagada. **Ojo con la trampa si
alguien lo apaga para "arreglar" algo:** con `strictNullChecks` a solas salen 9
errores que con `strict` entero no aparecen, porque `noImplicitAny` cambia como
se infieren los arreglos vacios (quedan en `never[]`). Va entero o no va.

**El CSV llevaba los acentos rotos en Excel.** Se exportaba UTF-8 **sin BOM**, y
Excel en Windows asume la codificacion local: "Fecha deteccion" con tilde salia
como `Fecha detecciÃ³n`, y los titulos de la BCN vienen en mayusculas con tilde,
asi que el archivo entero se veia mal. El `charset=utf-8` del tipo MIME no
alcanza — Excel mira los primeros bytes, no la cabecera. El BOM se agrega
**solo a los `.csv`**: metérselo a un `.txt` dejaria tres bytes basura al
principio para cualquier otra herramienta.

**Un arnes de mutacion sin linea base miente.** Me paso en esta serie: una
prueba ya estaba en rojo —fijaba el comportamiento viejo— asi que **todas las
mutaciones salian "DETECTADA"** sin que ninguna prueba las estuviera cazando.
Con la linea base arreglada, dos de tres sobrevivian. **Comprobar que la suite
este verde antes de mutar**, y negarse a informar si no lo esta.

**La epica de notificaciones esta cerrada desde el 27-ago, y sin Redis.**
`apps/worker` ya no tiene NestJS: era un `console.log` que ademas hacia que cada
`npm install` se bajara NestJS y `ts-node`. Ver `apps/worker/README.md`.

Las tres decisiones que aca figuraban como abiertas se tomaron asi:

1. **La cola es `notifications` en Postgres, no Redis.** Ya lo era: `status`
   con `queued` por defecto, `scheduled_at`, `sent_at`, `provider_message_id`,
   `dedupe_key` con indice unico y un indice parcial sobre los pendientes. Le
   faltaba el estado de reintento (`db/19`). Y hay una razon de correccion, no
   solo de ahorro: **la fila del aviso y el hecho que lo causa se escriben en
   la misma transaccion**, asi que no pueden discrepar. Con Redis son dos
   almacenes y las dos formas de discrepar son malas — un correo por una
   obligacion revertida, o una fila `queued` que nadie va a atender.
2. **Cron, no proceso residente.** `python -m app.tareas avisos` genera y
   despacha; una linea de crontab a las 7 de la mañana. Un proceso propio se
   justificara cuando haya trabajo disparado por el usuario que no pueda
   esperar al proximo cron.
3. **Las plantillas se rellenan en Python, no con React Email.** La tabla
   `notification_templates` ya existia con sintaxis `{{variable}}`.

**Lo que aparecio al enchufar las plantillas, y era lo grave:** el generador
**nunca creaba notificaciones de correo** — solo `channel="in_app"`. O sea que
se podia configurar Resend entero, correr el cron, y no salia un solo mensaje,
porque no habia ninguna fila que enviar. Nada fallaba. Ahora crea los dos
canales y la clave de deduplicacion lleva el canal, porque el indice unico es
`(tenant, clave, destinatario)` y sin eso los dos chocarian.

Y el `event_type` de la constante decia `obligacion_por_vencer` mientras las
plantillas sembradas usan `obligation_due`. No rompia nada **porque nadie
buscaba la plantilla todavia**; al enchufarla, el correo habria salido con el
texto de respaldo para siempre, sin ningun error.

**El relleno de plantillas NO usa Jinja2, y es por seguridad.** Las plantillas
son dato de empresa —`notification_templates` lleva `tenant_id` y RLS—, o sea
que un Admin Empresa las edita. Un motor con expresiones convierte "editar una
plantilla" en "ejecutar codigo en el proceso de la API": `{{ ''.__class__ }}` es
la primera linea de una cadena conocida. Solo se sustituye `{{nombre}}` por un
valor de un diccionario. Se pierden los condicionales; el peor caso de una
plantilla maliciosa pasa a ser un correo feo.

**Los tres tipos de fallo del correo se distinguen, y no es cosmetico.** 401/403
**cortan la corrida** en vez de matar el aviso: tratarlos como permanentes
dejaria cada aviso encolado en `failed` en su primer intento, y se descubriria
al arreglar la llave, cuando ya se perdieron. 429 **no es permanente** aunque
sea 4xx — es el que siempre se arregla esperando.

**El despachador toma de a un aviso, no por lote.** Un lote con `FOR UPDATE`
parece mas eficiente, pero el primer `commit` del bucle termina la transaccion y
**suelta los candados de las filas restantes**: otro despachador las toma
mientras este recorre su lista en memoria, y los dos mandan el mismo correo.

**Y `SET LOCAL` se pierde en el `commit`.** El cron recorre empresa por empresa
con RLS puesto —que es lo correcto, §4— pero el despachador confirma cada aviso
por separado: con el alcance por defecto atendia **un aviso por empresa** y el
resto quedaba invisible. De ahi `declarar(..., toda_la_sesion=True)` y
`olvidar()`, que hay que llamar o la conexion vuelve al pool con una empresa
pegada.

Para comprobar el correo, con un destino real:

```bash
docker compose exec api python -m app.tareas.comprobar_correo tu@correo.cl
```

Manda un correo de verdad. El error mas comun —dominio del remitente sin
verificar en Resend— **no se detecta hasta el primer envio**, que sin esto seria
el primer aviso de vencimiento de un cliente. Y "aceptado por Resend" no es
"entregado": si no llega, el problema esta en SPF/DKIM.

**El puente hacia el almacenamiento existe desde el 27-ago, y no guarda nada
en disco local.** El CHECK de `document_versions.storage_provider` son cuatro
—`s3`, `backblaze`, `google_drive`, `onedrive`— y **no hay opcion local ni de
desarrollo**: sin credenciales, la subida responde **503 con un mensaje claro**
y el resto del sistema funciona igual. Guardar en el disco del servidor sin que
nadie lo haya decidido produce archivos sin respaldo que se pierden en el primer
redespliegue, y la empresa los cree guardados.

`services/almacenamiento.py` habla con B2 por su **API compatible con S3**, asi
que las mismas variables sirven para S3 o R2: cambia el endpoint.

**Las dos reglas que sostienen el aislamiento**, porque ADR-005 tiene razon en
que **RLS no cubre el object storage** —Postgres no sabe nada de un bucket, y un
enlace firmado es una credencial que funciona sin pasar por la base—:

1. **La ruta lleva el `tenant_id` adelante**
   (`tenants/<uuid>/documents/<uuid>/v<n>/<nombre>`). No es cosmetico: es lo que
   permite acotar una llave de B2 a un prefijo por empresa el dia que haga
   falta. Con las rutas mezcladas eso ya no se puede sin mover todo.
2. **El enlace se emite despues de leer la fila con la sesion del tenant.** Si
   RLS no ve el documento, no hay URL. Y `confirm-upload` comprueba que la clave
   este dentro del prefijo de **ese** documento: sin eso, alguien podria
   confirmar una subida apuntando a la carpeta de otra empresa y quedarse con
   una revision que la descarga.

**Enlaces firmados y no un proxy por la API**: un PDF de 40 MB atravesando
FastAPI ocupa un worker durante toda la subida. Lo que se cede es que el archivo
llega sin que lo hayamos visto, asi que `confirmar_subida()` le pregunta al
bucket el tamano y el tipo **reales** en vez de creerle al navegador — y de paso
es lo unico que detecta un `PUT` que fallo a la mitad.

Para comprobar que las credenciales sirven de verdad:

```bash
docker compose exec api python -m app.tareas.comprobar_almacenamiento
```

**Dentro del contenedor**, porque es ahi donde llegan las variables: el
`.env` de la raiz lo lee `docker compose` para interpolar el bloque
`environment:`, no la API. Correrlo desde el host da "no configurado" aunque
todo este bien.

Sube, baja, compara el contenido y borra. **Que `boto3` construya una URL
firmada no prueba nada**: la firma se genera igual con una clave equivocada y
falla recien al usarla.

Y borra **la version**, no solo el archivo: el bucket guarda todas las
versiones a proposito (RF-106), asi que un borrado normal deja el objeto
guardado con un marcador encima. La consola muestra "0 archivos" y se sigue
pagando por los bytes.

**La pantalla de documentos existe desde el 27-ago, y al construirla aparecio
lo de siempre: el codigo estaba y nadie lo llamaba.**
`services/control_documental.py` tenia las transiciones, la aprobacion firmada y
la obsolescencia desde el 27-ago, con pruebas en verde, y **ningun router lo
invocaba**. Ademas las siete columnas del ciclo de vida y el `code` del
documento **no salian en ninguna respuesta**, asi que ni siquiera se podia
distinguir un borrador de lo que rige. Mismo patron que `bcn.sincronizar()`.

**Aprobar exige una sesion identificada y responde 409 si no la hay.** No se
toma al primer administrador de la empresa: eso dejaria escrito que esa persona
aprobo algo que no aprobo, y es exactamente lo que lee un auditor. Con
`X-Tenant-Id` —el modo sin Clerk— no hay usuario, asi que la aprobacion no se
puede probar en ese modo. Es a proposito.

**Faltaba una transicion que el propio modelo declaraba.** `TRANSICIONES` decia
`en_revision -> borrador` desde el principio y **no habia funcion para
hacerla**: quien revisaba algo incompleto tenia que aprobarlo igual o marcarlo
obsoleto. Ahora existe `return-to-draft`.

**Dos defectos que solo aparecieron manejando la pantalla en el navegador**, y
que ninguna prueba de unidad habria visto:

1. **Una fecha sin hora retrocedia un dia.** `new Date('2026-08-27')` es
   medianoche **UTC**; en Chile —UTC−4— eso es el 26. La base guardaba
   `valid_from = 2026-08-27` y la pantalla decia *"Rige desde 26 ago 2026"*. En
   un sistema de cumplimiento esa fecha es legal. `lib/fechas.ts` decide por la
   **forma** del dato: una fecha de calendario se formatea sin pasar por `Date`,
   una marca de tiempo si se convierte a hora local. Afecta a **todo huso al
   oeste de Greenwich**; al este pasa lo contrario y no se nota, que es peor.
2. **Dos botones con el mismo nombre en la misma fila.** El que abre el
   formulario de retiro y el que lo confirma se llamaban los dos "Marcar
   obsoleta": identicos para un lector de pantalla, e indistinguibles para
   `getByRole`.

**El store de documentos no cae a `mocks/`.** Cero documentos se ve como cero
documentos. En este modulo el dano de un respaldo falso es mayor que en
cualquier otro: quien ve "Procedimiento · Vigente" asume que existe y que puede
mostrarlo en una fiscalizacion.

**Y `CORS_ORIGINS` del compose de desarrollo ya es configurable.** Estaba fijo
en `http://localhost:3000`; levantar el frontend fuera del contenedor —en otro
puerto, para probar algo— hacia que la API rechazara el origen y la pantalla
dijera *"no se pudo contactar al servidor"*, que se lee como que la API esta
caida. Mismo valor por defecto de antes.

**Un `204` rompia TODOS los borrados de la aplicacion.** `res.json()` sobre un
cuerpo vacio lanza `SyntaxError`, y `request()` lo hacia siempre. Todos los
`DELETE` de la API responden 204, asi que cada borrado se leia como fallido: la
fila desaparecia de la base, la pantalla mostraba un error y **no recargaba**, y
quien lo hizo veia el registro seguir ahi. Reintentar daba 404, que se lee como
"esto esta roto". Se encontro borrando un equipo desde la pantalla y comparando
con la API — ninguna prueba lo habria visto, porque todas simulan `api`.

**Las tres pantallas ISO no llamaban a la API.** Aspectos Ambientales, Riesgos y
Oportunidades y Equipos Regulados leian `mocks/` **directamente**, sin una sola
peticion, mientras la API tenia CRUD completo de las tres desde hacia tiempo.
Ahora hay un `iso-store` unico para las tres, porque la cadena de 14001 es una
sola —aspecto significativo → riesgo → plan— y "que aspecto quedo sin tratar"
no se puede contestar mirando solo los aspectos.

**El vocabulario de esas pantallas estaba en el idioma equivocado.**
`packages/shared` define `riesgo`, `identificado`, `aspecto_ambiental`; la base
guarda `risk`, `identified`, `environmental_aspect`. Manda la base
(`lib/iso-vocabulario.ts`), y lo que no reconoce **se muestra crudo** en vez de
esconderse tras un guion: un valor feo se arregla, uno escondido no.

**`environmental_aspects.significance` guardaba estados de cumplimiento.** Su
CHECK admitia `compliant / partial / non_compliant / pending` —copiados de
`article_compliance`— cuando la significancia (ISO 14001 §6.1.2) contesta otra
pregunta: si el aspecto importa lo suficiente como para gestionarlo. La columna
"Significativo" y el filtro "significativo sin tratar" **no podian funcionar**,
porque `significant` no era un valor que la base admitiera. Lo corrige `db/21`;
las filas existentes pasan a `pending` y **no se traducen**, porque traducirlas
seria inventar una evaluacion que nadie hizo.

**El selector de planta ofrecia identificadores de ejemplo.** `useTenants()`
pide `/tenants/` sin declarar empresa, y esa ruta responde **401** cuando la
sesion viaja por `X-Tenant-Id`. El `Promise.all` entero se cae y el store se
queda con `mockTenants`, cuyas plantas son `planta-rancagua` mientras la API usa
UUID. Sintoma al crear un equipo: **422, `facility_id` no es un UUID valido**. Y
el filtro por planta comparaba un slug contra un UUID, asi que elegir una planta
dejaba la tabla vacia sin explicacion. Las pantallas ISO piden `/facilities/`
por su cuenta; **el resto sigue dependiendo de ese store**.

**Las normas desactualizadas ya se pueden actualizar** (`db/19` del PR de
notificaciones no, esto es aparte). El aviso solo avisaba, y ademas la matriz
**ya mostraba los articulos del texto vigente** —la pantalla los pide por
`/catalog/norms/{id}/articles`, que devuelve los de `is_current`—, asi que
`selected_version_id` era un dato que solo miraba el aviso y las evaluaciones
viejas eran invisibles. Medido: la Ley 19.300 apuntaba a una version con **2
articulos** mientras la vigente tenia **151**, y de sus 4 evaluaciones
**ninguna** estaba en la vigente.

Actualizar apunta la norma al texto de hoy y siembra sus articulos por evaluar.
**No migra las evaluaciones anteriores y no las borra**: migrarlas seria
inventar —entre versiones los articulos se renumeran, se parten y desaparecen—
y borrarlas destruiria la respuesta ante una auditoria del periodo en que se
hicieron. Verificado sobre la Ley 19.300: quedo en 155 filas = 151 nuevas
pendientes + **las 4 conservadas**.

**Y una trampa de las pruebas que cuesta media hora:** un `UPDATE` crudo con
`db.execute(text(...))` **no actualiza el mapa de identidad de la sesion**. La
fila cambia en la base y `db.get()` sigue devolviendo el objeto viejo, asi que
la prueba falla con "DID NOT RAISE" y el mensaje no se parece en nada a la
causa. `db.expire_all()` despues del `UPDATE`.

**PowerShell, no bash.** El entorno del usuario es Windows: `&&` y `<` no
funcionan en la terminal. Un comando por linea.

## Verificacion

```bash
npm run spec:check                      # los 4 artefactos de cada cambio
cd apps/api && python -m pytest         # 671 pruebas, 41 archivos
cd apps/web && npx vitest run           # 484 pruebas, 40 archivos
cd apps/api && python -m pytest         # 738 pruebas, 44 archivos
cd apps/web && npx vitest run           # 421 pruebas, 34 archivos
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

