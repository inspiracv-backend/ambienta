# SPEC-00 · Correcciones del material existente

**Objetivo.** Que el código de guía de `03-retrieval/`, `04-evaluacion/` y `05-agente/` deje de
enseñar comportamientos que hacen responder mal sin avisar.

## Alcance
- Los cinco defectos de abajo, en los archivos donde están.
- `00-contrato/`: reemplazar el spec congelado por el del 08/09 y rehacer `cruce.md` y
  `verificar_alineacion.py`.
- Una línea en cada README de etapa apuntando al módulo equivalente de `servicio/`.

## Fuera de alcance
- Reestructurar las carpetas, cambiar nombres de archivos o de funciones: las guías de las
  sesiones las citan.
- Portar al servicio (eso es SPEC-05 y SPEC-06).

## Los defectos

| # | Archivo | Qué pasa hoy | Qué tiene que pasar |
|---|---|---|---|
| 1 | `05-agente/grafo.py` · `despues_de_evaluar` | Tras dos rechazos del revisor, el grafo termina y entrega la última respuesta, la rechazada | Tras dos rechazos, la respuesta es la abstención estándar |
| 2 | `05-agente/grafo.py` · `evaluar` | `deberia_abstenerse=True` cuenta como rechazo, así que una abstención correcta se manda a corregir | Si la respuesta es una abstención y el revisor coincide en que había que abstenerse, se aprueba |
| 3 | `05-agente/tools.py` · `buscar_normativa` y `03-retrieval/busqueda_hibrida.py` | `fecha` se recibe y se descarta; la exacta y la de palabras filtran siempre por vigente | `fecha` llega a las tres búsquedas y las tres filtran por la versión vigente ese día (D-06) |
| 4 | `04-evaluacion/metricas.py` | El umbral de 0,35 se compara contra el puntaje RRF (~0,016) | La evidencia se decide sobre la similitud coseno de la búsqueda semántica, antes de fusionar |
| 5 | `05-agente/tools.py` | La herramienta busca con `umbral=0.0` y nunca devuelve `SIN_RESULTADOS` con corpus no vacío | La herramienta aplica el umbral de evidencia y devuelve `SIN_RESULTADOS` cuando nada lo supera (D-07) |

Para que 3, 4 y 5 funcionen, `Resultado` suma un campo `similitud` (la coseno original, o
`None` si vino de exacta o palabras) que la fusión no pisa. `puntaje` sigue siendo el de la
fusión.

## Criterios de aceptación

```gherkin
# language: es
Característica: El material de guía no inventa cuando no tiene evidencia

  Escenario: Dos rechazos terminan en abstención
    Dado un revisor que rechaza toda respuesta
    Cuando el agente responde "¿cuál es el plazo para declarar emisiones?"
    Entonces la respuesta final es "No tengo información suficiente para responder esto."
    Y el grafo hizo exactamente dos evaluaciones

  Escenario: Una abstención correcta se aprueba
    Dado que la búsqueda devuelve SIN_RESULTADOS
    Y el modelo responde que no tiene información suficiente
    Cuando el revisor marca deberia_abstenerse=verdadero
    Entonces el veredicto es "ok"
    Y no hay un segundo intento

  Escenario: La fecha llega a las tres búsquedas
    Dado el artículo 15 con una versión vigente hasta 2023-12-31 y otra desde 2024-01-01
    Cuando se busca "artículo 15" con fecha 2023-06-30
    Entonces se recupera el texto de la versión anterior
    Y ninguna de las búsquedas devuelve la versión de 2024

  Escenario: La métrica de abstención usa la similitud y no el puntaje fusionado
    Dada una pregunta sin número de artículo cuya mejor similitud coseno es 0,62
    Cuando se evalúa con umbral 0,35
    Entonces el caso cuenta como "con evidencia"

  Escenario: La herramienta se abstiene por umbral
    Dado un corpus con fragmentos
    Y una pregunta cuya mejor similitud es 0,20
    Cuando el agente llama a buscar_normativa
    Entonces la herramienta devuelve un texto que empieza con "SIN_RESULTADOS"
```

## Pruebas
- `tests/material/` en la raíz del repo, con pytest. El LLM y los embeddings se reemplazan
  por dobles: estas pruebas no pueden gastar tokens ni depender de la red.
- Los escenarios 3 a 5 necesitan PostgreSQL con pgvector; corren con el contenedor del README.

## Implementación (20/09/2026)

Implementado el 20/09/2026 en `03-retrieval/`, `04-evaluacion/` y `05-agente/`. Pruebas en
`tests/material/` (8). Se verificó que las 8 **fallan contra el código anterior** y pasan con la
corrección. `cruce.md`, `verificar_alineacion.py` y los README de cada etapa quedaron
actualizados y apuntan al servicio.
