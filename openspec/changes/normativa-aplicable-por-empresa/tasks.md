# Tasks: Normativa aplicable por empresa

## Lo que ya está construido y no hay que rehacer

Verificado contra la base el 18-ago-2026. Vale leerlo antes de empezar: más de la
mitad del modelo existe.

| Pieza | Estado |
|---|---|
| `sectors` | **Existe y sembrada** con 8 secciones CIIU, incluida `C · Industria manufacturera`. Tiene `parent_id` para subclases |
| `norm_sectors` | **Existe, vacía.** Con `applicability_level` (directa/indirecta/referencial), `rationale`, `confidence` y `source` |
| `legal_norm_versions` | **Existe** con `is_current`, `content_hash`, `valid_from/valid_to` |
| `legal_articles` | **Existe**, cuelga de la versión. Expuesto en `GET /catalog/norms/{id}/articles` |
| `tenant_legal_matrices`, `matrix_norms` | **Existen**, se pueblan a mano |
| `article_compliance` | **Existe y funciona de punta a punta** desde el 17-ago |

Lo que falta es el eslabón del medio, no los extremos.

## Decisiones pendientes que NO bloquean empezar

Ninguna de las dos cambia el modelo; se pueden responder mientras se construye:

- Si los 21 sistemas sectoriales del RETC (#103) son otra dimensión distinta de CIIU.
- Si el tramo de tamaño se declara o se deriva de una nómina futura.

## 1. Esquema

- [x] 1.1 Escribir `db/08_perfil_normativo.sql` idempotente
- [x] 1.2 Agregar `tenants.sector_id` (FK a `sectors`, **nullable**) y `tenants.size_bracket` con su CHECK de tramos
- [x] 1.3 Agregar a `matrix_norms` **solo** `inclusion_source`: la versión ya la da `selected_version_id`, el responsable `created_by`, y lo que deja de aplicar `applicability` + `applicability_reason`. Duplicarlas habría dejado dos fuentes de verdad
- [x] 1.4 Verificar que el script corre dos veces seguidas sin error y sobre una base ya existente
- [x] 1.5 Registrar el archivo en los lugares que deben coincidir. **Son cinco, no cuatro**: `docker-compose.yml`, `db/run.sh`, `db/README.md` y el bucle de `.github/workflows/ci.yml` — este último lo documenté mal en `CLAUDE.md` y CI falló con `column "sector_id" does not exist`. `docker-compose.prod.yml` no monta las migraciones numeradas
- [x] 1.6 Confirmar que no hace falta política RLS nueva — no se crea ninguna tabla; si eso cambiara, la migración debe declarar su política y sus GRANT

## 2. Perfil de la empresa

- [x] 2.1 Exponer sector y tramo en los esquemas de lectura y escritura de `tenants`
- [x] 2.2 `GET /catalog/sectors` ya existe: verificar que sirve para poblar el selector del alta
- [x] 2.3 Marcar como **sin perfil normativo** a la empresa sin sector, y que la API lo diga explícitamente
- [x] 2.4 Tests: alta sin sector se acepta y queda sin perfil; el giro escrito **no** cuenta como sector

## 3. Clasificación de normas por sector

- [x] 3.1 Modelo SQLAlchemy de `norm_sectors` — **ya existía**; se le agregaron `classified_by` y `classified_at`
- [x] 3.2 `GET /catalog/norms/{id}/sectors` — leer la clasificación, sin exigir Admin Global
- [x] 3.3 `PUT /catalog/norms/{id}/sectors/{sector_id}` — declarar aplicabilidad, **exige Admin Global**
- [x] 3.4 Rechazar la clasificación sin `rationale`
- [x] 3.5 Permitir acotar la clasificación a artículos concretos (`norm_sectors.article_id`)
- [x] 3.6 Registrar quién clasificó y cuándo
- [x] 3.7 Tests, **rompiéndolos a propósito**: sin fundamento se rechaza; un usuario de empresa no puede clasificar
- [x] 3.8 Declarar en `test_crud_cobertura.py` por qué este recurso no tiene CRUD completo, si corresponde — **sí hizo falta**: el test detectó `/catalog/norms/sectors` a medias y exigió el motivo

## 4. Cálculo de normativa aplicable

- [x] 4.1 Servicio que dado el perfil devuelve las normas del sector, separadas en obligatorias (directa) y recomendadas (indirecta/referencial)
- [x] 4.2 Cada norma devuelta indica **qué sector y qué nivel** la hicieron entrar
- [x] 4.3 Distinguir en la respuesta "el sector no tiene normas clasificadas" de "la empresa no tiene obligaciones"
- [x] 4.4 `GET /compliance/normativa-aplicable` — calcula y muestra, **sin escribir nada**
- [x] 4.5 Tests: sector con normas; sector sin clasificar; empresa sin perfil
- [x] 4.6 **Romper a propósito** el caso de la lista vacía y confirmar que el test falla

## 5. Generación de la matriz

- [x] 5.1 Servicio que sincroniza la matriz: agrega lo que falta, **nunca borra**
- [x] 5.2 Incorporar los artículos de la versión **vigente** de cada norma, en estado sin evaluar
- [x] 5.3 Conservar las evaluaciones existentes al recalcular
- [x] 5.4 Marcar como **ya no aplicable** lo que dejó de corresponder, sin borrarlo
- [x] 5.5 Respetar siempre lo agregado a mano: un recálculo no lo quita
- [x] 5.6 `POST /compliance/matrices/{id}/sincronizar`
- [x] 5.7 Tests del viaje completo: generar, evaluar, regenerar y **comprobar que la evaluación sobrevive**
- [x] 5.8 **Romper a propósito** la idempotencia y confirmar que el test lo detecta
- [x] 5.9 Medido: **4 evaluaciones en 196 ms**, segunda corrida +0 filas en 13 ms. **Pero la muestra es chica**: el seed solo tiene 2 normas con articulado, así que esto NO valida la preocupación del diseño (30 normas × 200 artículos = 6.000 filas). Hay que volver a medir cuando la ingesta BCN cargue normas reales

## 6. Aviso de versión desactualizada

- [ ] 6.1 Guardar en `matrix_norms` contra qué versión se evaluó
- [ ] 6.2 Consulta que compara esa versión con la que hoy tiene `is_current`
- [ ] 6.3 `GET /compliance/matrices/{id}/desactualizadas`
- [ ] 6.4 Que las evaluaciones sobre la versión anterior **sigan visibles**
- [ ] 6.5 Tests: versión nueva marca desactualizada; sin versión nueva no marca nada

## 7. Frontend

- [ ] 7.1 El alta de empresa pide sector y tramo
- [ ] 7.2 Pantalla de clasificación normativa para el Admin Global, mostrando **cuántas normas faltan clasificar** por sector
- [ ] 7.3 Pantalla del check: normativa aplicable separada en obligatorias y recomendadas, antes de generar
- [ ] 7.4 La matriz legal muestra **por qué entró** cada norma y si está desactualizada
- [ ] 7.5 Escrituras optimistas con reversión y aviso, como el resto de los stores
- [ ] 7.6 Tests de store, **rompiéndolos a propósito**

## 8. Cierre

- [ ] 8.1 Actualizar `docs/escrituras-del-frontend.md` con las acciones nuevas
- [ ] 8.2 Actualizar el estado en `CLAUDE.md`
- [ ] 8.3 Verificar: `python -m pytest`, `npx vitest run`, `bash db/run.sh --with-tests`
- [ ] 8.4 Archivar el cambio
