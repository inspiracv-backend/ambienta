# Design: el buscador transversal

## Una consulta por familia, no una unión SQL

Las tablas no comparten columnas: un documento tiene título y código, un
comentario tiene cuerpo y un padre, una norma tiene número. Un `UNION` las
obligaría a un molde común, y el molde termina siendo el mínimo denominador —
justo lo que hace que un resultado no se pueda distinguir de otro en la lista.

Se consulta cada fuente por separado y se normaliza en Python. Con un tope por
grupo eso son unas pocas consultas acotadas, no un problema de rendimiento.

## El filtro de permiso va por tipo, y se aplica **antes** de consultar

No se consulta lo que la persona no puede leer. Filtrar después funcionaría
igual para el resultado y desperdiciaría la consulta; filtrar antes además deja
claro en el código que el permiso decide **qué se busca**, no qué se muestra.

Los comentarios son el caso especial: su permiso depende del registro
comentado, que varía fila por fila. Se consultan restringidos a los
`entity_type` cuya familia la persona puede leer, en el mismo `WHERE`.

## Sin sesión identificada no se filtra por permiso

En el modo `X-Tenant-Id` —desarrollo, sin Clerk— no hay de dónde sacar
permisos, y RLS ya acota a la empresa. Es el mismo criterio que `/comentarios`
y `/historial`, y está dicho en el docstring para que no se lea como un hueco.

## El mínimo de dos caracteres, y por qué se dice

Una letra sola devuelve casi todo, que no es una búsqueda: es un listado caro
disfrazado. Se responde **422 explicando el mínimo** en vez de devolver una
lista vacía, que se leería como «no hay nada que coincida».

## El tope por grupo avisa

Diez por familia. Un grupo cortado lo dice: una lista que se corta en silencio
afirma que eso es todo lo que hay, y en un buscador esa afirmación es la que
hace que alguien deje de buscar.

## Lo que se busca en cada fuente

| fuente | columnas | por qué esas |
|---|---|---|
| documentos | `title`, `code` | el código es lo que se cita en una auditoría |
| comentarios | `body` | es todo lo que tienen |
| obligaciones | `title`, `code` | ídem documentos |
| normas | `title`, `norm_number` | se busca «19.300» tanto como «bases del medio ambiente» |
| hallazgos, auditorías, aspectos, riesgos, equipos, procesos | su título/nombre | lo que la pantalla muestra |

El número de norma va con `ILIKE` y no con FTS: «19.300» no es una palabra que
el stemmer sepa tratar, y quien lo escribe quiere una coincidencia literal.
Los títulos van con FTS, que es lo que resuelve los acentos.

## Lo que la pantalla tiene que decir

Tres estados, como siempre en este repositorio, y uno más propio del buscador:

| estado | significa |
|---|---|
| `null` | todavía no se buscó |
| error | no se pudo buscar |
| `[]` | se buscó y no hay coincidencias |
| cortado | hay más de lo que se muestra |

Y una advertencia fija: **no se busca dentro de los archivos**. Sin eso, quien
busque una frase que está en el PDF de un procedimiento concluiría que ese
procedimiento no la menciona.
