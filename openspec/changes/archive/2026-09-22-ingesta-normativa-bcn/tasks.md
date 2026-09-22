# Tareas — Ingesta del catálogo normativo desde la BCN

## Supuestos vigentes

Probados contra el servicio real el 13-ago-2026, no leídos de la documentación.

- **`datos.bcn.cl/sparql` responde 200 sin autenticación** y contiene **748.783**
  entidades `bcn-norms#Norm`.
- El namespace es `http://datos.bcn.cl/ontologies/bcn-norms#`. Probar con
  `bcn-resources#` devuelve cero resultados: es otra ontología.
- Las propiedades que hacen falta existen: `leychileCode`, `hasNumber`,
  `dc:title`, `publishDate`, `promulgationDate`, `type`, `hasXmlDocument`,
  y las de relación y versión.
- **La misma norma vuelve varias veces** con URIs distintas (obra, expresión,
  manifestación). Comprobado con la Ley 20.920: tres filas, un solo
  `leychileCode`.
- **El web service XML de 2009 responde 401** en `leychile.cl` y en `bcn.cl`.
- **La API key emitida el 13-ago-2026 está "No activa"**: devuelve 401 con
  `Authorization: Bearer`, `X-API-Key`, `?apikey=` y `?api_key=`.
- `legal_norms` ya tiene `external_norm_id`, `official_url` y `source_payload`.
- `apps/worker` es **una carpeta vacía**.

## Supuestos por confirmar

**No empezar la fase que depende de cada uno sin resolverlo.**

- [x] **Qué subconjunto de las 748.783 normas se trae.** Sin criterio, la
      ingesta no debe correr suelta. Bloquea la Fase 3 **(decidido el 21-sep, plan de cierre §6 decisión 1: las normas ya clasificadas y las de la reunión del piloto; viven en `TERMINOS`. Los "decretos 40 y 48" esperan que negocio diga cuáles son)**
- [x] **Cuál de las cuatro formas de mandar la API key es la correcta**, cuando **(no aplica: el 401 era el `User-Agent`, no la clave (`bcn.py::NAVEGADOR`))**
      la BCN la active. Bloquea la Fase 5
- [x] **Qué gana cuando la fuente contradice lo cargado a mano** **(la fuente gana en lo que es suya —título, número, fechas, texto— y lo que decidió una persona se conserva: ver Fase 3)**
- [ ] **Cada cuánto sincroniza, y quién revisa lo que cambió.** → **al desplegar**, fuera de la 1.0 (que no despliega): es una línea de cron. Lo que cambió ya se ve: la bitácora y el aviso de normas con versión más nueva. Una norma
      derogada río arriba cambia el cumplimiento de todas las empresas a la vez

## Fase 0 — Prerequisitos fuera de este módulo

- [x] **`countries` sin endpoint de lectura** (#166). Toda norma necesita país;
      sin esto no se puede crear ninguna
- [x] Confirmar que `legal_sources` tiene una fila para la BCN, o crearla
- [x] Pedir a la BCN la activación de la API key, y preguntar de paso el formato **(no aplica: el texto y el SPARQL bajan sin clave)**
      de autenticación
- [x] `BCN_API_KEY` en `.env.example` **con el nombre y sin el valor**, y en los **(no aplica: no hay `BCN_API_KEY` que guardar)**
      dos compose

## Fase 1 — El cliente de consulta

- [x] Módulo aislado con las consultas SPARQL, sin lógica de negocio dentro
- [ ] Prefijo fijado y validación de que la respuesta trae los campos esperados → **parcial**: una fila sin `leychileCode` se descarta, y el término que no trae su norma deja la corrida en `partial`. No hay validación de esquema de la respuesta
- [x] **Cero resultados no es un éxito**: se distingue de "no había novedades"
- [x] Reintento con espera creciente; un fallo de la fuente no rompe nada **(22-sep: `bcn._consultar`, solo ante red, 5xx o 429; `test_bcn_reintentos.py`)**
- [x] Tests con la respuesta simulada, incluidas las malformadas **(filas duplicadas y sin código en `test_catalogo_desde_la_bcn.py`; fallos de red y consultas rechazadas en `test_bcn_reintentos.py`)**
- [x] **Una prueba contra el servicio real**, no solo simulada. Es la lección del
      JWT Template: verificar el proveedor antes de construir encima

## Fase 2 — El mapeo

- [x] De propiedad BCN a columna, según la tabla del design
- [x] **Deduplicar por `leychileCode`, nunca por URI**: la URI identifica una
      representación, el código identifica la norma
- [ ] Guardar la respuesta cruda en `source_payload`, para poder remapear sin
      volver a pedir → **después del piloto**: hoy guarda la URI y el tipo de la BCN, que es lo que usa la sincronización para volver a la fuente
- [x] Extraer el organismo desde la ruta de la URI
- [x] Tests del mapeo con la Ley 20.920 como caso conocido

## Fase 3 — La sincronización

**Bloqueada por el criterio de qué normas traer.**

- [x] Buscar por `external_norm_id`: si existe actualiza, si no crea
- [x] **Refrescar solo lo que la BCN es dueña.** Lo que decidió una persona
      —alcance, responsables, qué artículos entran en el cálculo— no se toca
- [x] Relaciones entre normas a `legal_relations` **(22-sep: `sincronizar_relaciones`, las cinco propiedades de la ontología y sus inversas; una sola vez por el índice de `db/33`. La BCN no publica derogaciones como relación. Consultables en `GET /catalog/norms/{id}/relations` y en la ficha de la norma)**
- [x] Versiones a `legal_norm_versions`, distinguiendo la vigente
- [x] Una relación hacia una norma ausente **no inventa la norma**: se registra
      sin resolver **(en `response_metadata.relaciones_sin_resolver` de la corrida: 292 en la primera, casi todas concordancias de la Ley 19.300)**
- [x] Tests de idempotencia: correr dos veces no duplica ni pisa decisiones

## Fase 4 — La bitácora

**Hecha el 14-sep** (`app/tareas/sincronizar_bcn.py::anotar_corrida`). Las demás
fases de este archivo están **desfasadas**: el 26-ago la ingesta se construyó por
otro camino (SPARQL + XML de Ley Chile, ver CLAUDE.md) y sus casillas no se
volvieron a mirar. Hay que auditarlas contra el código antes de archivar.

- [x] Cada corrida escribe en `norm_sync_runs`: inicio, fin, creadas,
      actualizadas (incluye adoptadas) y versiones; las encontradas y lo que
      no encontró su norma van en `response_metadata`, los fallos en `error_detail`
- [x] Un fallo de la fuente deja registro y no deja el catálogo a medias: un
      savepoint por término — antes un fallo deshacía los términos anteriores
- [x] **No exponerla como recurso editable**: `GET /catalog/sync-runs`, solo
      lectura, declarado en `SIN_CRUD_COMPLETO`; el catálogo muestra la última.
      **Y desde el 22-sep tampoco la puede editar la aplicación**: `db/33` le
      quita `UPDATE` y `DELETE` al rol, como a `audit_log`
- [x] Tests de los desenlaces: completa, parcial, fallida, y en seco no deja
      corrida (`test_bitacora_bcn.py`, `test_bitacora_expuesta.py`)

## Fase 5 — El articulado

**Bloqueada por la activación de la API key.**

- [x] Reintentar la autenticación cuando la BCN habilite la clave **(no aplica: nunca hizo falta autenticarse)**
- [x] Traer el texto por `leychileCode`, que es el `idNorma` del web service
- [x] Poblar `legal_articles`
- [x] Recién con esto la matriz legal se puede evaluar artículo por artículo

## Fase 6 — Cómo se dispara

- [x] Comando manual, con la lógica **separada de cómo se invoca**
- [x] Que mudarlo al worker sea cambiar el disparador y nada más
- [x] Documentar cómo correrlo y cómo leer la bitácora

## Orden sugerido

Fase 0 primero: sin `countries` no se puede crear ninguna norma, por más que la
consulta funcione.

Las fases 1 y 2 se pueden hacer y probar hoy: el SPARQL responde. **La Fase 3 no
debe correr suelta** hasta que exista el criterio de qué traer — 748.793 normas
no caben en una decisión técnica.

La Fase 5 depende de un tercero. El adaptador sirve igual sin ella: entrega
metadatos y relaciones, que es lo que las tablas vacías esperaban.
