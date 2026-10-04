# Design: El registro de actividades, visible y completo

## 1. La emisión de un documento

`POST /emisiones` con `{documento, titulo, formato, filas?, filtros?,
entidad_tipo?, entidad_id?}`.

- **Acción `download`**, que el CHECK de `audit_log` ya admite y que el
  vocabulario del frontend ya traducía desde `exportado`. Ampliar el CHECK con
  un verbo nuevo sería una migración para decir lo mismo.
- **`documento` es una lista cerrada** (`informe_de_auditoria`,
  `matriz_de_aspectos`, `reporte`): un valor libre haría imposible filtrar.
- **Si nombra un registro, tiene que ser visible** (`validar_visible`). El
  informe de auditoría se anota contra su auditoría y aparece en el historial
  de esa ficha; una emisión contra un id ajeno sería la fuga que el repositorio
  ya conoce.
- **Se escribe con `services/auditoria.registrar`**, no por la ORM: el
  observador ignora `audit_log` a propósito.
- **Permiso `report.generate`.** Quien no puede generar reportes no los emite.
- **Una empresa suspendida puede exportar, y queda anotado.** La regla de solo
  lectura protege los datos de la empresa; anotar que se sacó una copia es
  trazabilidad, no un dato. Se exceptúa por raíz, en un solo lugar.
- Se anota **"abrió la impresión"**: el navegador no avisa si se cancela.

## 2. La pantalla

`audit-log-store` pide `GET /system/audit-log?limit=500` con la empresa de la
sesión y traduce cada fila a `AuditLogEntry`:

| de la API | a la pantalla |
|---|---|
| `entity_type` (nombre de tabla) | `entidadTipo` por una tabla de traducción; lo que no conoce va a `otro` con la tabla en la etiqueta |
| `action` | `accion`: `create`→`creado`, `update`→`actualizado`, `delete`→`eliminado`, `download`→`exportado`, `approve`→`estado_cambiado` |
| `before_data`/`after_data` | `cambios`, campo por campo |
| `actor_user_id` + `actor_nombre` | `actorId`, `actorNombre`; sin actor, "Sistema" |

**`otro` en vez de esconder.** El enum de `packages/shared` tenía catorce tipos
y la base audita más de cuarenta tablas. Un evento sin tipo reconocido que no
se muestra es exactamente lo que un registro de auditoría no puede hacer.

**El nombre de quien actuó lo pone el servidor**, con un `LEFT JOIN` a `users`
bajo RLS: la persona de otra empresa —un gestor— no se ve y queda "de otra
empresa". Resolverlo en el navegador obligaría a tener cargada la lista de
usuarios, que no siempre está.

**Lo de la sesión se conserva.** Lo que la pantalla anota en el momento sigue
entrando al store; al recargar se ve lo del servidor.

## 3. Las fechas

`desde` y `hasta` son **días de calendario de la empresa** (`husos.py`), no
instantes: "eventos del 3 de septiembre" es un día en Chile. `hasta` incluye el
día entero.
