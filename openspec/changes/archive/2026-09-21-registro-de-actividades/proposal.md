# Proposal: El registro de actividades, visible y completo

Decisiones 9 y 10 del 21-sep-2026 (`docs/plan-de-cierre-v1.md`, §6).

## Lo que hay hoy, medido

| pieza | estado |
|---|---|
| `audit_log` | Se escribe solo desde el 24-ago (observador del `flush`). **Más de 41.000 filas** en la base de desarrollo |
| `GET /system/audit-log` | Desde el 21-sep exige `audit_log.read`, va del más reciente al más antiguo y niega a quien está acotado a una planta. **Ningún llamador** |
| Pantalla `/historial` | Lee `audit-log-store`, que **no le pregunta nada a la API**: muestra solo lo de la sesión y se vacía al recargar |
| Emisión de PDF y CSV | Se anota en ese mismo store de sesión. **No queda nada en el servidor** |

O sea: el sistema guarda la trazabilidad que exigen RNF-08 y RNF-25 y **nadie la
puede ver**; y lo que sale del sistema hacia una auditoría externa —el caso de
RNF-26— no deja rastro.

## Lo que se propone

1. **`POST /emisiones`**: anota en `audit_log` que alguien emitió un documento
   (informe de auditoría, matriz de aspectos, reportes), con qué filtros y
   cuántas filas. Acción `download`, que el CHECK ya admite.
2. **La pantalla del registro lee la API**: los eventos más recientes, con los
   filtros que ya tiene, y el aviso de que hay más si la página vino cortada.
3. **Filtro por fechas en el servidor**: `desde` y `hasta` en días de
   calendario de la empresa, para poder consultar un período que no está entre
   los últimos eventos.

## Lo que exige del resto del sistema

| Pieza | Qué cambia |
|---|---|
| `routers/emisiones.py` | Nuevo, con `report.generate` |
| `routers/system.py` | `desde`, `hasta` y el nombre de quien actuó |
| `permisos_de_rutas.py` | La raíz `emisiones` |
| `deps.py` | Anotar una emisión no es escribir datos de la empresa: una suspendida puede exportar, y queda anotado |
| `packages/shared` | Tipos de entidad que faltaban, y `otro` como respaldo |
| Web | `audit-log-store` lee la API; tres pantallas anotan sus emisiones |

## Lo que NO entra

- **Filtros por entidad y por persona en el servidor.** Se aplican sobre la
  página cargada; si esta vino cortada, la pantalla lo dice.
- **Saber si la impresión se completó.** El navegador no avisa si se cancela:
  se anota que se abrió.

## Preguntas abiertas

1. ¿El registro debe poder exportarse entero para un fiscalizador (RNF-26), o
   basta con lo filtrado en pantalla?
2. ¿Cuánto tiempo se conserva el registro? Hoy no se borra nunca.
