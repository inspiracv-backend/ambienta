# SPEC-05 · Recuperación

**Objetivo.** Dada una pregunta y una sesión, devolver los fragmentos que la responden, o
ninguno si no hay evidencia suficiente, sin traer nunca el artículo equivocado con seguridad.

## Alcance
- Búsqueda exacta por norma y artículo.
- Búsqueda por palabras y semántica sobre la base del AI Service.
- Fusión, umbral de evidencia y consultas a una fecha.

## Fuera de alcance
- Normativa propia y documentos: van por herramientas en vivo (SPEC-06).
- Reordenamiento con un modelo (reranker): se evalúa en SPEC-08 si el recall lo pide.
- Caché semántico (V2).

## Reglas

| Regla | De dónde sale |
|---|---|
| Tres caminos: exacta, palabras, semántica | D-03 |
| Si la pregunta nombra un artículo (y opcionalmente la norma), la exacta manda y los otros solo agregan contexto detrás | D-03 |
| La exacta compara contra `norm_type` + `norm_number` normalizados ("DS 40", "D.S. N° 40", "decreto supremo 40" → `ds/40`; "Ley 19.300", "ley 19300" → `ley/19300`) y contra `article_number`, incluidos "bis" y transitorios | Con los datos reales el `ILIKE` actual no matchea |
| El umbral de evidencia se aplica a la **similitud coseno** de la semántica, antes de fusionar. Un resultado de palabras solo entra si también superó el umbral en semántica o si la exacta lo trajo | Defecto 4 de SPEC-00 |
| La fusión es RRF (k=60, pesos semántica 1,0 y palabras 0,6) y solo ordena; no decide si hay evidencia | D-03 |
| Cada resultado conserva `similitud` (coseno o nula) y `puntaje` (fusión) por separado | SPEC-00 |
| Sin fecha: se busca en lo indexado (vigente). Con fecha: se consulta `articles?vigente_el=` en vivo, solo para las normas candidatas | Decisión D del plan |
| Toda búsqueda corre con `app.tenant_id` fijado; no hay función que busque sin sesión | D-04 |
| Umbral y `k` son configuración, calibrada con SPEC-08. Valores iniciales: umbral 0,35, k 5 | — |

## Interfaz

```python
@dataclass
class Resultado:
    fragmento_id: int
    article_id: UUID
    norm_id: UUID
    cita: Cita               # norma, artículo, ruta, versión
    texto: str
    similitud: float | None
    puntaje: float
    origen: set[Literal["exacta", "palabras", "semantica", "en_vivo"]]

@dataclass
class Recuperacion:
    resultados: list[Resultado]
    modo: Literal["exacta", "combinada", "historica"]
    hay_evidencia: bool
    mejor_similitud: float | None

async def recuperar(pregunta: str, sesion: Sesion, *, fecha: date | None = None, k: int = 5) -> Recuperacion
def detectar_cita(pregunta: str) -> CitaDetectada | None
def normalizar_norma(texto: str) -> str | None
```

## Criterios de aceptación

```gherkin
# language: es
Característica: Traer lo correcto, o nada

  Escenario: Artículo pedido por número
    Cuando se recupera "¿qué dice el artículo 11 de la Ley 19.300?"
    Entonces el primer resultado es el artículo 11 de la Ley 19.300
    Y el modo es "exacta"

  Esquema del escenario: Variantes del nombre de una norma
    Cuando se normaliza "<texto>"
    Entonces el resultado es "<clave>"

    Ejemplos:
      | texto              | clave     |
      | DS 40              | ds/40     |
      | D.S. N° 40         | ds/40     |
      | decreto supremo 40 | ds/40     |
      | Ley 19.300         | ley/19300 |
      | ley N°19300        | ley/19300 |

  Escenario: Artículo bis
    Cuando se detecta la cita en "¿qué dice el artículo 10 bis?"
    Entonces el artículo detectado es "10 bis"

  Escenario: Pregunta conceptual
    Cuando se recupera "¿qué proyectos tienen que someterse a evaluación de impacto ambiental?"
    Entonces entre los tres primeros está el artículo 10 u 11 de la Ley 19.300
    Y el modo es "combinada"

  Escenario: Fuera del corpus
    Cuando se recupera "¿cuál es la tasa del impuesto a la renta de primera categoría?"
    Entonces hay_evidencia es falso
    Y no hay resultados

  Escenario: Coincidencia de palabras sin evidencia semántica
    Dado que "declaración" aparece en un artículo cuya similitud con la pregunta es 0,20
    Cuando se recupera la pregunta
    Entonces ese artículo no está en los resultados

  Escenario: Consulta a una fecha
    Cuando se recupera "artículo 11 de la Ley 19.300" con fecha 2009-06-30
    Entonces el texto viene del backend con vigente_el=2009-06-30
    Y el modo es "historica"

  Escenario: Norma sin texto a esa fecha
    Dado que el backend devuelve [] para una norma con vigente_el=1990-01-01
    Cuando se recupera con esa fecha
    Entonces hay_evidencia es falso
    Y no se lanza error

  Escenario: Sin sesión no se busca
    Cuando se llama a recuperar sin sesión
    Entonces se lanza un error antes de consultar la base
```

## Pruebas
- **Unitarias**: `detectar_cita`, `normalizar_norma`, RRF, aplicación del umbral, con
  resultados construidos a mano.
- **Integración** con la base sincronizada desde el compose (datos reales de la Ley 19.300):
  escenarios 1, 4 y 5. Los embeddings reales se cachean en un fixture para no pagarlos en cada
  corrida.
- La calidad de fondo (recall, posición) no se prueba acá: es SPEC-08.

## Implementación (20/09/2026)

Implementado en `servicio/src/ambienta_ia/recuperacion/` y `servicio/src/ambienta_ia/citas.py`.
Pruebas: `tests/unit/test_citas.py` y `tests/integracion/test_recuperacion.py`.

Diferencias con lo escrito arriba:
- La búsqueda por palabras usa **cualquiera** de los términos (OR), no todos: con AND, "requieren"
  y "requerirán" no se encuentran y una pregunta completa casi nunca matchea. El orden lo da
  `ts_rank`.
- En vez de "un resultado de palabras solo entra si también superó el umbral en semántica", cada
  resultado de palabras trae su propia similitud coseno (se calcula en la misma consulta) y se le
  aplica el mismo umbral. Es la misma regla, sin depender de que también haya salido en la otra
  lista.

## Contra el backend real (21/09/2026)

Ver [`prueba-contra-ambienta/`](../prueba-contra-ambienta/README.md).
- **Reordenador con el modelo** (`recuperacion/reordenar.py`): con el catálogo real la
  similitud no separa lo pertinente de lo ajeno y ningún umbral funciona. Se califican ~24
  candidatos de 0 a 3; hace falta al menos un 3 para que haya evidencia; máximo 2 partes por
  artículo; lo pedido por número y norma no se cae.
- Se busca con la pregunta de la persona y con la reformulación del modelo, juntas.
- Sin reordenador (demo, sin red) sigue el umbral de coseno.
- Medido sobre el catálogo real: recall@5 0,77 → 1,00; MRR 0,63 → 0,94; falsos positivos 2 → 0.
