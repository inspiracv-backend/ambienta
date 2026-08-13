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

- [ ] **Qué subconjunto de las 748.783 normas se trae.** Sin criterio, la
      ingesta no debe correr suelta. Bloquea la Fase 3
- [ ] **Cuál de las cuatro formas de mandar la API key es la correcta**, cuando
      la BCN la active. Bloquea la Fase 5
- [ ] **Qué gana cuando la fuente contradice lo cargado a mano**
- [ ] **Cada cuánto sincroniza, y quién revisa lo que cambió.** Una norma
      derogada río arriba cambia el cumplimiento de todas las empresas a la vez

## Fase 0 — Prerequisitos fuera de este módulo

- [ ] **`countries` sin endpoint de lectura** (#166). Toda norma necesita país;
      sin esto no se puede crear ninguna
- [ ] Confirmar que `legal_sources` tiene una fila para la BCN, o crearla
- [ ] Pedir a la BCN la activación de la API key, y preguntar de paso el formato
      de autenticación
- [ ] `BCN_API_KEY` en `.env.example` **con el nombre y sin el valor**, y en los
      dos compose

## Fase 1 — El cliente de consulta

- [ ] Módulo aislado con las consultas SPARQL, sin lógica de negocio dentro
- [ ] Prefijo fijado y validación de que la respuesta trae los campos esperados
- [ ] **Cero resultados no es un éxito**: se distingue de "no había novedades"
- [ ] Reintento con espera creciente; un fallo de la fuente no rompe nada
- [ ] Tests con la respuesta simulada, incluidas las malformadas
- [ ] **Una prueba contra el servicio real**, no solo simulada. Es la lección del
      JWT Template: verificar el proveedor antes de construir encima

## Fase 2 — El mapeo

- [ ] De propiedad BCN a columna, según la tabla del design
- [ ] **Deduplicar por `leychileCode`, nunca por URI**: la URI identifica una
      representación, el código identifica la norma
- [ ] Guardar la respuesta cruda en `source_payload`, para poder remapear sin
      volver a pedir
- [ ] Extraer el organismo desde la ruta de la URI
- [ ] Tests del mapeo con la Ley 20.920 como caso conocido

## Fase 3 — La sincronización

**Bloqueada por el criterio de qué normas traer.**

- [ ] Buscar por `external_norm_id`: si existe actualiza, si no crea
- [ ] **Refrescar solo lo que la BCN es dueña.** Lo que decidió una persona
      —alcance, responsables, qué artículos entran en el cálculo— no se toca
- [ ] Relaciones entre normas a `legal_relations`
- [ ] Versiones a `legal_norm_versions`, distinguiendo la vigente
- [ ] Una relación hacia una norma ausente **no inventa la norma**: se registra
      sin resolver
- [ ] Tests de idempotencia: correr dos veces no duplica ni pisa decisiones

## Fase 4 — La bitácora

- [ ] Cada corrida escribe en `norm_sync_runs`: inicio, revisadas, creadas,
      actualizadas, fallidas
- [ ] Un fallo de la fuente deja registro y no deja el catálogo a medias
- [ ] **No exponerla como recurso editable.** Editar la bitácora sería
      falsificar el registro de qué se sincronizó
- [ ] Tests de los tres desenlaces: bien, sin novedades, y fallo

## Fase 5 — El articulado

**Bloqueada por la activación de la API key.**

- [ ] Reintentar la autenticación cuando la BCN habilite la clave
- [ ] Traer el texto por `leychileCode`, que es el `idNorma` del web service
- [ ] Poblar `legal_articles`
- [ ] Recién con esto la matriz legal se puede evaluar artículo por artículo

## Fase 6 — Cómo se dispara

- [ ] Comando manual, con la lógica **separada de cómo se invoca**
- [ ] Que mudarlo al worker sea cambiar el disparador y nada más
- [ ] Documentar cómo correrlo y cómo leer la bitácora

## Orden sugerido

Fase 0 primero: sin `countries` no se puede crear ninguna norma, por más que la
consulta funcione.

Las fases 1 y 2 se pueden hacer y probar hoy: el SPARQL responde. **La Fase 3 no
debe correr suelta** hasta que exista el criterio de qué traer — 748.793 normas
no caben en una decisión técnica.

La Fase 5 depende de un tercero. El adaptador sirve igual sin ella: entrega
metadatos y relaciones, que es lo que las tablas vacías esperaban.
