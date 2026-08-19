# Escrituras del frontend: qué llega a la base y qué no

**13-ago-2026.** Medido acción por acción sobre las funciones que mutan estado
en los 12 stores, cruzado con el contrato OpenAPI y con los mappers de lectura.

---

## El número

| | Acciones |
|---|---|
| Llegan a la base | **27** |
| Solo estado local | 10 |
| **Total** | **37** |

**73 % conectado.** Antes de esta tanda era 62 % — pero ese 62 % estaba
inflado.

### Dos de las que se contaban como conectadas no llegaban

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

**El número real antes de esta tanda era 21 de 37, no 23.** Una escritura que
manda una petición que la base rechaza es indistinguible de una que no manda
nada — salvo que da más confianza, que es peor.

| Store | Conectadas |
|---|---|
| `obligations` | 3 / 3 |
| `tenants` | 7 / 8 |
| `users` | 5 / 8 |
| `audits` | **4 / 4** |
| `support-tickets` | 2 / 4 |
| `departamentos` | 1 / 2 |
| `notifications` | 1 / 2 |
| `plan-accion` | 1 / 2 |
| `legal-matrix` | **3 / 3** |
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
| `users.updatePermisos` | `user_permissions` existe como tabla, sin API. Depende de RBAC (0 de 33 tareas) |
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

### Necesita una decisión

| Acción | Decisión pendiente |
|---|---|
| `tenants.completarPerfilEmpresa` | El perfil se considera completo con giro **y RUT**, y `TenantUpdate` no acepta `rut_tax_id`. ¿Se vuelve editable, o el perfil se completa por otro camino? |

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
   **La matriz legal quedó cerrada: 3 de 3.**
5. **Las tareas del plan de acción** necesitan modelo propio: es migración,
   endpoints y pantalla. Ya está decidido que van como entidad, no como lista
   dentro del plan.
6. Lo demás depende de decisiones del equipo o de modelo nuevo.
