# Plan de implementación

De un conjunto de scripts de guía a un AI Service que se puede desplegar dentro del compose de
Ambienta, consumiendo la API real y guardando las conversaciones en el backend.

---

## Estado al 20/09/2026

| Fase | Estado |
|---|---|
| 0 · Preparación | ✅ salvo traer el `openapi.json` del 08/09 (pedido al equipo). [D0] cerradas: proveedores detrás de una interfaz, OpenAI por defecto, y un proveedor local sin red para pruebas y demo |
| 1 · Material corregido | ✅ 8 pruebas, verificadas contra el código anterior |
| 2 · Conectado | ✅ **contra el backend real** (rama `feat/cierre-con-eficacia` levantada en local, 21/09) |
| 3 · Con datos | ✅ **con el catálogo real de la BCN**: 24 normas, 792 fragmentos |
| 4 · Encuentra | ✅ |
| 5 · Responde | ✅ **contra el backend real con identidad real** (Clerk local): 34/34 chequeos, dos corridas. Falta su Clerk real, que es configuración |
| 6 · Medido y operable | ✅ evaluación con umbrales en CI, Dockerfile, compose, trazas. Falta el dataset dorado |

189 pruebas en total (181 del servicio, 8 del material) más la prueba de punta a punta contra
el backend real (`prueba-contra-ambienta/`, 34 chequeos). Lo que falta depende de lo que se le
pide al equipo (tabla de abajo).

## Punto de partida

**Lo que el backend ya resuelve** (handoff del 08/09): catálogo BCN cargado (24 normas, 26
versiones, 689 artículos), versiones y articulado por fecha, `updated_since`, paginación con
`X-Has-More`, enlace de descarga firmado con checksum, búsqueda transversal, historial,
comentarios, normativa propia (RCA) y persistencia del chatbot con citas.

**Lo que no existe en ningún lado:** el AI Service. Ni en este repositorio ni en el monorepo
(`apps/ai-service/` es un archivo de TypeScript).

**Lo que hay acá:** 12 decisiones de diseño que siguen valiendo, y código de guía con cinco
defectos que hacen responder mal sin avisar (SPEC-00).

---

## Fases

Cada fase termina con algo que se puede correr y demostrar. Ninguna empieza sin las specs de su
fase revisadas.

### Fase 0 · Preparación
- Rama de trabajo y estas specs revisadas por el equipo.
- **Traer el `openapi.json` del 08/09** desde `docs/integracion-agente/` del monorepo y
  reemplazar `00-contrato/backend/`. Todo lo demás se escribe contra ese archivo.
- Generar los modelos Pydantic del backend desde ese spec.
- Esqueleto de `servicio/`: `pyproject.toml`, estructura de carpetas, pytest y ruff en CI.
- Cerrar las decisiones abiertas marcadas **[D0]** abajo.

**Se demuestra:** `pytest` corre en CI sobre un paquete vacío; los modelos generados importan.

### Fase 1 · El material deja de enseñar lo que no es (SPEC-00)
Independiente del resto; se puede hacer en paralelo con la fase 2.
- Los cinco defectos 🔴 corregidos en `03-retrieval/`, `04-evaluacion/` y `05-agente/`.
- `cruce.md` y `verificar_alineacion.py` rehechos contra el spec del 08/09.
- Cada README de etapa apunta a su módulo en `servicio/`.

**Se demuestra:** `04-evaluacion/metricas.py` da una métrica de abstención que coincide con
lo que se ve a mano; el agente de guía termina en abstención cuando no tiene evidencia.

### Fase 2 · Conectado (SPEC-01, SPEC-02)
- Cliente HTTP contra las rutas reales, con paginación por cabecera y reintentos correctos.
- Validación del JWT de Clerk, `tenant_id`, `/me`, reenvío del token de la persona.
- Modo desarrollo con `X-Tenant-Id`, igual que el backend.

**Se demuestra:** la secuencia mínima del handoff (§1, cinco llamadas) corre desde Python
contra el compose de Ambienta.

### Fase 3 · Con datos (SPEC-03, SPEC-04)
- Base del AI Service con migraciones, RLS y rol sin bypass.
- Sincronizador del catálogo: árbol de artículos, `ruta`, regla `is_current`, `updated_since`
  con el máximo visto, reindexar solo lo que cambió.

**Se demuestra:** dos corridas seguidas; la primera indexa las 24 normas, la segunda no hace
nada. La Ley 19.300 queda con su versión vigente correcta.

### Fase 4 · Encuentra (SPEC-05)
- Búsqueda exacta por norma y artículo sobre `norm_type` + `norm_number`.
- Palabras y semántica, umbral de evidencia **antes** de fusionar, RRF después.
- Consultas históricas con `vigente_el`, en vivo contra el backend.

**Se demuestra:** "¿qué dice el artículo 11 de la Ley 19.300?" trae el 11 primero; una
pregunta fuera del corpus devuelve vacío.

### Fase 5 · Responde (SPEC-06, SPEC-07)
- Grafo con revisión que termina en abstención, nunca en una respuesta rechazada.
- Herramientas: normativa, normativa propia, obligaciones, búsqueda transversal, respaldo
  documental, historial.
- `POST /consulta` con SSE; la conversación y las citas quedan en `/support/chatbot`.

**Se demuestra:** una conversación de tres turnos desde el frontend de Ambienta, guardada en el
backend con `cited_norm_ids`, y la misma pregunta desde otra empresa sin ver nada ajeno.

### Fase 6 · Medido y operable (SPEC-08, SPEC-09)
- Dataset dorado sobre las 24 normas, armado con el experto legal del equipo.
- Umbrales mínimos en CI: un cambio que baja el recall o la abstención no se mergea.
- Trazas por consulta, logs JSON, Dockerfile, servicio en el compose.

**Se demuestra:** reporte de evaluación en cada PR; una consulta se puede reconstruir entera
desde su traza.

---

## Relación con las sesiones

| Sesión | Fases que se revisan |
|---|---|
| 3 · Ingesta | 1, 2 y 3 |
| 4 · Recuperación | 4 |
| 5 · Evaluación | 6 (evaluación) |
| 6 · Agente | 5 y 6 (operación) |

La sesión 2 (contrato) queda cubierta por `contrato/ai-service.openapi.yaml` y SPEC-01.

---

## Lo que necesitamos del equipo de Ambienta

Sin esto hay fases que no se pueden probar. Van en la respuesta al handoff.

| Qué | Para qué fase | Por qué |
|---|---|---|
| El `openapi.json` del 08/09 | 0 | Todo se escribe contra ese archivo |
| Un usuario de Clerk de prueba por empresa demo (o que el modo desarrollo acepte un usuario) | 5 | En modo desarrollo `/me` devuelve usuario `null` y un mensaje necesita autor: sin esto no se puede guardar una conversación en pruebas |
| Una RCA con artículos y 2 o 3 documentos (vigente y borrador) en cada empresa demo | 5 | Sin datos privados no se puede probar lo de más valor ni el aislamiento |
| La lista blanca de normas BCN | 3 | Qué traer de las 748.000 es decisión de producto |
| Si el compose tiene o no `pgvector` | 3 | El 02/09 lo vimos en el compose; el handoff dice que no está |
| Quién arma el dataset dorado con criterio legal | 6 | Las respuestas de referencia no las puede escribir alguien sin formación jurídica |

---

## Decisiones abiertas

Las marcadas **[D0]** se cierran en la fase 0 porque cambian el esqueleto.

| # | Decisión | Recomendación | Motivo |
|---|---|---|---|
| **[D0]** A | Proveedor del modelo de lenguaje | Detrás de una interfaz; por defecto el que el equipo ya usa en el backend (`model_name` del handoff) | Cambiarlo no puede tocar más de un archivo |
| **[D0]** B | Proveedor de embeddings | Detrás de una interfaz; elegir midiendo con el dataset, no antes | La dimensión del vector es parte del esquema: cambiar de modelo obliga a reindexar |
| C | ¿Se indexan RCA y documentos privados en la base del AI Service? | **V1: no.** Se consultan en vivo por herramienta con el token de la persona. V2: sí, con RLS | Mientras no haya datos privados indexados, la base del AI Service no guarda nada que no sea público y el aislamiento sigue siendo solo del backend |
| D | Consultas históricas | En vivo contra `articles?vigente_el=`; se indexa solo lo vigente | 689 artículos no justifican indexar todas las versiones |
| E | Streaming | SSE desde el AI Service; al backend se guarda el mensaje completo al terminar | Es lo que el handoff asume (§8) |
| F | ¿El agente puede escribir en el backend (comentarios, obligaciones)? | **No en V1.** Solo lee y guarda sus propios mensajes | Una escritura con el token de la persona es una acción que la persona no hizo |

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| El contrato del backend cambia mientras construimos | Modelos generados desde el spec y test de contrato en CI: el cambio rompe el build, no la producción |
| Probar solo en modo desarrollo y descubrir los problemas de Clerk al final | La fase 5 no se da por cerrada sin una corrida con usuarios de Clerk reales |
| Una respuesta vacía se lee como "no hay normativa" cuando es un `tenant_id` equivocado | SPEC-02: toda lista vacía inesperada se registra con el `tenant_id` de la sesión |
| El dataset lo arma quien construye el sistema y mide lo que el sistema ya sabe hacer | SPEC-08: las preguntas las escribe el equipo legal sin ver las respuestas del sistema |
