# SPEC-04 · Sincronización del catálogo

**Objetivo.** Mantener la base del AI Service igual al catálogo del backend, trayendo solo lo que
cambió y armando cada fragmento desde el árbol de artículos, sin parsear texto legal.

## Alcance
- Catálogo público: normas, versión vigente y su articulado.
- Corrida completa y corrida incremental.
- Invocación por comando (`python -m ambienta_ia.sincronizar`) y programable.

## Fuera de alcance
- Traer normas nuevas de la BCN: lo hace el backend (`sincronizar-bcn`). El AI Service solo
  copia lo que el backend ya tiene.
- Normativa propia y documentos (V2, decisión C).
- Versiones no vigentes: las consultas históricas van en vivo (decisión D).

## Reglas

| Regla | De dónde sale |
|---|---|
| Se leen normas con `updated_since` = `sincronizacion.updated_at_maximo`. Al terminar se guarda el máximo `updated_at` visto, no la hora | Handoff §3 |
| La versión a indexar es la de `is_current = true`. Si hay más de una, la de `valid_from` más reciente | Handoff §4 (Ley 19.300: 1994 y 2010) |
| Si el `content_hash` de la versión vigente no cambió, no se generan embeddings | SPEC-03 |
| Si cambió la versión vigente, los fragmentos de la anterior se borran en la misma transacción en que se insertan los nuevos. Nunca hay un momento con las dos o con ninguna | D-06: no servir texto derogado |
| La `ruta` se arma subiendo por `parent_article_id` hasta la raíz, en el orden de `display_order` | D-02, handoff §4 |
| Se indexan los nodos con `content` no vacío. Los contenedores (título, capítulo) aportan a la `ruta`, no son fragmentos | Un título sin texto no se cita |
| Un artículo de más de `MAX_CARACTERES` (1.800) se parte por párrafos, nunca a mitad de oración | D-01 |
| Una norma que falla no frena las demás: se registra y se sigue. El `updated_at_maximo` solo avanza hasta la última norma procesada sin error | Si avanzara igual, la norma fallida no se volvería a pedir nunca |
| La sincronización usa la cuenta `servicio_lectura` | SPEC-02 |

## Interfaz

```python
async def sincronizar(completa: bool = False) -> ResultadoSincronizacion

@dataclass
class ResultadoSincronizacion:
    normas_vistas: int
    versiones_nuevas: int
    versiones_sin_cambios: int
    fragmentos_indexados: int
    fragmentos_borrados: int
    errores: list[ErrorNorma]
    updated_at_maximo: datetime | None
    duracion_s: float
```

```python
def armar_ruta(articulo: Articulo, por_id: dict[UUID, Articulo], norma: Norma) -> str
def elegir_vigente(versiones: list[VersionNorma]) -> VersionNorma | None
def fragmentar(articulo: Articulo, ruta: str) -> list[FragmentoNuevo]
```

## Criterios de aceptación

```gherkin
# language: es
Característica: El AI Service tiene el mismo catálogo que el backend

  Escenario: Primera corrida
    Dado un backend con 24 normas y 689 artículos vigentes
    Y una base del AI Service vacía
    Cuando corre la sincronización
    Entonces hay fragmentos para las 24 normas
    Y updated_at_maximo es el mayor updated_at de las normas recibidas

  Escenario: Segunda corrida sin cambios
    Dado que la sincronización ya corrió
    Cuando corre de nuevo sin cambios en el backend
    Entonces la petición lleva updated_since igual a updated_at_maximo
    Y no se generó ningún embedding

  Escenario: Dos versiones marcadas vigentes
    Dada la Ley 19.300 con una versión de 1994 y otra de 2010, ambas con is_current verdadero
    Cuando se elige la versión a indexar
    Entonces se elige la de 2010

  Escenario: Cambio de versión sin hueco
    Dada una norma indexada con la versión V1
    Y el backend publica V2 como vigente
    Cuando corre la sincronización
    Entonces los fragmentos de V1 ya no existen
    Y los de V2 existen
    Y ninguna consulta concurrente vio la norma sin fragmentos

  Escenario: La ruta sale del árbol
    Dado el artículo 11 cuyo padre es el Párrafo 2º, cuyo padre es el Título II de la Ley 19.300
    Cuando se arma su ruta
    Entonces es "Ley 19.300 › Título II › Párrafo 2º › Artículo 11"

  Escenario: Los contenedores no son fragmentos
    Dado un título sin content con tres artículos hijos
    Cuando se fragmenta la norma
    Entonces hay tres fragmentos y ninguno es el título

  Escenario: Una norma que falla no se pierde
    Dado que la norma N3 responde 500 y las demás 200
    Cuando corre la sincronización
    Entonces el resultado lista el error de N3
    Y updated_at_maximo no supera el updated_at de N3
    Y en la próxima corrida N3 se vuelve a pedir
```

## Pruebas
- **Unitarias**: `armar_ruta`, `elegir_vigente`, `fragmentar` con árboles armados en la prueba,
  incluido el caso real de la Ley 19.300 (un fixture con un extracto de su árbol).
- **Integración** con backend simulado (`respx`) y base real: escenarios 1, 2, 4 y 7.
- **Integración** contra el compose de Ambienta: escenario 1 con los datos reales.

## Implementación (20/09/2026)

Implementado en `servicio/src/ambienta_ia/sincronizar/`. Pruebas: `tests/unit/test_arbol.py` y
`tests/integracion/test_sincronizacion.py` (incluida la de cambio de versión con un observador
concurrente que nunca ve la norma sin fragmentos).

Agregados: el texto que se convierte en vector lleva el **título de la norma** además de la
ruta y el texto (`texto_para_embedding`): un artículo de una RCA no dice "RCA" en ningún lado.
Una norma del listado con `tenant_id` no nulo se omite: no es catálogo público.

## Contra el backend real (21/09/2026)

Ver [`prueba-contra-ambienta/`](../prueba-contra-ambienta/README.md).
- **El árbol llega plano** (`parent_article_id` vacío en los 689 artículos). Se reconstruye la
  ruta por `display_order`: títulos (`subsection`) y párrafos (`paragraph`) son contexto.
- **El número se toma del encabezado del texto** ("Artículo 11 bis.-"): `article_number` pierde el
  sufijo. Los transitorios se distinguen por la sección "ARTICULOS TRANSITORIOS".
- **`/catalog/norms` devuelve también la normativa propia de la empresa de la cuenta**, sin
  `tenant_id`. El sincronizador pide `/compliance/normativa-propia/`, excluye esas normas, purga
  las que se hayan colado, y si esa llamada falla no indexa nada.
- Resultado: 24 normas vistas, 23 vigentes, 792 fragmentos, todos con número; la segunda corrida
  no trae nada.
