# Conectar el AI Service a Ambienta

**Para quien construye el asistente. Escrito el 8-sep-2026 contra el sistema
corriendo, no contra la documentación.**

Todo lo que dice este documento se puede comprobar: cada endpoint existe hoy en
`apps/api/app/routers/`, cada número se midió contra la base, y donde no hay
nada lo digo en vez de dejarlo implícito.

- **Contrato completo, legible por máquina:** [`openapi.json`](openapi.json) —
  regenerado hoy. 172 rutas, 319 operaciones.
- **Swagger navegable:** `http://localhost:8000/docs` con el sistema levantado.
- **Ejemplos de respuesta:** [`ejemplos-de-respuesta.json`](ejemplos-de-respuesta.json).

> El `openapi.json` que estaba en esta carpeta era del **20-ago** y le faltaban
> **63 rutas**, entre ellas `/buscar`, `/historial`, `/comentarios`, las
> versiones de una norma y el enlace de descarga de documentos. Si trabajaste
> con ese archivo, varias de las conclusiones del informe salen de ahí.

---

## 0. Tres cosas del informe que no son así

Las pongo primero porque cambian qué hay que construir.

### 0.1 El catálogo de la BCN **sí está poblado**

El informe asume un catálogo vacío o de ejemplo. Medido hoy contra la base:

| | |
|---|---|
| Normas públicas | **24** |
| De ellas, con identificador de la BCN | **23** |
| Versiones de texto legal | **26** |
| Artículos | **689** (largo medio: 1.221 caracteres) |
| Normas con más de una versión | **3** |

La Ley 19.300 está completa, con sus 153 partes y su versión vigente de
2024-04-10. La sincronización real corre desde el **26-ago**; antes de esa fecha
el catálogo sí eran 8 normas de ejemplo, y ahí es donde probablemente miraste.

**Consecuencia para ti:** no hace falta que el AI Service cargue normativa. Ya
hay de dónde citar. Lo que sí falta es *decidir qué más traer* — la BCN tiene
748.000 normas y la mayoría son nombramientos y concesiones de acuicultura (§9).

### 0.2 La búsqueda **no cubre el texto de los artículos**

`GET /buscar` busca en **títulos y códigos**, no en el cuerpo de los artículos.
Está en `app/services/buscador.py`: para las normas mira `title` y
`norm_number`, y nada más.

Y acá hay algo que te sirve: el índice para buscar dentro del articulado **ya
existe en la base y ningún endpoint lo usa**.

```sql
-- db/01_schema.sql:1429
CREATE INDEX ix_articles_fts ON legal_articles USING gin (to_tsvector('spanish', content));
```

O sea que si necesitás búsqueda semántica o full-text sobre los 689 artículos,
la mitad cara del trabajo está hecha. Es un endpoint nuevo, chico. Ver §8.

### 0.3 El enlace firmado de descarga **ya existe**

El informe propone crear `GET /documents/{id}/versions/{version_id}/download`.
Ya está, con otro nombre y devolviendo más:

```
GET /api/v1/documents/{document_id}/versions/{version_id}/download-url
```

```json
{
  "url": "https://s3.us-west-004.backblazeb2.com/...&X-Amz-Signature=...",
  "expires_in": 300,
  "checksum_sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
}
```

El `checksum` viaja **en la misma respuesta** y no en otra llamada: entre dos
peticiones alguien puede publicar una revisión nueva, y validarías el archivo
contra el hash de otro texto.

**Sin credenciales de almacenamiento configuradas responde 503 con un mensaje
claro**, no un 500 ni una URL rota. Hoy hay **0 documentos** cargados en el
sistema, así que este endpoint no lo vas a poder ejercitar hasta que se suba
alguno (§9.3).

---

## 1. La secuencia mínima que funciona

Cinco llamadas. Si estas cinco te responden, estás conectado.

```bash
BASE=http://localhost:8000/api/v1
TOKEN="<JWT de Clerk>"       # ver §2

# 1. Quién soy, de qué empresa, y qué puedo hacer
curl -H "Authorization: Bearer $TOKEN" $BASE/me

# 2. Qué normativa hay para citar
curl -H "Authorization: Bearer $TOKEN" "$BASE/catalog/norms?limit=50"

# 3. El articulado vigente de una norma
curl -H "Authorization: Bearer $TOKEN" "$BASE/catalog/norms/$NORM_ID/articles"

# 4. Abrir una conversación
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"user_id":"'$USER_ID'","title":"Consulta sobre EIA","scope":"tenant"}' \
  $BASE/support/chatbot

# 5. Guardar la respuesta CON sus citas
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
        "conversation_id":"'$CONV_ID'",
        "role":"assistant",
        "content":"El titular debe presentar un EIA.",
        "citations":[{"norma":"Ley 19.300","articulo":"11","texto":"..."}],
        "cited_norm_ids":["'$NORM_ID'"],
        "model_name":"claude-opus-5",
        "token_usage":{"input":1200,"output":340}
      }' \
  $BASE/support/chatbot/$CONV_ID/messages
```

El `user_id` del paso 4 es el **UUID interno** de Ambienta, no el id de Clerk.
Lo devuelve `/me` (§5.1). Es la confusión más común: el JWT lleva el id de
Clerk (`user_xxx`) y el resto de la API usa el UUID.

---

## 2. Autenticación

**La API no emite tokens propios: valida los de Clerk.** No hay API keys.

### 2.1 Los dos modos, y sólo uno está activo a la vez

| Modo | Cuándo | Cómo se identifica |
|---|---|---|
| **Producción** | `CLERK_JWKS_URL` está puesta | `Authorization: Bearer <JWT>` — el header `X-Tenant-Id` se **ignora por completo** |
| **Desarrollo** | esa variable no está | `X-Tenant-Id: <uuid de la empresa>` |

Lo gobierna una sola variable, y es la misma que hace falta para validar
tokens: no es un flag que alguien pueda dejar apagado por descuido.

**En modo desarrollo no hay usuario.** `/me` devuelve la empresa y `usuario` en
`null`, con `modo_desarrollo: true`. Sirve para probar lecturas; **no sirve para
guardar conversaciones**, porque un mensaje necesita un autor.

De dónde sale el `tenant_id`: del claim del JWT, que Clerk toma de
`publicMetadata`. Si esa metadata no está, la persona entra y recibe **403 en
todo**. Es el error más común al dar de alta una cuenta nueva.

### 2.2 La cuenta de servicio ya está preparada

Existe un rol `servicio_lectura` en **todas** las empresas, con los 15 permisos
`.read` y ninguno más, y un script para crear el usuario:

```bash
docker compose exec -T postgres psql -U ambienta -d ambienta \
  -v correo="'ia@ejemplo.cl'" \
  -v nombre="'Servicio IA'" \
  -v clerk="'user_XXXXXXXXXXXX'" \
  -v empresa="'<uuid de la empresa>'" \
  -f db/scripts/crear_usuario_de_servicio.sql
```

El script documenta los pasos previos en Clerk (allowlist, primer ingreso,
`publicMetadata`). Tres cosas que importan:

- **Ve una empresa, no todas.** `roles.tenant_id` es `NOT NULL` y RLS acota
  cada consulta. Si el AI Service tiene que atender a varias empresas, necesita
  **un usuario por empresa** — y eso es la respuesta correcta, no un atajo: una
  cuenta de sólo lectura que cruzara empresas sería peor que una de escritura
  que respeta el aislamiento, porque leería todo.
- **`email` es único global.** Dos empresas no pueden compartir la dirección, y
  las subdirecciones (`ia+andes@`) están bloqueadas en Clerk. Hacen falta
  correos distintos de verdad.
- **No incluye `chatbot.use`**, que es lo que hace falta para escribir mensajes.
  Deliberado: guardar la conversación debería hacerse con la sesión de **la
  persona que conversa**, no con la cuenta de servicio — el registro de
  auditoría necesita un responsable con nombre, y "el servicio" no lo es. Si el
  diseño resulta ser otro, es una decisión a tomar (§9.1), no un permiso a
  agregar sin pensarlo.

### 2.3 Las credenciales no van por chat ni por correo

Ni las de Clerk, ni el `.env`. El repositorio es **público**: nada de esto entra
acá. Coordinar el canal con Fabrizzio.

---

## 3. Reglas que valen para todos los endpoints

### 3.1 Prefijo y versión

Todo cuelga de `/api/v1`. La API se llama `Ambienta API 0.1.0`.

### 3.2 Paginación: `skip`, `limit` y **dos cabeceras**

29 endpoints de listado aceptan `skip` y `limit`.

- `limit` por defecto **100**, máximo **500**. Pedir más responde **422**, no se
  recorta en silencio.
- Cada respuesta trae:

```
X-Has-More: true|false
X-Page-Limit: 100
```

**`X-Has-More` es la que importa para indexar.** El cuerpo es un arreglo pelado;
sin esa cabecera, una respuesta de 100 filas de 340 se ve exactamente igual que
una de 100 de 100. Va **siempre**, también cuando no hay más: una cabecera que
sólo aparece cuando falta algo obliga a distinguir "no hay más" de "esta versión
del servidor no lo dice".

### 3.3 Sincronización incremental: `updated_since`

`/catalog/norms` y `/documents/` aceptan `updated_since` (ISO 8601). Devuelven
lo modificado **después** de esa marca, con `>` estricto.

**Guardá el `updated_at` máximo que viste, no la hora en que corriste.** Cada
registro trae su `updated_at` justamente para eso. Un cliente con el reloj
adelantado que guardara *su* hora se saltaría filas, y no habría cómo notarlo.

### 3.4 Errores

Siempre `{"detail": "..."}`.

| Código | Qué significa acá |
|---|---|
| **401** | falta el token, o falta `X-Tenant-Id` en modo desarrollo |
| **403** | el token es válido pero falta el permiso. El mensaje dice **cuál**: `Falta el permiso obligation.read.` |
| **404** | no existe, o no es de esta empresa — **no se distinguen a propósito** |
| **409** | el cuerpo está bien y la operación es legítima, pero el recurso está en un estado que no la admite |
| **422** | el cuerpo está mal, o un id del cuerpo no es de esta empresa |
| **503** | almacenamiento sin configurar (sólo en subida/descarga de archivos) |

**404 y 422 no distinguen "no existe" de "es de otra empresa", y es
deliberado**: distinguirlos convertiría el endpoint en un oráculo para enumerar
identificadores ajenos.

### 3.5 Reintentos

- **5xx**: reintentar con backoff.
- **4xx**: no reintentar nunca. Un 403 no se arregla insistiendo.
- **429**: no hay límite de tasa en los endpoints de negocio hoy. Sólo las dos
  rutas públicas de acceso invitado lo tienen, y no las vas a usar.

### 3.6 El aislamiento entre empresas es de PostgreSQL, no de la API

Vale la pena saberlo porque explica varios comportamientos: **Row Level Security
es la única barrera**. La API se conecta con un rol que no puede saltársela. La
consecuencia práctica para vos: **una consulta mal armada devuelve cero filas,
no las de todas las empresas**. Falla cerrado y en silencio.

Si un listado te vuelve vacío y esperabas datos, la causa más probable es que el
`tenant_id` de la sesión no es el que creés.

---

## 4. Leer normativa

### 4.1 El catálogo

```
GET /api/v1/catalog/norms?buscar=&tipo=&updated_since=&skip=&limit=
```

`buscar` filtra por título o número, sin distinguir mayúsculas. Orden estable:
tipo, número, id.

Campos de `LegalNormRead`:

```
id · country_id · source_id · external_norm_id · norm_type · norm_number
title · issuing_body · publication_date · promulgation_date · effective_from
repeal_date · status · official_url · subjects[] · last_source_sync_at
created_at · updated_at
```

`external_norm_id` es el identificador en la BCN — el que permite volver a la
fuente oficial. `official_url` es el enlace a Ley Chile.

### 4.2 Las versiones de una norma

```
GET /api/v1/catalog/norms/{norm_id}/versions
```

De la más reciente a la más antigua. **Esta ruta es nueva** (no estaba en el
`openapi.json` que tenías) y contesta la pregunta que hace una auditoría: *con
qué texto se evaluó el cumplimiento en un periodo ya cerrado*.

Dos filos:

- **`valid_to: null` significa "todavía rige"**, no "no rige". Leído al revés,
  cualquier filtro devuelve cero justo para la versión vigente, que es la más
  consultada.
- **La BCN marca más de una versión como vigente a la vez.** Ya pasó con la Ley
  19.300 (la de 1994 y la de 2010). Usá `is_current` para saber cuál rige hoy;
  si tenés que desempatar por fechas, la que empezó después.

### 4.3 El articulado — **y el de una fecha dada**

```
GET /api/v1/catalog/norms/{norm_id}/articles
GET /api/v1/catalog/norms/{norm_id}/articles?vigente_el=2023-06-30
```

Sin `vigente_el` devuelve el texto vigente hoy. Con él, el que regía esa fecha.

Campos de `LegalArticleRead`:

```
id · norm_version_id · parent_article_id · external_article_id · article_type
article_number · heading · content · display_order · effective_from
effective_to · created_at · updated_at
```

`content` es el texto completo del artículo. `display_order` da el orden de
lectura. `parent_article_id` arma la jerarquía (título → capítulo → artículo).

**Una norma sin texto para esa fecha devuelve `[]`, no 404**: la norma existe y
la respuesta correcta es "no había texto vigente entonces".

### 4.4 Normativa propia de la empresa (RCA, ISO)

```
GET  /api/v1/compliance/normativa-propia/
POST /api/v1/compliance/normativa-propia/
POST /api/v1/compliance/normativa-propia/{norma_id}/articulos
```

Una RCA es normativa **de una empresa**, no del catálogo público: sus
condiciones obligan a ese titular y a nadie más. Viven en las mismas tablas con
`tenant_id` no nulo, y RLS las separa.

**Para el asistente esto importa mucho:** una respuesta sobre "qué me exige mi
RCA" sale de acá, no de la BCN, y es la pregunta que más valor tiene para el
cliente. Hoy hay **0 filas** — se llenan cuando el cliente cargue sus RCAs.

---

## 5. Leer los datos de la empresa

### 5.1 `/me` — la primera llamada de cualquier integración

```
GET /api/v1/me
```

Devuelve:

- **`usuario`** — tu fila, con el **UUID interno** que usa el resto de la API.
- **`empresa`** — con su **sector económico y tramo por tamaño**, que son los
  que determinan qué normativa le aplica.
- **`permisos`** — ya resueltos: roles + concesiones individuales − denegaciones.
  **La denegación gana.**
- **`roles`** — los códigos de rol, por si necesitás una decisión más gruesa.
- **`perfil_empresa`** — si la empresa completó su perfil. **Lo decide el
  servidor**, no el navegador: sin perfil completo la API rechaza con 409 las
  escrituras de Matriz Legal y Obligaciones.
- **`instalaciones`, `departamentos`, `acotado`** — a qué está limitado.
- **`modo_desarrollo`** — `true` cuando no hay Clerk, y entonces `usuario` es
  `null` (§2.1).

**Un alcance vacío significa "sin acotar", no "ninguno".** El campo `acotado` lo
dice explícito para que no haya que interpretar una lista vacía.

Consultá `permisos` antes de ofrecer una acción: es más barato que recibir un
403 y tener que explicárselo al usuario.

### 5.2 Buscador transversal

```
GET /api/v1/buscar/?q=residuos%20peligrosos
```

Busca en 9 tipos de entidad a la vez: documentos, obligaciones, normas, no
conformidades, auditorías, aspectos ambientales, riesgos, equipos regulados y
procesos. Devuelve grupos por tipo.

```json
{
  "grupos": [
    { "tipo": "obligation", "hay_mas": false,
      "coincidencias": [
        { "tipo": "obligation", "id": "…", "titulo": "Declaración RETC anual",
          "codigo": "OBL-RETC-2026", "contexto": {} }
      ]
    }
  ]
}
```

Tres cosas:

- **Mínimo 2 caracteres**, si no responde 422 explicando el mínimo.
- **Tope de 10 por grupo**, y `hay_mas` avisa cuando se cortó. Una lista cortada
  en silencio hace que alguien deje de buscar.
- **Resuelve acentos.** Usa `to_tsvector('spanish', …)`, que normaliza por su
  cuenta. Medido: `emision` encuentra `DECRETO DE EMISIÓN`; con `ILIKE` no lo
  encontraría, y fallaría sobre 13 de las 24 normas del catálogo — cero
  resultados y ningún error.
- **Filtra por permiso antes de consultar.** Quien no tiene `audit.read` no se
  entera de los títulos de las auditorías escribiendo una palabra en una caja.

### 5.3 Historia de un registro

```
GET /api/v1/historial/?entity_type=obligation&entity_id=<uuid>
```

Actividad, conversación y adjuntos de un registro en una sola línea de tiempo.
Devuelve `eventos[]`, `fuentes[]`, **`fuentes_pendientes[]`** y `hay_mas`.

`fuentes_pendientes` declara qué orígenes que RF-113 nombra **todavía no
existen** (hoy: el correo). Está para que quien lo muestre lo diga: una línea de
tiempo sin correos que no avisa hace concluir que no hubo correos.

### 5.4 Conversación sobre un registro

```
GET   /api/v1/comentarios/?entity_type=obligation&entity_id=<uuid>
POST  /api/v1/comentarios/
```

Comentarios con hilo (un nivel de respuesta) y menciones. **El permiso depende
del registro comentado**: comentar una auditoría exige `audit.write`, una
obligación `obligation.write`.

Publicar exige **sesión identificada**; sin ella responde 409. Esto es material
de contexto valioso para el asistente: es donde queda escrito *por qué* se
declaró tarde algo.

### 5.5 Los otros dominios

Todo lo demás está en el `openapi.json`: obligaciones, matriz legal,
declaraciones y calendario RETC, auditorías e informes, ISO 14001 (aspectos,
riesgos, equipos), tablero, incumplimientos, instalaciones, procesos,
notificaciones. Son lecturas convencionales con la misma paginación y los mismos
errores.

---

## 6. Documentos y sus archivos

```
GET /api/v1/documents/?updated_since=&skip=&limit=
GET /api/v1/documents/vinculados?entity_type=obligation&entity_id=<uuid>
GET /api/v1/documents/{document_id}/versions
GET /api/v1/documents/{document_id}/versions/{version_id}/download-url
```

`/documents/vinculados` es **el sentido que la gente usa**: nadie abre un
documento para averiguar qué respalda; se abre la obligación y se pregunta con
qué se sostiene. La pregunta de un fiscalizador tiene esa forma.

**El ciclo de vida vive en la revisión, no en el documento.** Un documento tiene
varias revisiones y sólo una vigente. Para citar algo como evidencia mirá el
estado de la **revisión** — un borrador no sirve como evidencia, y esa distinción
es todo el punto del módulo.

**Hoy hay 0 documentos en el sistema.** El módulo funciona; no hay contenido.

---

## 7. Guardar la conversación

Esta es la parte que no aparece en el informe, y es la que más te ahorra: **la
persistencia del chatbot ya está construida.** No hace falta que el AI Service
se arme su propio almacenamiento.

### 7.1 Los endpoints

```
GET    /api/v1/support/chatbot                          # conversaciones
POST   /api/v1/support/chatbot                          # abrir una
GET    /api/v1/support/chatbot/{id}                     # una conversación
PATCH  /api/v1/support/chatbot/{id}                     # título, estado
DELETE /api/v1/support/chatbot/{id}

GET    /api/v1/support/chatbot/{id}/messages            # el hilo, en orden
POST   /api/v1/support/chatbot/{id}/messages            # guardar un turno
GET    /api/v1/support/chatbot/{id}/messages/{msg_id}
PATCH  /api/v1/support/chatbot/{id}/messages/{msg_id}   # citas y normas citadas
```

Los mensajes **no se borran**, ni lógicamente. Un hilo al que le falta un
mensaje no queda más corto: queda engañoso, porque lo que viene después sigue
contestando algo que ya no aparece.

### 7.2 Los campos de un mensaje

```json
{
  "conversation_id": "uuid",
  "role": "assistant",
  "content": "El titular debe presentar un EIA.",
  "citations": [
    {"norma": "Ley 19.300", "articulo": "11", "texto": "Los proyectos requerirán…"}
  ],
  "cited_norm_ids": ["uuid-de-la-norma"],
  "model_name": "claude-opus-5",
  "token_usage": {"input": 1200, "output": 340}
}
```

- **`citations`** es una **lista** de forma libre — cada motor cita distinto, así
  que no le imponemos estructura. Es JSONB.
- **`cited_norm_ids`** es un **`uuid[]`** de verdad, con índice GIN. Sirve para
  contestar "qué normas mencionó el asistente" sin parsear texto, y para el
  camino inverso: qué respuestas tocaron una norma que acaba de cambiar.
- **`token_usage`** y **`model_name`** son para costo y trazabilidad. Nadie los
  usa todavía; llenalos igual.

Las respuestas de lectura devuelven además `id`, `tenant_id`, `feedback` y
`created_at`.

### 7.3 Cuatro defectos que arreglé hoy, porque los ibas a encontrar vos

Estos cuatro estaban en el camino exacto que tenés que recorrer, y **ninguno
fallaba de forma visible**. Los cuento porque explican por qué el código de hoy
no se parece al que verías en un `git log` de la semana pasada.

**1 — Las citas no se guardaban.** `ChatbotMessageCreate` no declaraba
`citations` ni `cited_norm_ids`, y Pydantic descarta en silencio lo que no
declara. Mandabas tus citas, recibías **201**, y la fila quedaba con `[]`. Sin
ningún error.

**2 — Y si se hubieran guardado, habría dado 500.** El modelo declaraba
`cited_norm_ids` como JSONB mientras la columna es `uuid[]`:
`column "cited_norm_ids" is of type uuid[] but expression is of type jsonb`. Dos
defectos tapándose entre sí: el que descartaba en silencio ocultaba al que
revienta.

**3 — El hilo se leía desordenado.** La consulta no tenía `ORDER BY`, así que
devolvía el orden físico de las filas. Medido hoy con cuatro mensajes seguidos:

| operación | orden devuelto |
|---|---|
| recién insertados | `[37, 38, 39, 40]` |
| `PATCH citations` | `[37, 38, 39, 40]` |
| **`PATCH cited_norm_ids`** | **`[37, 39, 40, 38]`** |

La diferencia es el índice GIN sobre `cited_norm_ids`: tocar una columna
indexada hace que la fila se reescriba al final. O sea que **la operación que
barajaba el hilo era anotar qué normas citó el asistente** — justo lo que vas a
hacer vos. Y de ese hilo sale el contexto que le mandás al modelo: barajado, te
contesta otra cosa, y no hay ningún síntoma.

**4 — Escribir en una conversación que no era tuya devolvía 201.** Las claves
foráneas de PostgreSQL **no pasan por RLS**, así que la restricción sólo exigía
que la conversación existiera, no que fuera de tu empresa. Y una conversación
inexistente daba **500** en vez de 404 — el peor caso para un servicio que
reintenta ante 5xx: reintentaría para siempre algo que nunca va a funcionar.

| lo que se manda | antes | ahora |
|---|---|---|
| conversación inexistente | 500 | **404** |
| conversación de otra empresa | 201, y la fila quedaba escrita | **404** |

Los cuatro tienen pruebas: `apps/api/tests/test_citas_del_chatbot.py` y
`apps/api/tests/test_hilo_del_chatbot.py`. Las mutaciones están comprobadas —
desconectar el `ORDER BY` o la guarda hace fallar las pruebas.

### 7.4 Qué NO hace esta capa

Es persistencia, no orquestación. **No hay** streaming, ni ventana de contexto,
ni resumen automático de conversaciones largas, ni RAG, ni embeddings. Todo eso
es del AI Service. Acá se guarda lo que pasó.

---

## 8. Lo que no existe y habría que construir

Sin rodeos, para que puedas estimar:

| Falta | Costo | Nota |
|---|---|---|
| **Búsqueda full-text sobre el texto de los artículos** | bajo | El índice GIN ya existe (§0.2). Es un endpoint nuevo sobre `legal_articles.content` |
| **Embeddings / vectores** | medio | No hay `pgvector` ni tabla de embeddings. Es una decisión de arquitectura, no un endpoint |
| **Webhook de "el catálogo cambió"** | bajo | Hoy se resuelve con `updated_since` (§3.3), que probablemente alcanza |
| **Endpoint de contexto armado** | medio | Hoy el AI Service arma su contexto con varias llamadas. Un `/contexto?pregunta=` que devuelva empresa + normativa aplicable + obligaciones en un tiro es útil, pero define política de relevancia — o sea que es una decisión de producto |
| **Streaming (SSE/WS)** | — | La API es HTTP request/response. El streaming vive en el AI Service; acá se guarda el mensaje completo cuando termina |

Ninguno es bloqueante para una primera versión.

---

## 9. Lo que falta decidir, y no lo decido yo

Tres cosas abiertas que dependen de Fabrizzio y del cliente. Las dejo escritas
para que no queden como supuestos de nadie.

### 9.1 Con qué identidad escribe el AI Service

El rol `servicio_lectura` **no incluye `chatbot.use`** (§2.2), a propósito: un
mensaje guardado tiene autor, y "el servicio" no es un responsable con nombre.
Las opciones son dos y son distintas:

- **Con la sesión de la persona que conversa** — el token del usuario viaja al
  AI Service. Trazabilidad correcta; obliga a pasar el token.
- **Con la cuenta de servicio + `chatbot.use`** — más simple; deja todos los
  mensajes atribuidos a "Servicio IA".

Mi recomendación es la primera, y es la que asume el diseño actual.

### 9.2 Dónde corre el AI Service

`apps/ai-service/` es una carpeta con un archivo. No hay servicio. Si va a
correr fuera del `docker compose`, hay que resolver `CORS_ORIGINS` y la red.

### 9.3 Datos reales

Hoy: **0 documentos**, **0 plantillas de declaración**, **0 normativa propia**,
2 empresas de ejemplo. El catálogo sí tiene 24 normas reales de la BCN. Para
probar el asistente contra algo que se parezca a un cliente hace falta que se
carguen RCAs y documentos.

Y la decisión de fondo: **qué normas traer de la BCN**. Son 748.000 y la mayoría
son nombramientos y concesiones de acuicultura. Traerlas todas no es
exhaustividad, es ruido que después alguien clasifica a mano.

---

## 10. Levantarlo para probar

```bash
docker compose up -d
docker compose exec api python -m app.tareas sincronizar-bcn    # el catálogo
docker compose exec api python -m app.tareas.sembrar_demo       # los datos
```

Sin el segundo paso ninguna empresa tiene sector declarado, el CORE responde
`sin_perfil` y el sistema se ve vacío por falta de **datos**, no de
funcionalidad.

- API: `http://localhost:8000` · Swagger: `/docs`
- Web: `http://localhost:3000`
- Sin cuenta de Clerk, la API acepta `X-Tenant-Id` (§2.1) — alcanza para
  ejercitar todas las lecturas de este documento.

---

## Dudas

Cualquier cosa de este documento se puede verificar en el repositorio. Si algo
no coincide con lo que ves corriendo, es un defecto y quiero saberlo: el
problema recurrente de este sistema no ha sido lo que falta, sino **lo que
informa cosas que no son ciertas** — y las cuatro de §7.3 son exactamente eso.
