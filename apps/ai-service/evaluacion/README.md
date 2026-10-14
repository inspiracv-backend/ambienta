# Evaluación

| Archivo | Qué es |
|---|---|
| `semilla_demo.jsonl` | 20 casos sobre los datos del backend simulado. Sirve para que CI tenga contra qué medir desde el día uno. **No es el dataset dorado.** |
| `umbrales.json` | Mínimos (y el máximo de `falsos_positivos`) que un PR no puede empeorar. Solo suben. |

## El dataset dorado lo escribe el equipo legal

Sobre las normas reales del catálogo, sin ver las respuestas del sistema (SPEC-08): al menos 50
casos, 10 que deben abstenerse, 10 que piden un artículo por número y 5 a una fecha. Mismo
formato que la semilla. Va en `dorado.jsonl`, en un PR propio, nunca junto con un cambio de
código.

## Primera medición (20/09/2026)

Embeddings locales (bolsa de palabras), `UMBRAL_EVIDENCIA=0.25`, k=5:

| recall@5 | precisión@5 | mrr | abstención correcta | falsos positivos |
|---|---|---|---|---|
| 0,80 | 0,47 | 0,73 | 0,90 | **0** |

Los tres casos que fallan son a propósito de sinónimos, y muestran el límite del proveedor
local, no del diseño:

- `ds40-003-concepto`: la pregunta dice "megawatts", el artículo "MW".
- `ley19300-051-concepto`: "culpa o dolo" contra "culposa o dolosamente".
- `ley19300-011-concepto`: "en vez de una declaración" no comparte palabras con el artículo 11.

## Segunda medición, con el modelo real (21/09/2026)

`text-embedding-3-small` + `gpt-4o-mini`, mismo dataset. Recuperación, según el umbral:

| Umbral | recall@5 | mrr | abstención correcta | falsos positivos |
|---|---|---|---|---|
| 0,25 | 1,00 | 0,89 | 0,85 | 3 |
| 0,30 | 1,00 | 0,89 | 0,95 | 1 |
| 0,35 | 1,00 | 0,89 | 0,95 | 1 (`fuera-sociedades`) |
| **0,40** | **1,00** | **0,89** | **1,00** | **0** |

Los tres casos de sinónimos que fallaban con los embeddings locales pasan todos.

Respuestas completas, con el modelo y el revisor:

| Umbral | abstención correcta | falsos positivos | citas válidas | tokens por consulta | latencia p95 |
|---|---|---|---|---|---|
| 0,35 | 1,00 | 0 | 0,97 | ~1.710 | 4,0 s |
| 0,40 | 1,00 | 0 | 0,97 | ~1.630 | 4,0 s |

Con 0,35 el revisor frena el falso positivo que deja pasar la búsqueda; con 0,40 la búsqueda ya
no lo deja pasar. **Se fija 0,40** para no depender de la segunda barrera. La única cita "no
válida" es el art. 15 del DS 40 en `ley19300-011-concepto`, que es pertinente (contenido de la
DIA): el dataset es más estricto que la respuesta.

La corrida completa (dos umbrales, 20 casos cada uno, más las consultas de prueba) costó del orden
de centavos de dólar con `gpt-4o-mini`.

## Cómo se corre

```bash
# recuperación: sin modelo de lenguaje, barato
python -m ambienta_ia.evaluar --dataset evaluacion/semilla_demo.jsonl \
    --umbrales evaluacion/umbrales.json --barrido --salida reporte.json

# respuestas completas: usa el modelo y gasta tokens
python -m ambienta_ia.evaluar --dataset evaluacion/semilla_demo.jsonl --modo respuestas \
    --umbrales evaluacion/umbrales.json
```

## Tercera medición: el catálogo real (21/09/2026)

Contra el backend real de Ambienta levantado en local, con los 24 textos de la BCN, y la semilla
[`semilla_catalogo_real.jsonl`](semilla_catalogo_real.jsonl) (17 casos; las respuestas se
verificaron leyendo el texto real).

| | recall@5 | MRR | abstención | falsos positivos |
|---|---|---|---|---|
| Sin reordenador, umbral 0,40 | 0,77 | 0,63 | 0,88 | 2 |
| **Con reordenador** | **1,00** | **0,94** | **1,00** | **0** |

Respuestas completas con reordenador: abstención 1,00, falsos positivos 0, al menos una cita
esperada 1,00; ~3.000 tokens y p95 de ~12 s por consulta.

Lo que enseñó: con el catálogo real, **el umbral de coseno no sirve** ("velocidad máxima en
autopistas" llega a 0,518, más que "artículo 3 del DS 40"). El umbral de 0,40 medido con la
demo no se traslada. Ver `../../prueba-contra-ambienta/README.md`.
