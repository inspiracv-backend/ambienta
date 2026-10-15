# SPEC-08 · Evaluación

**Objetivo.** Saber, con números reproducibles, si el sistema trae el artículo correcto, si
responde bien con él y si se abstiene cuando debe, y que ningún cambio empeore eso sin que se
note.

## Alcance
- Dataset dorado sobre el catálogo real.
- Métricas de recuperación, de cita y de abstención.
- Juez con modelo como segunda capa.
- Umbrales mínimos en CI.

## Fuera de alcance
- Evaluación con usuarios reales (se hace con las trazas de SPEC-09 una vez en uso).

## Reglas

| Regla | De dónde sale |
|---|---|
| Se mide la recuperación por separado de la respuesta | D-09 |
| La cita se verifica en código: el artículo citado existe, es de la versión correcta y está entre los esperados | D-08 |
| La evidencia se decide con la similitud coseno, no con el puntaje fusionado | SPEC-00, defecto 4 |
| El dataset lo escribe el equipo con criterio legal **sin ver las respuestas del sistema**. Quien construye no escribe las preguntas | Si no, se mide lo que el sistema ya sabe hacer |
| Al menos 50 casos; al menos 10 deben abstenerse; al menos 10 piden un artículo por número; al menos 5 son a una fecha | Cubrir los tres caminos y D-06 |
| El dataset se versiona en el repo. Un cambio en el dataset y un cambio en el código no van en el mismo PR | Si no, no se sabe qué movió la métrica |
| Los umbrales de CI se fijan con la primera medición real y solo suben | — |

## Formato del caso

```json
{
  "id": "ley19300-011-a",
  "pregunta": "¿Qué proyectos tienen que presentar un estudio de impacto ambiental?",
  "norma": "ley/19300",
  "articulos_esperados": ["11"],
  "fecha": null,
  "debe_abstenerse": false,
  "respuesta_referencia": "…",
  "autor": "…",
  "revisado_por": "…"
}
```

## Métricas

| Métrica | Qué mide | Sobre qué casos |
|---|---|---|
| `recall@k` | Los esperados aparecen entre los primeros k | con respuesta |
| `mrr` | Posición del primer acierto | con respuesta |
| `abstencion_correcta` | Se abstuvo si y solo si debía | todos |
| `falsos_positivos` | Respondió cuando debía abstenerse | los que deben abstenerse. **Es la métrica que más importa** |
| `citas_validas` | Proporción de citas que existen y están entre los recuperados | con respuesta |
| `fidelidad` (juez) | La respuesta no afirma nada que no esté en lo recuperado | con respuesta |
| `costo_medio`, `latencia_p95` | Por consulta | todos |

## Criterios de aceptación

```gherkin
# language: es
Característica: Las métricas dicen la verdad

  Escenario: Abstención medida con la similitud
    Dado un caso sin número de artículo cuya mejor similitud es 0,62
    Cuando se evalúa con umbral 0,35
    Entonces el caso no cuenta como abstención

  Escenario: Cita inexistente
    Dada una respuesta que cita el artículo 99 de la Ley 19.300, que no existe
    Cuando se calcula citas_validas
    Entonces esa cita cuenta como inválida

  Escenario: Un cambio que empeora no se mergea
    Dado que el umbral de CI para falsos_positivos es 0
    Cuando un PR hace que un caso que debía abstenerse responda
    Entonces el job de evaluación falla y nombra el caso

  Escenario: Resultado reproducible
    Dado el mismo código, dataset y modelos
    Cuando se corre la evaluación dos veces
    Entonces las métricas de recuperación son idénticas

  Escenario: Barrido de k
    Cuando se corre el barrido con k en 1, 3, 5, 10 y 20
    Entonces el reporte muestra recall, precisión y tokens de contexto para cada k
```

## Pruebas y ejecución
- `python -m ambienta_ia.evaluar --dataset evaluacion/dorado.jsonl` genera
  `reporte.json` y un resumen en markdown.
- **Unitarias** de las métricas con casos armados a mano (escenarios 1 y 2).
- **CI**: recuperación en cada PR (usa embeddings cacheados, barato); respuesta y juez solo en
  la rama principal (cuesta tokens). El resumen se publica como comentario del PR.

## Implementación (20/09/2026)

Implementado en `servicio/src/ambienta_ia/evaluar/`. Dataset semilla y primera medición en
`servicio/evaluacion/` (README con los números). Umbrales fijados con esa medición:
recall@5 0,80 · mrr 0,73 · abstención 0,90 · falsos positivos 0.

Los tres casos que fallan con embeddings locales son de sinónimos ("megawatts" / "MW", "culpa"
/ "culposa") y quedan a propósito: son los que tienen que pasar con el proveedor de producción.
`citas_validas` se fija con la primera corrida con el modelo real.

**21/09/2026, con el modelo real** (`text-embedding-3-small` + `gpt-4o-mini`): recall@5 1,00 ·
mrr 0,89 · abstención 1,00 · falsos positivos 0 · citas válidas 0,97, con umbral 0,40, que pasa
a ser el valor por defecto. Esa corrida encontró dos defectos que la demo no mostraba (el revisor
no veía los datos de la empresa, y una reformulación corta del modelo no alcanzaba el umbral);
los dos tienen prueba en `tests/unit/test_agente.py`.

## Contra el backend real (21/09/2026)

Ver [`prueba-contra-ambienta/`](../prueba-contra-ambienta/README.md).
- Nueva semilla sobre el catálogo real (`evaluacion/semilla_catalogo_real.jsonl`, 17 casos,
  respuestas verificadas en el texto). Respuestas completas: abstención 1,00, falsos positivos 0,
  al menos una cita esperada 1,00.
- Nueva métrica `cita_esperada`: `citas_validas` es precisión y castiga citar además otros
  artículos pertinentes.
- El CLI arma la sesión con `/me` cuando recibe `--token`.
