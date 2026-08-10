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

**Hoy RLS no es la segunda barrera: es la única.** Medido el 10-ago-2026,
ninguna consulta de la aplicación filtra por `tenant_id` — ni `CRUDBase` ni un
solo router. Lo que separa a una empresa de otra es enteramente PostgreSQL.

Y RLS sólo se aplica si la transacción corre como `ambienta_app`. La API se
conecta como `ambienta`, que es **superusuario con BYPASSRLS**, así que todo
depende de que `SET LOCAL ROLE ambienta_app` se ejecute en cada transacción —
lo hace `get_tenant_db`, y sólo él.

- Usar **siempre** `get_tenant_db` para datos de empresa. `get_db` corre sin
  ninguna barrera: sirve para el catálogo global (que no tiene `tenant_id`) y
  para los health checks, nada más.
- **No consultar después de `db.commit()`.** El commit cierra la transacción y
  con ella se van el rol y el tenant: lo que venga después ve todas las
  empresas. Verificado — se pasa de 4 usuarios visibles a 6.
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

**Actualizado 09-ago-2026.** Si esto lleva meses sin tocarse, verificar antes
de confiar: `npm run spec`, `docker compose up -d`, `npx openspec list --specs`.

| Area | Estado |
|---|---|
| Base de datos | **Completa y verificada.** 52 tablas, 38 con RLS, 9 smoke tests en verde |
| API | 95 endpoints. Backend de auth completo (Clerk fases 1 y 2) |
| Tablero S-06/S-07 | **Conectado a datos reales** y verificado contra Postgres |
| Resto del frontend | 20 pantallas **con datos de ejemplo**, no con la API |
| Auth en el frontend | Cableado (Clerk fase 3), **inactivo sin llave**: sin `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` sigue el DevRoleSwitcher. Falta el token en las llamadas (fase 4) |
| worker · ai-service | Sin implementar |

**Lo unico que consume la API de verdad es el tablero.** Cualquier otra
pantalla que se vea funcionando esta leyendo `apps/web/mocks/`.

## Trampas conocidas

Cosas que ya costaron tiempo. Vale leerlas antes de tocar lo que mencionan.

**`db/01_schema.sql` no es una migracion.** Editarlo solo afecta a bases
nuevas. Todo cambio de esquema necesita ademas un `db/NN_*.sql` idempotente, y
ese archivo tiene que declarar **su propia politica RLS y sus GRANT**: el bucle
de politicas y el `GRANT ON ALL TABLES` de `01_schema` corren una sola vez, asi
que una tabla nacida en una migracion no los hereda y queda visible entre
empresas. La lista de archivos vive en cuatro lugares que deben coincidir: los
dos compose, `db/run.sh` y `db/README.md`.

**El modelo esta escrito dos veces.** `packages/shared` lo define en Zod y
`apps/api/schemas` en Pydantic, en dos lenguajes que no pueden importarse. Hoy
la sincronia es manual y ya se rompio: hubo codigo leyendo `compliance_answer`
e `is_active`, columnas que no existen, sin que nada lo detectara. **Contrastar
contra `db/01_schema.sql` y los modelos antes de escribir cualquier mapeo.**

**Los tests pueden ser vacuos.** Romper a proposito lo que un test dice
proteger y confirmar que falla. Se hizo con las dos propiedades de seguridad de
Clerk y con la del webhook.

**El aislamiento no avisa cuando se rompe.** Es la trampa mas cara de todas.
Un endpoint escrito con `get_db` en vez de `get_tenant_db`, o una consulta
puesta despues de un `db.commit()`, no falla: devuelve datos de todas las
empresas con normalidad. No hay excepcion, ni log, ni test que se ponga rojo
salvo los de `test_aislamiento.py`. Ver §4.

**PowerShell, no bash.** El entorno del usuario es Windows: `&&` y `<` no
funcionan en la terminal. Un comando por linea.

## Verificacion

```bash
npm run spec:check                      # los 4 artefactos de cada cambio
cd apps/api && python -m pytest         # 57 tests
cd apps/web && npx vitest run           # 190 tests
bash db/run.sh --with-tests             # 9 comprobaciones del esquema
```

