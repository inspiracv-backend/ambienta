# AI Service de Ambienta

Implementación Python del servicio de IA, integrada en `apps/ai-service`.

## Configuración en Ambienta

Crear `apps/ai-service/.env` a partir de [`.env.example`](.env.example). Los valores mínimos
para que el proceso web arranque son `BACKEND_URL` y `DATABASE_URL_CONSULTA`; también se
requiere `DATABASE_URL_SINCRONIZADOR` para actualizar el índice y `DATABASE_URL_ADMIN` más
`CLAVE_IA_CONSULTA`/`CLAVE_IA_SINCRONIZADOR` para ejecutar las migraciones.

En Docker, `BACKEND_URL` debe apuntar al host de API alcanzable desde el contenedor, por ejemplo
`http://api:8000/api/v1` si se conecta a la red de Compose de Ambienta. Las URLs de PostgreSQL
deben usar el host de la base dedicada al servicio (no la base del backend). Para sincronizar
contra Ambienta en producción se requiere `SERVICIO_TOKEN`; en desarrollo puede usarse
`SERVICIO_TENANT_ID`, pero se desactiva la identidad real y no se guardan conversaciones.

El proveedor de producción requiere `OPENAI_API_KEY` o `ANTHROPIC_API_KEY` según la selección.
Con OpenAI, `DIMENSION_EMBEDDINGS` tiene que coincidir con la dimensión creada por la migración
(1536 por defecto). Si se cambia, hay que recrear el esquema/vectorización y sincronizar de nuevo.

El archivo `compose.yml` de este directorio levanta una base pgvector y un backend simulado para
desarrollo local. La pipeline valida lint, pruebas y construcción Docker de forma independiente
del backend de producto.

Responde consultas de cumplimiento ambiental citando la norma, o dice que no sabe. Consume la API
de Ambienta tal como la describe el handoff del 08/09/2026 y guarda cada conversación en el
backend, con sus citas.

Las especificaciones están en [`specs/`](specs/): cada módulo implementa una y cada
escenario de la spec es una prueba con el mismo nombre.

---

## Probarlo en cinco minutos, sin claves

```bash
docker compose up --build
```

Levanta la base con pgvector, aplica las migraciones, arranca un **backend simulado** con las
reglas del handoff, sincroniza el catálogo y deja el servicio en `http://localhost:8100`.
Usa un modelo demo que no redacta (pega la mejor oración de la evidencia) y embeddings locales:
sirve para ver el circuito completo, no para medir calidad.

```bash
curl -s localhost:8100/consulta -H 'Content-Type: application/json' \
     -H 'X-Tenant-Id: a0000000-0000-0000-0000-000000000001' \
     -d '{"pregunta": "¿Qué dice el artículo 11 de la Ley 19.300?"}' | jq

# en streaming
curl -N localhost:8100/consulta -H 'Accept: text/event-stream' -H 'Content-Type: application/json' \
     -H 'X-Tenant-Id: a0000000-0000-0000-0000-000000000001' \
     -d '{"pregunta": "¿qué me exige mi RCA sobre material particulado?"}'
```

Sin Clerk configurado es **modo desarrollo**: la empresa va en `X-Tenant-Id`, no hay usuario, y
la conversación no se guarda (`"guardado": false`). Es la misma regla que el backend.

Con OpenAI: `PROVEEDOR_LLM=openai PROVEEDOR_EMBEDDINGS=openai DIMENSION_EMBEDDINGS=1536
UMBRAL_EVIDENCIA=0.40 OPENAI_API_KEY=... docker compose up --build`. Cambiar la dimensión obliga
a empezar con la base vacía (`docker compose down -v`).

---

## Cómo está armado

```
src/ambienta_ia/
  config.py            variables de entorno, validadas al arrancar            SPEC-09
  backend/             cliente de la API de Ambienta, errores, modelos        SPEC-01
  identidad.py         JWT de Clerk, tenant_id, /me, modo desarrollo          SPEC-02
  conocimiento/        pool por rol, empresa fijada por transacción, migrar  SPEC-03
  sincronizar/         árbol de artículos → fragmentos, versión vigente       SPEC-04
  citas.py             "DS 40" = "D.S. N° 40" = decreto_supremo 40/2012       SPEC-05
  recuperacion/        exacta, palabras, semántica, histórica, RRF            SPEC-05
  agente/              grafo, herramientas, verificación de citas, revisor    SPEC-06
  consulta.py          conversación en el backend, pregunta, respuesta        SPEC-07
  api/                 POST /consulta (JSON y SSE), /salud, /listo            SPEC-07/09
  evaluar/             métricas, umbrales, CLI                                SPEC-08
  observabilidad.py    logs JSON y una traza por consulta                     SPEC-09
  proveedores/         modelo y embeddings detrás de una interfaz
  demo/                backend simulado y sus datos (solo pruebas y demo)
migraciones/           roles y esquema, con RLS
evaluacion/            dataset semilla, umbrales y la primera medición
tests/                 unit · integracion · evaluacion
```

### Las reglas que el código hace cumplir

| Regla | Dónde |
|---|---|
| La empresa sale del token verificado; ningún método ni herramienta la recibe | `identidad.py`, `backend/cliente.py`, `agente/herramientas.py` |
| El token de la persona se reenvía: el asistente ve lo que la persona ve | `identidad.py` |
| RLS en la base propia, dos roles sin bypass: el que consulta no escribe | `migraciones/001_esquema.sql` |
| Paginación por `X-Has-More`, `updated_since` con el máximo visto | `backend/cliente.py`, `sincronizar/` |
| La versión vigente sale de `is_current`; si empatan, la más reciente | `sincronizar/arbol.py` |
| La evidencia se decide con la similitud coseno, antes de fusionar | `recuperacion/buscar.py` |
| Sin evidencia no se redacta; tras dos rechazos, abstención | `agente/grafo.py` |
| Toda etiqueta `[F#]` citada tiene que existir en esta consulta | `agente/evidencia.py` |
| La pregunta se guarda antes del modelo; la respuesta, completa y con citas | `consulta.py` |

---

## Desarrollo

```bash
uv venv .venv && uv pip install -e ".[dev,openai,anthropic]"
docker run -d --name mentoria-pgvector -e POSTGRES_PASSWORD=ambienta -p 55432:5432 pgvector/pgvector:pg16
.venv/bin/pytest            # unit + integración + evaluación
.venv/bin/ruff check src tests
```

Las pruebas de integración usan `TEST_DATABASE_URL` (por defecto el contenedor de arriba),
crean una base por corrida y la borran. Sin PostgreSQL se saltan. **Usar un PostgreSQL solo para
las pruebas:** los roles `ia_consulta` e `ia_sincronizador` son de todo el servidor, y las pruebas
les reescriben la clave.

### Contra el backend real, sin depender de nadie

`mentoria/prueba-contra-ambienta/` levanta el backend de
Ambienta desde su repo público, con identidad real (un Clerk local) y el catálogo de la BCN, y
corre 34 chequeos de punta a punta. Ahí están también los hallazgos.

### Contra el backend real

1. Copiar `.env.ejemplo` a `.env` y completar.
2. `python -m ambienta_ia.conocimiento.migrar`
3. `python -m ambienta_ia.sincronizar` (con `SERVICIO_TOKEN` de la cuenta `servicio_lectura`)
4. `uvicorn ambienta_ia.api.app:app --port 8100`

Para integrar el servicio al despliegue de producto todavía hay que añadirlo como servicio del
Compose de despliegue y conectarlo a la red del backend y al proxy. Este paso queda separado para
que levantar el AI Service no altere el ciclo de vida actual de la API.

---

## Lo que queda pendiente y de quién depende

| Qué | Por qué importa | De quién |
|---|---|---|
| `openapi.json` del 08/09 | `backend/modelos.py` está escrito a mano desde el spec del 02/09 y el handoff; hay que regenerarlo y comparar | Equipo de Ambienta |
| Usuario de Clerk de prueba por empresa | Probar el guardado de conversaciones con identidad real | Equipo de Ambienta |
| RCA y documentos cargados | La herramienta de normativa propia y el aislamiento solo se prueban con datos | Equipo de Ambienta |
| Nombre exacto del estado de una revisión de documento | `VersionDocumento` acepta `status` o `estado` hasta confirmarlo | Equipo de Ambienta |
| Lectura de artículos de normativa propia | Se usa `/catalog/norms/{id}/articles` (mismas tablas con RLS); confirmar que responde para una RCA | Equipo de Ambienta |
| Proveedor de producción y calibración | El umbral y los mínimos de evaluación se midieron con embeddings locales | Mentoría + equipo |
| Dataset dorado con criterio legal | La semilla no reemplaza al experto | Equipo legal |
