# Design: la integración con el AI Service

## `updated_since` compara contra `updated_at`, y eso tiene un filo

El filtro es `updated_at > updated_since`, estrictamente mayor. Con `>=` un
ciclo que pida "desde la última corrida" recibe siempre la última fila de la
corrida anterior; con `>` puede **perderse** una fila escrita en el mismo
microsegundo del corte.

Se elige `>` y se documenta, porque el modo de fallo de `>=` es ruido constante
y el de `>` es improbable y detectable: quien indexa guarda el `updated_at`
máximo que vio, no la hora en que corrió.

**El reloj es el del servidor**, no el del cliente. Un AI Service con el reloj
adelantado que guardara *su* hora se saltaría filas. Por eso la respuesta sigue
trayendo `updated_at` en cada registro: el próximo corte sale del dato, no del
reloj de nadie.

## El articulado por fecha usa `valid_from`/`valid_to`, no `is_current`

`is_current` dice cuál rige **hoy**; la pregunta del AI Service es cuál regía en
una fecha. Se resuelve con el rango de vigencia de la versión.

Un detalle que importa: `valid_to` es nulable y `NULL` significa *«todavía
rige»*, no *«no rige»*. La condición es
`valid_from <= fecha AND (valid_to IS NULL OR valid_to >= fecha)`. Escribirla al
revés devolvería **cero artículos para la versión vigente**, que es justo la que
más se consulta.

Y si ninguna versión cubre esa fecha, la respuesta es **lista vacía, no 404**:
la norma existe y la respuesta correcta es "no había texto vigente entonces".
Es el mismo criterio que ya usa el endpoint para una norma sin versión vigente.

## El checksum viaja con el enlace, no aparte

`EnlaceDeDescarga` suma `checksum_sha256`. Pedirlo en otra llamada funciona y
abre una ventana: entre las dos peticiones alguien puede publicar una revisión
nueva, y el AI Service validaría el archivo contra el hash del otro texto —
concluyendo que se corrompió cuando lo que pasó es que cambió.

`None` cuando la revisión no lo tiene: se calcula al confirmar la subida, y una
revisión creada por otro camino puede no tenerlo. **No se inventa un hash**; el
AI Service sabrá que no puede verificar, que es distinto de verificar mal.

## Las cabeceras se declaran donde se emiten

`X-Has-More` y `X-Page-Limit` salen de `recortar()` en `_paginacion.py`, así que
la declaración se deriva del mismo lugar en vez de escribirse endpoint por
endpoint. Son ~60 rutas paginadas: escribirlo a mano es una decisión que se
puede olvidar, y olvidarla no falla — sólo deja el contrato mintiendo.

Es el mismo criterio que las respuestas de error, que ya se derivan en
`construir_esquema()`.

## `X-Tenant-Id`: la descripción decía menos de lo que hace falta

El contrato lo mostraba como un header opcional más. Con Clerk configurado la
cabecera **se ignora por completo** —un token de una empresa con `X-Tenant-Id`
de otra sigue devolviendo los datos de la primera—, y eso no se deducía del
contrato. Un integrador podía razonablemente creer que era el selector de
tenant.

No es un cambio de comportamiento: es que el contrato diga lo que el sistema ya
hace.
