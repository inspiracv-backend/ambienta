# Design: comentarios y menciones

## La tabla es polimórfica, y reusa el mapa de RF-108

`comments` guarda `entity_type` + `entity_id`, igual que `entity_documents`, y
la comprobación es **la misma función**: `vinculos_de_documentos.ANCLAJES`.

Eso no es ahorro de código, es lo que evita que las dos listas se separen. Con
dos mapas, una entidad comentable y no vinculable —o al revés— sería un estado
que nadie eligió y que sólo se descubre usando el sistema. Una prueba ya exige
que ese mapa coincida con el CHECK de la base; ahora sostiene las dos tablas.

**Consecuencia buscada:** un `entity_type` que no esté en el mapa no se puede
comentar, y el mensaje lo dice.

## El hilo es de un nivel, y se rechaza el segundo

`parent_id` apunta a un comentario de la misma entidad. Si ese padre ya tiene
padre, se responde **422 diciendo cuál es la raíz**.

La alternativa —aplanar contra la raíz, como hace un chat— parece amable y
cambia el registro: en una discusión sobre si una evidencia sirve, una
respuesta colgada del comentario equivocado le atribuye al autor que le estaba
contestando a otra persona. El cliente sabe qué hacer con un 422 que le dice la
raíz; no sabe que su respuesta se movió.

Un CHECK no puede exigirlo —Postgres no mira la fila del padre en un CHECK— así
que lo exige el servicio, y hay una prueba que lo rompe a propósito.

## Las menciones son filas, no texto

`comment_mentions(comment_id, user_id)`, única por par.

Buscar `@` en el cuerpo sería más corto y fallaría en silencio: un nombre
compuesto se corta por el espacio, dos personas del mismo nombre son
indistinguibles, y el resultado de equivocarse es que **la notificación no
sale** — sin ningún error. El cliente manda la lista; el cuerpo es texto y se
guarda tal cual.

Cada usuario mencionado se comprueba con la sesión del tenant. Un usuario de
otra empresa falla **igual que uno inexistente**: mismo código, mismo mensaje.

## La notificación va por la cola que ya existe

`notifications`, con `dedupe_key = f"mencion:{comment_id}:{user_id}"` y
`channel="in_app"`.

Dos razones para no inventar un canal propio: la fila del aviso y el hecho que
lo causa se escriben **en la misma transacción**, así que no pueden discrepar;
y el despachador, los reintentos y la lectura ya están construidos y probados.

**Sólo in-app.** El correo usa la misma cola y sería una línea más, pero
mandar un correo por cada mención es una decisión de producto —volumen, ruido,
gente que deja de leerlos— y nadie la tomó. Encolar los dos canales «por si
acaso» es cómo se llega a que el cliente pida apagar la funcionalidad entera.

**Nadie se notifica a sí mismo.** Mencionarse en el propio comentario es
frecuente al escribir («me lo llevo yo») y una notificación por eso entrena a
ignorarlas.

## El autor es obligatorio

`author_user_id` es `NOT NULL`, y sin sesión identificada el endpoint responde
**409**. No se toma al primer administrador: eso dejaría escrito que esa
persona dijo algo que no dijo.

El costo es que en el modo `X-Tenant-Id` —sin Clerk— no se puede comentar. Es
el mismo costo que ya paga aprobar una revisión documental, y las pruebas
resuelven el camino con `dependency_overrides[get_current_user]`, que simula
**de dónde sale la identidad** y deja correr la guarda entera.

## Editar y borrar

- `edited_at` nulo hasta la primera edición, y **se expone**: un comentario
  editado después de que alguien lo respondió cambia lo que quedó escrito.
- El borrado es lógico (`deleted_at`), como todo el sistema. Un hilo con la
  raíz borrada **conserva sus respuestas**: destruirlas borraría la respuesta de
  otras personas por decisión de una sola.

## RLS y GRANT en la migración

Las dos tablas nacen en `db/28`, así que **no heredan** el bucle de políticas ni
el `GRANT ON ALL TABLES` de `01_schema`: los declaran ellas. Es la trampa que
CLAUDE.md documenta y que dejaría las dos tablas visibles entre empresas.

`comment_mentions` **también lleva `tenant_id`**, aunque se pueda derivar del
comentario. Sin la columna no hay política de RLS que escribir sobre ella, y una
tabla sin política en un sistema donde RLS es la única barrera no es una
optimización: es un agujero.
