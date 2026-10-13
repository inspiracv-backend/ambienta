# Design: la línea de tiempo

## La traducción de vocabulario se deriva, no se escribe

`audit_log.entity_type` guarda el nombre de la **tabla** porque lo escribe el
observador del `flush`, que ve modelos de SQLAlchemy y no conceptos de negocio.
Cambiarlo sería reescribir 9.575 filas y romper el observador.

Así que se traduce al leer, y la traducción sale de
`ANCLAJES[tipo].modelo.__tablename__`. **No es una lista nueva**: es el mismo
mapa que valida el anclaje de RF-108 y que resuelve el permiso de RF-111,
preguntándole al modelo cómo se llama su tabla. Una entidad nueva no necesita
que nadie se acuerde de agregarla en un cuarto lugar.

Hay una prueba que compara los `entity_type` **realmente presentes** en
`audit_log` contra los nombres de tabla derivados, y avisa de los que ninguna
entidad de dominio reclama. No falla por ellos —hay tablas auditadas que no son
entidades comentables, como `user_permissions`— pero deja el número a la vista.

## Una respuesta, tres orígenes, un orden

El evento sale normalizado: `tipo`, `ocurrido_el`, `actor`, `resumen` y el
detalle propio de su origen. La alternativa —tres listas que el navegador
entrelaza— pone el criterio de orden en el cliente, y dos clientes distintos
mostrarían dos historias distintas del mismo registro.

**El orden es del más reciente al más antiguo**, igual que el componente que ya
existe: en una fiscalización la primera pregunta es *qué pasó al final*.

## Las fuentes se declaran, incluidas las que faltan

La respuesta trae `fuentes` con lo que la compone y `fuentes_pendientes` con lo
que no. Hoy: `correo`, porque RF-107 (#72) no existe.

Es el mismo criterio que la `periodicidad` vacía de `retc_systems` y que las
plantillas Excel: **lo que no se sabe se dice**, en vez de entregar algo que se
ve completo. Una línea de tiempo sin correos que no avisa hace concluir que no
hubo correos.

## Un tope, y que se note

Se devuelven como máximo 200 eventos. Un registro con más tiene historia
anterior, y la respuesta lo dice con `hay_mas`: una lista cortada en silencio
es la misma trampa que las oportunidades del CRM filtradas en el navegador.

## El permiso, otra vez del registro

Leer la historia de una obligación exige `obligation.read`, resuelto con
`familia_de` — el mismo camino que los comentarios. Una línea de tiempo es una
lectura del registro, así que no puede pedir menos que leerlo.

## Lo que el frontend NO cambia

`HistorialTimeline` conserva sus props y las 5 páginas que lo montan no se
tocan. Lo que cambia es de dónde salen los eventos: un hook que consulta la API
y **se combina con** lo de la sesión, para que una acción recién hecha aparezca
sin esperar a la próxima carga.

La traducción español → dominio (`obligacion` → `obligation`) vive en
`lib/vocabulario-de-entidades.ts`, con una prueba que exige que **cada**
`EntidadAuditable` esté mapeada o declarada sin equivalente. Cuatro no lo
tienen —`usuario`, `tenant`, `departamento`, `planta`— y para esas la línea de
tiempo sigue mostrando sólo lo de la sesión, que es lo que hacía antes.
