# Tareas — CRUD completo de los recursos de negocio

> **Marcadas porque están hechas, no porque se planificaran.** Este cambio se
> escribió después de implementarlo; ver la nota del `proposal.md`.

## Supuestos vigentes

Verificados contra el sistema real, no heredados del análisis.

- **52 tablas** en la base, **38 con política RLS**. Las otras 14 son catálogo
  compartido: la ley es igual para todas las empresas.
- Los recursos son **instancias directas de `CRUDBase` sin sobreescribir nada**.
  Comprobado antes de tocar el genérico: si alguno hubiera tenido overrides, la
  estrategia de arreglar un solo archivo no habría servido.
- **Las tablas no se crean desde SQLAlchemy.** No hay `Base.metadata.create_all()`
  en ninguna parte del repo.
- **Tres tablas tienen clave compuesta y no columna `id`**: `audit_participants`,
  `equipment_operators`, `facility_processes`.
- Las FK de PostgreSQL **no pasan por RLS**. Comprobado apuntando a una fila de
  otra empresa: la restricción se satisface.
- `SET LOCAL` **muere con la transacción**, así que el tenant se pierde en cada
  `commit`.

## Supuestos por confirmar

**No cerrar las tareas que dependen de cada uno sin resolverlo.**

- [ ] **De dónde salen `created_by` y `updated_by`**: sesión en `CRUDBase` o
      trigger en la base. Lo segundo cubre también las escrituras manuales
- [ ] **Semántica de null en los `Update`**: hoy `X | None = None` no distingue
      "no enviado" de "enviado como null"
- [ ] **Las 10 tablas que siguen sin API**: dependen de decisiones abiertas de
      otros cambios (CRM, información documentada, sub-tenancy)
- [ ] **`user_permissions`**: existe en la base sin API. Espera a que se apruebe
      `sistema-actores-roles-rbac`

## Fase 0 — Prerequisitos fuera de este módulo

- [x] Secuencia para `ticket_number` en la base (`db/06_ticket_number.sql`).
      Sin ella `POST /support/tickets` devolvía 500
- [x] `ambienta_app` con `LOGIN` (`db/07_rol_aplicacion.sql`), **con un bloque
      que aborta si el rol puede saltarse RLS**. Un rol de aplicación con
      `BYPASSRLS` deja el aislamiento en nada sin que nada lo advierta
- [x] Registrar los dos scripts nuevos en los **cuatro** lugares que deben
      coincidir: los dos compose, `db/run.sh` y `db/README.md`
- [x] CI: aplicar los 7 scripts **antes** de los tests. Estaban después, y solo
      2 de 7 — pytest corría contra una base vacía y sin el rol
- [x] CI: correr los tests como `ambienta_app`. Con el dueño de la base daría
      falsos verdes, porque es superusuario y salta RLS

## Fase 1 — Arreglar el genérico antes de exponer nada

- [x] `remove()` pasa a borrado lógico, con la fecha del reloj de la base
- [x] Punto único de filtrado de lo borrado para todas las lecturas
- [x] `get()` de `db.get()` a `select()`: por el mapa de identidad nunca pasaba
      por un `WHERE` donde filtrar
- [x] Borrar dos veces responde 404 sin mover la fecha original
- [x] Mensaje explícito al instanciar el genérico sobre un modelo sin columna
      `id`, en vez de un `AttributeError` a mitad de consulta
- [x] `expire_on_commit=False`: el refresco al serializar un `POST` abría una
      transacción nueva **sin rol y sin tenant**
- [x] Tests del genérico rompiendo a propósito lo que dicen proteger

## Fase 2 — Helpers compartidos

- [x] Validación de que el destino de una FK sea **visible bajo RLS**, con la
      misma respuesta para "no existe" y "es de otra empresa"
- [x] Validación anti-ciclo para las jerarquías
- [x] Clase aparte para tablas de asociación de clave compuesta
- [x] Revivir la asociación borrada al recrearla, en vez de chocar con la única
- [x] Traducción de `IntegrityError` **por tipo de excepción, no por el texto**
      del mensaje del motor

## Fase 3 — Exponer los recursos

- [x] `DELETE` en los routers que ya existían: eran **0 de 26**
- [x] `GET` por identificador donde faltaba: eran **12 de 26**
- [x] Ocho tablas nuevas con CRUD completo: `departments`, `processes`,
      `integration_accounts`, `audit_participants`, `equipment_operators`,
      `facility_processes`, `entity_documents`, `facility_norm_assignments`
- [x] `POST /support/tickets`: autor tomado de la sesión, no del cuerpo del
      request. Confiar en el cuerpo dejaba crear tickets a nombre de otro
- [x] `/tenants/` deja de estar sin autenticar: exige admin global, acota a la
      empresa propia y responde 404 en vez de 403 — un 403 confirma que el
      recurso existe

## Fase 4 — Contrato

- [x] Derivar el 401 de que la ruta declare `security`
- [x] Derivar el 404 de que la ruta tenga un `{parámetro}` de path
- [x] Descripciones de tag para que Swagger agrupe por dominio

## Fase 5 — Verificación

- [x] Medir contra el contrato **en ejecución**, no leyendo código:
      **95 rutas, 211 operaciones**, y **37 recursos** con lectura y escritura
      completas
- [x] 10 ciclos CRUD de punta a punta contra la API levantada
- [x] Aislamiento: token de una empresa con el header de otra sigue devolviendo
      solo la propia
- [x] **84 funciones de prueba** en 10 archivos bajo `apps/api/tests/`
- [x] CI en verde con el esquema completo

## Fase 6 — Frontend

- [x] Adaptadores de lectura por recurso
- [x] Corregir el mapeo de obligaciones: los nombres de campo no coincidían con
      el esquema y el mapa de estados traducía a dos que el `CHECK` no admite
- [x] `tenants-store` trae plantas además de empresas
- [x] Enlaces profundos a los recursos nuevos
- [ ] **Escrituras**: cuatro stores de negocio actualizan solo el estado local.
      Crear o editar desde esas pantallas no llega a la base
- [ ] Schemas Zod de `packages/shared` al día con los Pydantic nuevos

## Fase 7 — Documentación

- [x] `docs/estado-crud-base-de-datos.md` con las cifras medidas
- [x] `docs/resumen-conversion-crud.md`
- [x] `db/README.md` con el conteo de políticas actualizado
- [x] Escribir este cambio y archivarlo, para que `openspec/specs/` deje de
      estar dos cambios atrás del sistema real
