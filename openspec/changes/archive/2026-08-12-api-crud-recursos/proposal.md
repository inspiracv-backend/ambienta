# Proposal: CRUD completo de los recursos de negocio

> **Este cambio se escribió después de implementarlo, y conviene decirlo.**
>
> El trabajo se hizo entre el 10 y el 12 de agosto de 2026 sin pasar por
> `/opsx:propose`, saltándose la regla 1 de `CLAUDE.md`. Se documenta ahora para
> que `openspec/specs/` refleje el sistema real: sin esto, la próxima spec se
> escribe contra un estado imaginado, que es exactamente cómo llegamos a tener
> código leyendo `compliance_answer` e `is_active`, columnas que no existen.
>
> Lo que sigue describe el estado que se encontró y las decisiones que se
> tomaron. Las tareas van marcadas porque están hechas, no porque se planificaran.

Fuentes: contrato OpenAPI en ejecución · `db/01_schema.sql` · `apps/api/app/crud/base.py` · `docs/estado-crud-base-de-datos.md`.

## Contexto

### El número que engañaba

Al cerrar el CRUD de los recursos ya expuestos, el avance quedó en **17 de 26
recursos completos**. Es cierto, y se ve mejor de lo que era: mide *lo que
estaba expuesto*, no *lo que faltaba por exponer*.

| | Tablas |
|---|---|
| Total en la base | **52** |
| Con alguna API | 31 |
| **Sin ninguna API** | **21** |

El 40 % de las tablas no tenía forma de tocarse desde la aplicación.

### De dónde venía

| Operación | Recursos que la tenían |
|---|---|
| Crear | 24 de 26 |
| Listar | 22 de 26 |
| Leer uno | 12 de 26 |
| Actualizar | 15 de 26 |
| **Borrar** | **0 de 26** |

**Ningún recurso tenía borrado**, y el problema no era solo que faltara el
endpoint. `CRUDBase.remove()` hacía borrado **físico** mientras el esquema
estaba diseñado para borrado **lógico** con `deleted_at` e índices parciales. Al
mismo tiempo, las lecturas no filtraban `deleted_at`.

Las dos mitades estaban mal y se tapaban entre sí, precisamente porque ningún
router exponía el borrado. Exponerlo directo lo habría hecho nacer roto: una
fila borrada habría seguido apareciendo en los listados.

También había un endpoint devolviendo **500**: `POST /support/tickets`, cuya
columna `ticket_number` es `NOT NULL UNIQUE` y nadie generaba. Era el único roto
de los 91 — y justo el que sostiene el flujo del Cliente Invitado, cuyo único
propósito es crear solicitudes.

## Objetivo

Que cada recurso de negocio se comporte igual: las cinco operaciones, borrado
que preserva la evidencia, referencias que no cruzan de empresa y errores que
significan lo mismo en todas partes.

## Qué exige del resto del sistema

| Área | Qué necesita | Estado |
|---|---|---|
| `db/` | Secuencia para `ticket_number` (`06_ticket_number.sql`) | Hecho |
| `db/` | `ambienta_app` con LOGIN y sin poder saltarse RLS (`07_rol_aplicacion.sql`) | Hecho |
| CI | Aplicar los 7 scripts **antes** de los tests, con `ON_ERROR_STOP` | Hecho |
| CI | Correr pytest como `ambienta_app`, no como dueño de la base | Hecho |
| `apps/web` | Adaptadores por recurso y stores que dejen de leer `mocks/` | **Parcial** |
| `packages/shared` | Schemas Zod al día con los Pydantic nuevos | **Parcial** |
| Documentación | `db/README.md` con el conteo de políticas actualizado | Hecho |

## Lo que este cambio no hace

- **No conecta las escrituras del frontend.** Varias pantallas leen de la API
  pero al crear o editar actualizan solo el estado local. La API las soporta;
  falta cablearlas.
- **No implementa RBAC.** El aislamiento resuelto es *entre* empresas. Quién
  puede hacer qué *dentro* de una sigue en `sistema-actores-roles-rbac`.
- **No llena `created_by` ni `updated_by`.** Las columnas existen y RNF-08 pide
  trazabilidad; hoy se puede cambiar la estructura organizacional sin dejar autor.

## Decisiones que requiere el equipo

- [ ] **`created_by` / `updated_by`**: ¿se llenan desde la sesión en `CRUDBase`,
      o con triggers en la base? Lo segundo cubre también las escrituras
      manuales, que es donde más falta hacen.
- [ ] **Los `Update` no distinguen "no enviado" de "enviado como null".** Sobre
      una columna obligatoria eso intenta escribir null. ¿Se adopta un centinela
      o se aceptan `PATCH` parciales solo sobre columnas opcionales?
- [ ] **10 tablas siguen sin API.** Son las que dependen de decisiones abiertas
      de otros cambios (CRM, información documentada, sub-tenancy). ¿Se exponen
      al cerrar cada cambio, o se agrupan?
- [ ] **`user_permissions` existe sin API.** Depende de que se apruebe
      `sistema-actores-roles-rbac`.
