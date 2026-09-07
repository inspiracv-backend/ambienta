# Proposal: Comentarios con hilo y menciones sobre cualquier registro

Fuente: Análisis Funcional v1.8 §3.17, **RF-111** (comentarios con hilo sobre
cualquier registro) y **RF-112** (menciones a usuarios con notificación).
Issue #74, sub-tarea de la épica #31.

## El problema que nombró el cliente

La épica #31 lo dice con sus palabras: *«la información se maneja por correo y
se pierde, sobre todo la de normativas, RCAs e ISO»*.

Lo que se pierde no es el dato: es **la conversación sobre el dato**. Por qué se
evaluó así un artículo, quién dijo que la evidencia servía, qué se acordó
cuando el plazo se corrió. Eso hoy vive en la bandeja de alguien, y cuando esa
persona se va, se va con ella.

## Lo que hay hoy, medido el 7-sep-2026

**Nada.** Ni tabla, ni modelo, ni endpoint:

| Búsqueda | Resultado |
|---|---|
| Tablas con `comment` o `mention` en el nombre | **0** |
| Archivos de `apps/api/app` que los nombren | **0** |

Lo más parecido es `support_ticket_messages`, y **es otra cosa**: son los
mensajes de un ticket de soporte, con `author_guest_email` para quien escribe
sin cuenta y `is_internal` para lo que el cliente no ve. Generalizarla sería
mezclar una bandeja de atención con las notas internas sobre un registro de
cumplimiento — dos cosas con reglas de visibilidad opuestas.

## Lo que se propone

1. **`comments`, polimórfica**, con `entity_type` + `entity_id` — la misma
   forma que `entity_documents`, y **validada por el mismo mapa** que se
   escribió para RF-108. Una entidad nueva se vuelve comentable agregando una
   línea, no una tabla.
2. **Hilos de un solo nivel.** Una respuesta cuelga de un comentario raíz y no
   de otra respuesta.
3. **`comment_mentions`, normalizada.** Quién fue mencionado es una fila, no un
   `@` dentro del texto.
4. **La mención notifica**, reusando `notifications` — la cola que ya existe,
   con su deduplicación y su despachador.
5. **El hilo se ve en la ficha** de la obligación. Sin eso es otra tabla que
   nadie llama, que es el patrón que este repositorio repite.

## Las decisiones que este cambio toma, y por qué

### Un comentario exige una sesión identificada

Sin usuario responde **409**, no se atribuye al primer administrador de la
empresa. Es el mismo criterio que aprobar una revisión documental: dejar
escrito que alguien dijo algo que no dijo es peor que no tener el comentario, y
en un registro que se exporta a un auditor es exactamente lo que se lee.

### Una respuesta a una respuesta se rechaza, no se reacomoda

Aplanarla contra la raíz es lo que hacen las herramientas de chat, y acá sería
un error: **cambia a quién le está contestando el autor**. En una discusión
sobre si una evidencia sirve, colgar la respuesta del comentario equivocado
cambia el sentido de lo que quedó escrito. Se responde 422 diciendo cuál es la
raíz.

### Mencionar a alguien de otra empresa falla como si no existiera

Misma regla y mismo mensaje que el anclaje de RF-108: distinguir «no existe» de
«existe y es de otra empresa» convierte el campo en un oráculo para enumerar
usuarios ajenos.

### Editar deja marca; borrar no borra

`edited_at` se expone: un comentario editado después de que alguien lo
respondió cambia el registro, y quien lo lea tiene que poder saberlo. El
borrado es lógico, como todo en este sistema.

## Lo que NO entra

- **Parsear `@` del texto.** El cliente manda la lista de mencionados; el
  cuerpo es texto. Deducir a quién se menciona de una cadena falla con nombres
  compuestos y con dos personas del mismo nombre, y falla **en silencio**: la
  notificación simplemente no sale.
- **Adjuntos en el comentario.** Ya existe la capa de documentos y RF-108 los
  vincula al registro.
- **La línea de tiempo (#75) y el buscador (#76).** Son los otros dos de la
  épica y se apoyan en esta tabla; no se hacen acá.
- **Correo por mención.** Se encola la notificación in-app. El canal de correo
  usa la misma cola y es una línea, pero **avisar por correo de cada mención es
  una decisión de producto** —volumen y ruido— que nadie tomó todavía.
