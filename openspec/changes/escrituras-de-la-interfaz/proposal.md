# Proposal: Escrituras de la interfaz

Fuentes: los 12 stores de `apps/web/lib/` · contrato OpenAPI en ejecución · `docs/estado-crud-base-de-datos.md`.

## Why

Las lecturas del frontend están conectadas: 10 de 12 stores traen datos reales.
Las escrituras no. Medido acción por acción sobre las funciones que mutan
estado:

| | Acciones |
|---|---|
| Llegan a la base | **19** |
| Solo estado local | **18** |
| **Total** | **37** |

En la práctica eso significa que en la mitad de las pantallas alguien edita
algo, **lo ve cambiar, y desaparece al recargar**. No hay error, no hay aviso.
Es la peor forma de fallar: la interfaz afirma que guardó.

### Lo que apareció al medirlo

La suposición de que "conectar una escritura es agregar un `PATCH`" resultó
falsa, y por eso las estimaciones anteriores se quedaron cortas dos veces.

**El mapper de lectura inventa varios de los campos editables.** `tenants` lee
`limiteUsuarios: 50` y `modulosActivos: []` **escritos a mano en el código**, no
de la API. Conectar solo la escritura daría un "guardado" que al recargar vuelve
a 50 — cambiaríamos un engaño por otro.

Conectar un campo es hacer que **dé la vuelta completa**: escribir donde
corresponde y leer de ahí mismo.

## What Changes

1. **Siete acciones pasan a persistir**, cada una con su lado de lectura.
2. **Una escritura que falla revierte lo mostrado y lo dice**, en vez de dejar la
   pantalla mintiendo.
3. **Las que no se pueden conectar quedan documentadas** en su propio código, con
   la causa, para que nadie las lea como olvido ni las intente de nuevo.

## Qué exige del resto del sistema

| Área | Qué necesita | Estado |
|---|---|---|
| `apps/web/lib/api-client.ts` | Mensaje legible desde el error de la API | Hecho |
| `apps/web/lib/toast-store.tsx` | Superficie para avisar del fallo | Ya existía |
| Mapper de `tenants` | Leer de `settings` en vez de valores fijos | **Este cambio** |
| Mapper de `audits` | Leer las etapas de mejora y los porqués | **Este cambio** |
| Mapper de `support` | Leer la visibilidad del mensaje | **Este cambio** |
| API | `rut_tax_id` editable, para completar el Perfil Empresa | **No existe** |
| API | Dónde guardar las tareas de un plan de acción | **No existe** |

## Lo que este cambio no hace

- **No conecta las nueve restantes.** Cada una necesita algo que no existe:
  una decisión del equipo, un campo que la API no acepta, o datos aguas arriba.
- **No agrega paginación** a los listados, que es un problema aparte y más grande.
- **No toca las 13 pantallas que todavía importan datos de ejemplo directo**, sin
  pasar por un store.

## Decisiones que requiere el equipo

- [ ] **`completarPerfilEmpresa` no se puede guardar**: el Perfil Empresa se
      considera completo cuando hay giro y RUT, y la API **no acepta editar el
      RUT**. ¿Se expone, o el perfil se completa por otro camino?
- [ ] **Las tareas de un plan de acción no tienen dónde vivir.** ¿Entran como
      modelo propio, o como lista dentro del plan?
- [ ] **`settings` es un jsonb sin forma declarada.** Si tres pantallas escriben
      claves distintas ahí, nadie sabrá qué contiene. ¿Se le fija un esquema?
- [ ] **Escritura optimista o pesimista.** Este cambio adopta la optimista con
      reversión, que es lo que ya hacían los stores conectados. Con conexiones
      lentas el parpadeo se nota.
