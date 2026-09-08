"""Detectores de las clases de defecto que este repositorio ya sufrio.

## Por que existe

El patron de este proyecto no es "codigo con errores": es **codigo que responde
bien y no hace nada**. `bcn.sincronizar()` escrita, probada y sin un solo
llamador. `control_documental.py` igual. Pantallas leyendo `mocks/` sin hacer
una peticion. Un cron corriendo a la unica hora a la que no avisaba.

Encontrar eso no necesita criterio, necesita **buscar**. Este archivo hace la
busqueda; el juicio sobre cada coincidencia lo pone una persona despues.

Se escribio despues de intentarlo con quince agentes en paralelo: gastaron 4,4
millones de tokens en seis minutos y devolvieron cero por un limite de gasto.
Esto cuesta nada, tarda segundos y se puede volver a correr mañana.

## La regla que este repositorio se impone a si mismo

> Un medidor nuevo tiene que reproducir casos ya verificados a mano antes de que
> se publique su resultado.

Ya paso tres veces que un numero falso se citara despues como un hecho. Por eso
cada detector declara **casos conocidos** que tiene que encontrar, y el programa
**se niega a informar** si no los encuentra.

    python herramientas/auditar.py            # el informe
    python herramientas/auditar.py --detalle  # con cada coincidencia
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
API = RAIZ / "apps" / "api" / "app"
WEB = RAIZ / "apps" / "web"


@dataclass
class Deteccion:
    donde: str
    que: str
    detalle: str = ""


@dataclass
class Detector:
    nombre: str
    explica: str
    #: Lo que tiene que encontrar si funciona. Si falla, no se publica nada.
    casos_conocidos: list[str] = field(default_factory=list)
    #: Lo que **no** debe marcar: falsos positivos ya verificados a mano.
    #:
    #: Tan importante como la otra lista. Un detector que marca de mas se
    #: aprende a ignorar, y entonces deja de servir aunque a veces acierte.
    no_debe_marcar: list[str] = field(default_factory=list)
    hallazgos: list[Deteccion] = field(default_factory=list)

    def comprobar(self) -> str | None:
        """`None` si reprodujo sus casos conocidos; si no, que le falto."""
        encontrados = {h.donde + " " + h.que for h in self.hallazgos}
        problemas = [
            f"no encontro {c}"
            for c in self.casos_conocidos
            if not any(c in e for e in encontrados)
        ]
        problemas += [
            f"marca de mas {c}"
            for c in self.no_debe_marcar
            if any(c in e for e in encontrados)
        ]
        return "; ".join(problemas) if problemas else None


def _archivos(raiz: Path, patron: str, excluir: tuple[str, ...] = ()) -> list[Path]:
    salida = []
    for p in raiz.rglob(patron):
        partes = set(p.parts)
        if partes & {"node_modules", ".next", ".venv", ".venv-doc", "__pycache__", ".git"}:
            continue
        if any(e in str(p) for e in excluir):
            continue
        salida.append(p)
    return salida


# ── 1. Endpoints que el frontend nunca llama ────────────────────────────────


def endpoints_sin_llamador() -> Detector:
    """Rutas de la API que no aparecen en ninguna parte de `apps/web`.

    **No todas son un defecto.** Hay endpoints legitimos que solo consume una
    tarea programada, un webhook o una integracion. Lo que esto entrega es la
    lista para mirar, no una acusacion — el CRM tenia 28 operaciones y la
    interfaz llamaba a dos, y eso solo se vio contandolo.

    Se compara por el **prefijo estatico** de la ruta, porque el frontend arma
    los identificadores con plantillas: `/obligations/${id}` no contiene el
    literal `/obligations/{obligation_id}`.
    """
    d = Detector(
        nombre="endpoints que el frontend nunca llama",
        explica=(
            "Una operacion que nadie invoca es trabajo hecho que el producto no "
            "ofrece. Ojo: algunas son legitimas (tareas, webhooks)."
        ),
        # `/gestor/clientes` se agrego el 4-sep y la pantalla `/gestores` sigue
        # pidiendo `/contracts/`: verificado a mano leyendo `gestores-store.tsx`.
        casos_conocidos=["/gestor/clientes"],
    )

    rutas = set()
    for archivo in _archivos(API / "routers", "*.py"):
        texto = archivo.read_text(encoding="utf-8", errors="replace")
        prefijo = ""
        m = re.search(r'APIRouter\((?:[^)]*?)prefix="([^"]+)"', texto, re.S)
        if m:
            prefijo = m.group(1)
        for m in re.finditer(r'@router\.(get|post|patch|put|delete)\(\s*\n?\s*"([^"]*)"', texto):
            rutas.add((prefijo + m.group(2), archivo.name))

    texto_web = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in _archivos(WEB, "*.ts") + _archivos(WEB, "*.tsx")
    )

    for ruta, archivo in sorted(rutas):
        # El prefijo estatico: todo hasta el primer parametro de camino.
        estatico = ruta.split("{")[0].rstrip("/")
        if not estatico or estatico == "":
            continue
        if estatico not in texto_web:
            d.hallazgos.append(Deteccion(donde=archivo, que=ruta))
    return d


# ── 2. Funciones de servicio que nadie llama ────────────────────────────────


def servicios_sin_llamador() -> Detector:
    """Funciones publicas de `app/services/` sin una sola referencia fuera.

    Es la forma exacta de `bcn.sincronizar()` y `control_documental.py`:
    escritas, probadas y sin llamador. Las pruebas no lo detectan porque las
    pruebas **si** las llaman — por eso aca los tests no cuentan como llamador.
    """
    d = Detector(
        nombre="funciones de servicio que solo llaman las pruebas",
        explica=(
            "Escritas, probadas y sin llamador en la aplicacion. Es el patron "
            "que ya aparecio tres veces en este repositorio."
        ),
        casos_conocidos=["control_documental.py validar_sirve_como_evidencia"],
        # **La primera version marcaba estas tres y era falso**: las llama otra
        # funcion del MISMO archivo, y el detector excluia el propio archivo de
        # la busqueda. Se cazo porque `tasa_de_cierre()` la llama `construir()`
        # veinte lineas mas abajo, y eso lo escribi yo el dia anterior.
        #
        # Si vuelven a aparecer, el detector volvio a contar mal y su cifra no
        # se publica.
        no_debe_marcar=[
            "informe_de_auditoria.py tasa_de_cierre",
            "crm.py primera_etapa",
            "despacho.py validar_destinatario",
        ],
    )

    codigo_app = {}
    for archivo in _archivos(API, "*.py"):
        codigo_app[archivo] = archivo.read_text(encoding="utf-8", errors="replace")

    for archivo, texto in codigo_app.items():
        if archivo.parent.name != "services":
            continue
        try:
            arbol = ast.parse(texto)
        except SyntaxError:
            continue
        for nodo in arbol.body:
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if nodo.name.startswith("_"):
                continue
            usos = 0
            for otro, otro_texto in codigo_app.items():
                encontrados = len(re.findall(rf"\b{re.escape(nodo.name)}\b", otro_texto))
                # En su propio archivo, una de las apariciones es el `def`.
                # **Restarla es todo el arreglo**: sin esto, cualquier funcion
                # auxiliar usada por su vecina salia marcada como huerfana, y
                # el detector marcaba 29 cosas de las que la mayoria eran falsas.
                if otro == archivo:
                    encontrados -= 1
                usos += encontrados
            if usos == 0:
                d.hallazgos.append(
                    Deteccion(
                        donde=f"services/{archivo.name}",
                        que=f"{nodo.name}()",
                        detalle=f"linea {nodo.lineno}",
                    )
                )
    return d


# ── 3. Pantallas que leen datos de ejemplo ──────────────────────────────────


def frontend_con_mocks() -> Detector:
    """Codigo de produccion del frontend que importa de `mocks/`.

    Ya paso con las tres pantallas ISO: leian `mocks/` **sin hacer una sola
    peticion**, mientras la API tenia CRUD completo. Y con el selector de
    plantas, que ofrecia identificadores de ejemplo y hacia fallar la escritura
    con un 422 incomprensible.

    Un respaldo de ejemplo no siempre esta mal, pero **siempre hay que saber que
    esta**: quien ve "Procedimiento - Vigente" asume que existe.
    """
    d = Detector(
        nombre="frontend que importa datos de ejemplo",
        explica=(
            "Una pantalla que cae a `mocks/` muestra algo que no existe en la "
            "base, y se ve igual que si existiera."
        ),
        # Verificado a mano el 6-sep: la pantalla del calendario importa
        # `mockUsers` para resolver los nombres de los responsables.
        casos_conocidos=["calendario/page.tsx mocks/users"],
    )
    for archivo in _archivos(WEB, "*.tsx") + _archivos(WEB, "*.ts"):
        if ".test." in archivo.name or "/mocks/" in str(archivo).replace("\\", "/"):
            continue
        texto = archivo.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"from ['\"](?:@/)?(?:\.\./)*mocks/([\w./-]+)['\"]", texto):
            d.hallazgos.append(
                Deteccion(
                    donde=str(archivo.relative_to(WEB)).replace("\\", "/"),
                    que=f"mocks/{m.group(1)}",
                )
            )
    return d


# ── 4. Fechas medidas en horas ──────────────────────────────────────────────


def fechas_en_horas() -> Detector:
    """Aritmetica que suma horas donde el dominio cuenta dias de calendario.

    Mordio tres veces en un solo dia:

    - La banda de +-12 h del cron: **cero avisos**, siempre.
    - `date.today()` en la vigencia de un contrato: la base va en UTC y el host
      en hora de Chile, asi que pasadas las 20:00 estan en dias distintos.
    - `now() + interval '7 days'` en seis pruebas: Chile cambia de hora el
      primer sabado de septiembre y 168 horas caen un dia despues.

    `date.today()` no es "hoy": es "hoy donde corre este proceso".
    """
    d = Detector(
        nombre="fechas de calendario medidas en horas",
        explica=(
            "Sumar 24 h no es 'un dia' cuando hay husos o cambio de hora. Usar "
            "`services/husos.py::hoy_de`, que pregunta el huso de la empresa."
        ),
        # Verificado a mano: `_plantilla_de` filtra la vigencia de la plantilla
        # con `date.today()`, o sea con el reloj del proceso y no con el huso de
        # la empresa.
        casos_conocidos=["avisos_de_vencimiento.py date.today()"],
    )
    patrones = [
        (r"\bdate\.today\(\)", "date.today()"),
        (r"\bdatetime\.now\(\)(?!\s*\.astimezone)", "datetime.now() sin huso"),
        (r"timedelta\(days=", "timedelta(days=...)"),
        (r"interval '\d+ days'", "interval 'N days'"),
        (r"make_interval\(days", "make_interval(days=>...)"),
    ]
    for archivo in _archivos(API, "*.py"):
        if "tareas" not in str(archivo) and "services" not in str(archivo) and "routers" not in str(archivo):
            continue
        texto = archivo.read_text(encoding="utf-8", errors="replace")
        for patron, etiqueta in patrones:
            for m in re.finditer(patron, texto):
                linea = texto[: m.start()].count("\n") + 1
                d.hallazgos.append(
                    Deteccion(
                        donde=str(archivo.relative_to(API)).replace("\\", "/"),
                        que=etiqueta,
                        detalle=f"linea {linea}",
                    )
                )
    return d


# ── 5. Columnas que ninguna respuesta expone ────────────────────────────────


def columnas_invisibles() -> Detector:
    """Campos del modelo que ningun schema Pydantic devuelve.

    Es el sintoma que tuvo el control documental: las siete columnas del ciclo
    de vida existian, se escribian, y **no salian en ninguna respuesta** — asi
    que ni siquiera se podia distinguir un borrador de lo que rige.

    Se ignoran las columnas de infraestructura (`created_at`, `tenant_id`...),
    que legitimamente no se exponen en todas partes.
    """
    d = Detector(
        nombre="columnas del modelo que ninguna respuesta expone",
        explica=(
            "Se escriben y no se pueden leer. El dato existe en la base y es "
            "invisible para quien usa el producto."
        ),
    )
    ignorar = {
        "id", "tenant_id", "created_at", "created_by", "updated_at",
        "updated_by", "deleted_at", "metadata_",
    }
    esquemas = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in _archivos(API / "schemas", "*.py")
    )
    for archivo in _archivos(API / "models", "*.py"):
        texto = archivo.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"^\s{4}(\w+):\s*Mapped\[", texto, re.M):
            campo = m.group(1)
            if campo in ignorar:
                continue
            if not re.search(rf"^\s+{re.escape(campo)}\s*:", esquemas, re.M):
                linea = texto[: m.start()].count("\n") + 1
                d.hallazgos.append(
                    Deteccion(
                        donde=f"models/{archivo.name}",
                        que=campo,
                        detalle=f"linea {linea}",
                    )
                )
    return d


DETECTORES = [
    endpoints_sin_llamador,
    servicios_sin_llamador,
    frontend_con_mocks,
    fechas_en_horas,
    columnas_invisibles,
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detalle", action="store_true", help="lista cada coincidencia")
    parser.add_argument("--solo", help="corre un detector por nombre parcial")
    args = parser.parse_args(argv)

    fallo_la_guarda = False
    for hacer in DETECTORES:
        d = hacer()
        if args.solo and args.solo not in d.nombre:
            continue

        falta = d.comprobar()
        print()
        print("=" * 78)
        print(f"{d.nombre.upper()}  —  {len(d.hallazgos)} coincidencias")
        print("=" * 78)
        print(d.explica)

        if falta:
            # **No se publica el numero.** Un detector que no reproduce lo que
            # ya se verifico a mano esta midiendo otra cosa, y su cifra se
            # citaria despues como un hecho.
            print()
            print(f"  !! NO REPRODUJO SUS CASOS CONOCIDOS: {falta}")
            print("  !! El resultado de este detector NO es confiable.")
            fallo_la_guarda = True
            continue

        if d.casos_conocidos:
            print(f"(reproduce sus {len(d.casos_conocidos)} casos verificados a mano)")

        if args.detalle:
            print()
            por_donde: dict[str, list[Deteccion]] = {}
            for h in d.hallazgos:
                por_donde.setdefault(h.donde, []).append(h)
            for donde in sorted(por_donde):
                cosas = por_donde[donde]
                print(f"  {donde}  ({len(cosas)})")
                for h in cosas[:12]:
                    sufijo = f"  [{h.detalle}]" if h.detalle else ""
                    print(f"      {h.que}{sufijo}")
                if len(cosas) > 12:
                    print(f"      ... y {len(cosas) - 12} mas")

    print()
    return 1 if fallo_la_guarda else 0


if __name__ == "__main__":
    sys.exit(main())
