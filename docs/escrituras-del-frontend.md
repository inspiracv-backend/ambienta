# Escrituras del frontend: qué llega a la base y qué no

**19-ago-2026.** Medido con un script que **se valida contra ocho casos
comprobados a mano antes de imprimir ningún total**: si no los reproduce, no
publica nada.

Esa guarda no es ceremonia. Las tres primeras versiones del medidor dieron tres
números distintos y los tres falsos — cortaban el cuerpo de la función en la
primera llave anidada, perdían la llamada partida en dos líneas (`api` y
`.post(...)`) por buscar la cadena literal `api.`, y confundían la llave de un
tipo de parámetro con la del cuerpo de la función. Un medidor que no se puede
verificar es peor que no medir, porque su número se cita después como si fuera
un hecho.

---

## El número

| | Acciones |
|---|---|
| Llegan a la base | **29** |
| Solo estado local | 10 |
| **Total** | **39** |

**74 % conectado.**

### Dos correcciones al conteo anterior, que decía 27 de 37

No es que se hayan conectado dos acciones más: **el conteo anterior estaba mal
por dentro**. Su encabezado decía 10 acciones sin conectar y su propia tabla
listaba 11.

- **`tenants.completarPerfilEmpresa` ya estaba conectada.** Figuraba bajo
  "Necesita una decisión" porque `TenantUpdate` no aceptaba `rut_tax_id`. Esa
  decisión se tomó y el campo se agregó —está documentado en el docstring de
  `TenantUpdate`— pero nadie volvió a la tabla. Hoy manda giro y RUT, revierte
  si la API responde 403 y avisa.
- **`legal-matrix` tiene 4 acciones, no 3.** Se contaba 3 de 3 y se declaraba
  "cerrada" mientras `addNorm` seguía sin conectar, en la misma página.

Es el mismo patrón que este documento ya describe en otro lado: un número que
se ve mejor de lo que está, y que nadie vuelve a medir porque se ve bien.

### Antes de esta tanda ya se había corregido otra sobreestimación

Se contaba "manda un `POST`" como "llega a la base". No es lo mismo, y la
diferencia no se ve leyendo el código:

- **`audits.addNonConformity`** mandaba `severity: 'alta'`, y la columna solo
  acepta `minor|major|critical`. Además omitía `code` y `title`, que son
  `NOT NULL`. La fila **nunca se insertaba**, y el `.catch(() => {})` se comía
  el error.
- **`audits.closeNonConformity`** cerraba con `PATCH {status:'closed'}`, pero
  la base exige `(status='closed') = (closed_at IS NOT NULL)`. Violaba el
  CHECK. Existe `/nonconformities/{id}/close`, que además rechaza el cierre si
  quedan planes de acción abiertos.

Una escritura que manda una petición que la base rechaza es indistinguible de
una que no manda nada — salvo que da más confianza, que es peor.

### Y `createTenant` engañaba de una tercera forma

El `POST` salía y la fila se creaba, así que cualquier medición la daba por
conectada. Pero el store insertaba la empresa en pantalla con un id inventado
—`tenant-${Date.now()}`— y **nunca lo reconciliaba con el que devolvía la API**.
La empresa recién creada apuntaba a una fila inexistente: cambiarle el plan o
agregarle una planta fallaba sin explicación. Y si la API rechazaba el alta,
`.catch(() => {})` la dejaba en la lista como si existiera hasta la próxima
recarga.

**Escribir bien no es solo que la petición salga.** Es que lo que queda en
pantalla corresponda a lo que quedó en la base.

| Store | Conectadas |
|---|---|
| `tenants` | **9 / 9** |
| `audits` | **4 / 4** |
| `obligations` | **3 / 3** |
| `users` | 5 / 8 |
| `legal-matrix` | 3 / 4 |
| `support-tickets` | 2 / 4 |
| `departamentos` | 1 / 2 |
| `notifications` | 1 / 2 |
| `plan-accion` | 1 / 2 |
| `gestores` | 0 / 1 |

---

## Lo que hay que entender antes de seguir conectando

**Una escritura no es un `PATCH`: es un viaje de ida y vuelta.** Es la lección
que costó tres estimaciones equivocadas, cada una más corta que la realidad.

Conectar un campo editable tiene dos lados, y hacer solo uno produce un engaño
distinto pero igual de malo:

| Lado que falta | Qué ve la persona |
|---|---|
| Escribir | La pantalla confirma un cambio que la base nunca recibió |
| Leer | La base guarda el cambio y la pantalla sigue mostrando el valor de siempre |

`tenants` estaba en el segundo caso sin que nadie lo notara: el mapper traía
`limiteUsuarios: 50` y `modulosActivos: []` **escritos a mano en el código**.
Escribirlos sin tocar la lectura habría dado un "guardado" que se deshace al
recargar.

### Tres stores piden datos y los descartan

Esto es lo que hace que la métrica de "stores que leen de la API" quede corta
como indicador:

| Store | Qué descarta |
|---|---|
| ~~`audits`~~ | **Resuelto.** El store mapea la respuesta de `/audits/nonconformities/`; las no conformidades en pantalla son las de la base |
| ~~`legal-matrix`~~ | **Resuelto.** Los artículos vienen de `/catalog/norms/{id}/articles` y su evaluación de `/compliance/article-compliance` |
| `plan-accion` | Arma cada plan con `tareas: []` |

Mientras sigan así, **ninguna escritura sobre esas entidades puede funcionar**:
apuntaría a identificadores inventados.

---

## Las 10 que no llegan a la base

Ninguna es "falta de tiempo". Cada una tiene una causa concreta, y está escrita
también en el docstring de su función, que es donde la va a leer quien intente
arreglarla.

### Falta modelo o endpoint

| Acción | Causa |
|---|---|
| `users.updatePlants` | **Desacuerdo de modelo.** El único vínculo es `user_roles.facility_id`, y su PK `(user_id, role_id)` admite **una** planta por rol. La pantalla modela `plantIds` en plural |
| `users.updatePermisos` | `user_permissions` existe como tabla. **El RBAC ya funciona en la API** —permiso efectivo, guarda derivada de la ruta, rol `servicio_lectura`— pero falta el endpoint que administre las excepciones por usuario, y la pantalla que lo consuma |
| `users.updateDescriptorCargo` | `UserUpdate` no acepta ese campo |
| `support.setVisibilidad` | `SupportTicketUpdate` acepta `status`, `priority` y `assigned_to`. No hay visibilidad por ticket |
| `notifications.updatePreferences` | No hay tabla ni endpoint de preferencias por usuario. `rules` y `templates` son configuración de empresa |
| `plan-accion.toggleTarea` | Las tareas de un plan **no existen en el modelo** |
| `departamentos.updateTipo` | `ProcessUpdate` no expone `process_type`, que es justo lo que reclasifica esa pantalla |

### Falta un dato aguas arriba

| Acción | Causa |
|---|---|
| `legal-matrix.addNorm` | **Decisión de diseño, no falta de endpoint.** `legal_norms` es catálogo global **sin `tenant_id`, a propósito**. Una RCA es de una empresa: escribirla ahí la publicaría a todos los tenants. Hay que decidir dónde vive la normativa propia |
| `support.addCorreccion` | Ya no está bloqueada por las no conformidades: ahora depende de que el ticket modele la corrección |
| `gestores.addContrato` | `client_tenant_id` sale de datos de ejemplo: la sub-tenancy no existe |

### Resueltas, que estaban listadas como pendientes

| Acción | Cómo se resolvió |
|---|---|
| ~~`tenants.completarPerfilEmpresa`~~ | **Ya está conectada.** La decisión —¿se vuelve editable el RUT?— se tomó: `TenantUpdate` lo acepta, y solo para el Admin Global. Manda giro y RUT, revierte si la API responde 403 y avisa. Seguía en esta tabla porque nadie volvió a mirarla |

---

## Cómo se comporta una escritura conectada

1. La pantalla muestra el cambio **de inmediato**, sin esperar confirmación.
2. Si la API lo rechaza, **vuelve al valor anterior y lo dice**.
3. Cuando la acción escribe varios registros, se revierten **solo los que
   fallaron**: si de diez se guardaron ocho, decir que no se guardó ninguno
   sería falso.

El mensaje sale del cuerpo que devuelve la API. `detail` llega en dos formas
—una cadena cuando rechaza un router, una **lista por campo** cuando rechaza la
validación— y leer solo la primera dejaba los 422 mostrando `[object Object]`.

### `settings` es un cajón compartido

Tres campos de empresa —límite de usuarios, módulos activos y logo— no tienen
columna propia y viven en `settings`, el jsonb del tenant. Se escribe
**fusionando, nunca reemplazando**: mandar el objeto entero desde una pantalla
borraría lo que escribieron las otras, y el destrozo solo se vería al recargar
una tercera.

Es una solución de transición. Un jsonb sin esquema declarado no se puede
validar; cuando alguno de esos campos se estabilice, merece columna propia.

---

## Lo que sigue, en orden de lo que más desbloquea

1. ~~**Mapear las no conformidades desde la API.**~~ **Hecho.** Desbloqueó
   `updateEtapas` y `updatePorques`, y destapó que el alta y el cierre nunca
   habían funcionado.
2. ~~**Exponer `GET /catalog/countries`.**~~ **Hecho** (PR #171). Falta que el
   formulario de alta de normas lo consuma.
3. ~~**Cruzar el articulado con `article_compliance`.**~~ **Hecho.** Evaluar
   crea la fila si no existe y la edita si ya está.
4. ~~**Excluir un artículo del porcentaje** (RF-24).~~ **Hecho.** Vive en
   `article_compliance.attributes`, con esquema declarado en `packages/shared`.
   Queda `addNorm`: la matriz legal está en **3 de 4**, no cerrada como decía
   antes esta línea.
5. ~~**El perfil normativo de la empresa.**~~ **Hecho.** El alta pide sector
   CIIU y tramo, y `updatePerfilNormativo` deja declararlos en una empresa ya
   creada. Sin esa segunda acción toda empresa anterior quedaba en `sin_perfil`
   para siempre: el sistema decía correctamente que faltaba el dato y no
   ofrecía ningún camino para completarlo.
6. **Las tareas del plan de acción** necesitan modelo propio: es migración,
   endpoints y pantalla. Ya está decidido que van como entidad, no como lista
   dentro del plan.
7. Lo demás depende de decisiones del equipo o de modelo nuevo.

---

## Cómo se volvió a medir

El script vive en el scratchpad, no en el repo, porque **lo que importa no es la
herramienta sino la disciplina**: cuenta las acciones declaradas en cada
`ContextValue`, delimita el cuerpo de cada una contando llaves, y sigue **un
nivel de delegación** —`setIncluidoEnCalculo` no llama a la API: llama a
`guardarInclusion`, que sí—.

Antes de imprimir cualquier total comprueba ocho acciones cuyo estado real está
verificado leyendo el código. Si falla una sola, no publica nada. Las tres
versiones anteriores del script habrían pasado ese filtro en cero casos, y las
tres estaban a punto de escribir un número en este documento.
