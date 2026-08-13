# Escrituras del frontend: qué llega a la base y qué no

**13-ago-2026.** Medido acción por acción sobre las funciones que mutan estado
en los 12 stores, cruzado con el contrato OpenAPI y con los mappers de lectura.

---

## El número

| | Acciones |
|---|---|
| Llegan a la base | **23** |
| Solo estado local | 14 |
| **Total** | **37** |

**62 % conectado.** Antes de esta tanda era 51 %.

| Store | Conectadas |
|---|---|
| `obligations` | 3 / 3 |
| `tenants` | 7 / 8 |
| `users` | 5 / 8 |
| `audits` | 2 / 4 |
| `support-tickets` | 2 / 4 |
| `departamentos` | 1 / 2 |
| `notifications` | 1 / 2 |
| `plan-accion` | 1 / 2 |
| `legal-matrix` | 1 / 3 |
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
| `audits` | Pide `/audits/nonconformities/` y **no mapea la respuesta**. Las no conformidades en pantalla salen de los datos de ejemplo, con ids que la API no conoce |
| `legal-matrix` | Arma cada norma con `articulos: []`. Los artículos que se ven son de ejemplo |
| `plan-accion` | Arma cada plan con `tareas: []` |

Mientras sigan así, **ninguna escritura sobre esas entidades puede funcionar**:
apuntaría a identificadores inventados.

---

## Las 14 que no llegan a la base

Ninguna es "falta de tiempo". Cada una tiene una causa concreta, y está escrita
también en el docstring de su función, que es donde la va a leer quien intente
arreglarla.

### Falta modelo o endpoint

| Acción | Causa |
|---|---|
| `users.updatePlants` | La relación usuario-planta no está expuesta; el mapper arma `plantIds: []` |
| `users.updatePermisos` | `user_permissions` existe como tabla, sin API. Depende de RBAC (0 de 33 tareas) |
| `users.updateDescriptorCargo` | `UserUpdate` no acepta ese campo |
| `support.setVisibilidad` | `SupportTicketUpdate` acepta `status`, `priority` y `assigned_to`. No hay visibilidad por ticket |
| `notifications.updatePreferences` | No hay tabla ni endpoint de preferencias por usuario. `rules` y `templates` son configuración de empresa |
| `plan-accion.toggleTarea` | Las tareas de un plan **no existen en el modelo** |
| `departamentos.updateTipo` | `ProcessUpdate` no expone `process_type`, que es justo lo que reclasifica esa pantalla |

### Falta un dato aguas arriba

| Acción | Causa |
|---|---|
| `legal-matrix.addNorm` | `POST /catalog/norms` exige `country_id` y `source_id`. **De países no hay ni endpoint de lectura** |
| `legal-matrix.updateArticulo` | El store nunca carga artículos reales |
| `audits.updateEtapas` | `NonconformityUpdate` acepta `improvement_stages`, pero el store descarta las NC de la API |
| `audits.updatePorques` | Igual, con `root_cause_answers` |
| `support.addCorreccion` | Depende de la misma cadena de no conformidades |
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

1. **Mapear las no conformidades desde la API.** Desbloquea cuatro acciones de
   una vez y es la entidad más usada del módulo de auditorías.
2. **Exponer `GET /catalog/countries`.** Veinte minutos, y desbloquea crear
   normas desde la interfaz.
3. **Cargar los artículos de la matriz de cumplimiento.** Es el corazón de la
   matriz legal: evaluar SI/NO/NA es lo que el módulo existe para hacer.
4. Lo demás depende de decisiones del equipo o de modelo nuevo.
