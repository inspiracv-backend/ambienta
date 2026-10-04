# Proposal: La línea de tiempo de un registro, con datos de verdad

Fuente: Análisis Funcional v1.8 §3.17, **RF-113** — *«Línea de tiempo por
registro: comentarios + audit log + adjuntos + correos»*. Issue #75, sub-tarea
de la épica #31.

## Lo que hay hoy, medido el 7-sep-2026

**El componente existe y no tiene qué mostrar.** Es importante decirlo así y no
«falta la línea de tiempo», porque el trabajo es otro:

| pieza | estado |
|---|---|
| `HistorialTimeline` | **Existe**, montado en 5 pantallas de detalle |
| `audit-log-store` | **Nunca le pregunta a la API.** Sólo lo de esta sesión del navegador |
| `GET /system/audit-log` | Existe, **cero llamadores** |
| Filas en `audit_log` | **9.575**, invisibles |

El propio store lo dice en un comentario: *«Conectarlo es trabajo aparte: hay
que mapear la forma de la API a `AuditLogEntry`»*. Eso es este cambio.

Y hay que reconocerle algo: hasta #208 el store arrancaba con `mockAuditLog`,
o sea mostrando **un registro de auditoría inventado**. Quedó vacío a propósito,
porque vacío dice la verdad. Este cambio lo llena con la verdad.

## Tres vocabularios para la misma cosa

Al medirlo aparece el problema real, y es el que haría que una unión ingenua
mostrara **cero eventos**:

| dónde | cómo se llama una obligación |
|---|---|
| `audit_log.entity_type` | `obligations` — el nombre de la **tabla** |
| `comments` / `entity_documents` | `obligation` — el nombre de **dominio** |
| `packages/shared` (`EntidadAuditable`) | `obligacion` — en **español** |

No se inventa un cuarto. El de dominio manda —es el que ya validan `ANCLAJES` y
RF-108— y la traducción hacia el nombre de tabla **se deriva del modelo**
(`Anclaje.modelo.__tablename__`), no de una lista nueva que mantener.

## Lo que se propone

`GET /historial?entity_type=&entity_id=` que **une en el servidor** las tres
fuentes que existen, ordenadas del evento más reciente al más antiguo:

1. **El registro de actividades** (`audit_log`), que es RNF-08/RNF-25. La línea
   de tiempo lo **muestra**, no lo reemplaza: la épica #31 lo dice explícito.
2. **Los comentarios** (RF-111, recién construidos).
3. **Los adjuntos** (`entity_documents`, RF-108).

Unir en el servidor y no en el navegador porque el orden cronológico entre
fuentes distintas se decide una vez, y porque la traducción de vocabulario es
del lado que conoce los modelos.

## Los correos NO entran, y la respuesta lo dice

RF-113 nombra cuatro fuentes y **la captura de correos no existe**: es RF-107,
issue #72, sin construir.

Mostrar tres y callarse la cuarta dejaría una línea de tiempo que **se ve
completa**, y alguien concluiría que sobre ese registro no hubo correos cuando
lo que pasa es que el sistema todavía no los mira. En un módulo cuya razón de
ser es *«la información se maneja por correo y se pierde»*, esa omisión sería
exactamente el error que viene a arreglar.

Por eso la respuesta declara qué fuentes la componen y cuáles faltan, y la
pantalla lo muestra.

## Lo que NO entra

- **Conectar `GET /system/audit-log`** a la vista global de auditoría. Es otra
  pantalla y otro problema (paginar 9.575 filas); acá se lee por entidad.
- **El buscador transversal (#76).** Es el que queda de la épica.
- **Escribir en el audit log desde acá.** Se escribe solo, en `before_flush`.
