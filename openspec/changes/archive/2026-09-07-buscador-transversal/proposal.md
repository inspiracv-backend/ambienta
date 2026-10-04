# Proposal: Un buscador que atraviesa el sistema

Fuente: Análisis Funcional v1.8 §3.17, **RF-114** — *«Buscador transversal
sobre documentos, comentarios y registros»*. Issue #76, el último de la
épica #31.

## Lo que hay hoy, medido el 7-sep-2026

**Nada.** Ni endpoint, ni servicio, ni pantalla:

| Búsqueda | Resultado |
|---|---|
| Rutas de la API con `/search` o `/buscar` | **0** |
| Pantallas con un buscador global | **0** |

Lo único parecido es el filtro de texto de la cartera del CRM, que opera sobre
la lista que ya está en memoria.

## Por qué importa acá más que en otro producto

Los tres cambios anteriores de esta épica repartieron la información: un
documento cuelga de una obligación (#73), la conversación vive en el registro
(#74), la historia se reúne por entidad (#75). Todo eso se encuentra **si ya
sabés a qué ficha entrar**.

La pregunta que hace un fiscalizador no tiene esa forma. Dice *«muéstreme lo de
los residuos peligrosos»*, y eso está repartido entre una norma, tres
obligaciones, un procedimiento y el comentario donde alguien explicó por qué se
declaró tarde.

## La decisión técnica, y la medición que la decide

**Búsqueda de texto completo con la configuración `spanish`, no `ILIKE`.**

Este repositorio ya perdió tiempo con esto en la BCN: *«la búsqueda distingue
acentos — `emision` no encuentra `EMISIÓN`: devuelve cero resultados y ningún
error»*. Medido hoy contra la base real:

| forma | `emision` encuentra `DECRETO DE EMISIÓN` |
|---|---|
| `to_tsvector('spanish', …)` | **sí** |
| `ILIKE '%emision%'` | **no** |

El stemmer español normaliza los acentos por su cuenta, así que no hace falta
`unaccent`. Y `ILIKE` —la opción corta— fallaría sobre **13 de las 24 normas
del catálogo**, que es donde están los títulos en mayúscula con tilde. Cero
resultados y ningún error, otra vez.

## Lo que se propone

`GET /buscar?q=…` sobre tres familias:

1. **Documentos** — título y código.
2. **Comentarios** — el texto, con el registro al que pertenecen.
3. **Registros** — obligaciones, hallazgos, auditorías, normas, aspectos,
   riesgos, equipos y procesos.

Agrupado por tipo, con un tope por grupo y aviso cuando se corta.

## El permiso es el problema real, no la consulta

Un buscador que devuelve de todo **es un oráculo**: quien no tiene `audit.read`
no debería enterarse de los títulos de las auditorías escribiendo una palabra
en una caja. RLS acota a la empresa, no a lo que esa persona puede ver dentro
de ella.

Cada resultado se filtra por el `<familia>.read` de su tipo, resuelto con el
**mismo mapa** `ANCLAJES` que valida el anclaje de RF-108, el permiso de RF-111
y la traducción de RF-113. Es su cuarto uso, y sigue siendo una sola lista.

## Lo que NO entra

- **Buscar dentro del contenido de los archivos.** El PDF vive en B2 y
  extraerle texto es otra cosa —y otra decisión de costo—. Se busca el
  **documento**, no lo que dice adentro, y la pantalla lo aclara para que nadie
  concluya que un procedimiento no menciona algo.
- **Índices materializados ni columnas `tsvector` guardadas.** Con este volumen
  la consulta directa alcanza; una columna generada que se olvide de
  actualizar es un buscador que deja de encontrar lo nuevo, en silencio.
- **Corrección de errores de tipeo.** `fuzzystrmatch` está disponible y es un
  problema aparte.
