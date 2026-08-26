"""Que el catalogo salga de la BCN de verdad, y se pueda listar (RF-17).

## Lo que estaba mal

`services/bcn.py` sabia buscar y guardar desde el 25-ago. **Nadie la llamaba:**
ni router ni tarea. La sincronizacion se corrio una vez desde un script suelto y
el dato no sobrevivio — medido antes de escribir esto: las 8 normas del catalogo
tenian `last_source_sync_at` en `nunca`, y la Ley 19.300 tenia **2 articulos**,
no los 151 que afirmaba CLAUDE.md.

Es el mismo patron que tuvo `audit_log`: la pieza lista, sin nadie que la use, y
un numero publicado que ya no era cierto.

## Los tres defectos que aparecieron al medirlo

1. **`buscar()` no deduplicaba.** De 5 filas por la Ley 19.300, **4 eran la
   misma norma**. Y el `LIMIT` de SPARQL cuenta filas, no normas.
2. **La adopcion no reconocia los decretos.** El seed escribe `148/2003` y la
   BCN devuelve `148`: de 8 normas clasificadas, **6 se habrian duplicado**,
   dejando la clasificacion por sector pegada a la copia falsa.
3. **Los decretos supremos se guardaban como resolucion.** La BCN usa `dto` en
   la URI, y el mapa de tipos solo conocia `ds` y `decreto`. Nueve normas mal
   tipadas, sin ningun error.

Ninguno de los tres fallaba. Los tres mentian.

## La mutacion que sobrevivio, y por que no es un hueco

Romper la comparacion de `buscar()` —dejar `previa = None` y `if True`— **no
hizo fallar nada**, y la primera lectura fue "falta cobertura". Es al reves: esa
mutacion no cambia el comportamiento. La deduplicacion no la hace la
comparacion, la hace el diccionario: `por_codigo[codigo] = candidata` sigue
pisando por clave. Lo unico que se pierde es *cual* de las filas gana, y eso ya
lo cubre `test_al_deduplicar_gana_la_fila_con_mas_datos`.

La mutacion efectiva es devolver la lista con duplicados, y **esa si se detecta**
—por dos pruebas—. Vale anotarlo porque un superviviente mal leido se arregla
escribiendo una prueba que no comprueba nada.
"""
from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services import bcn
from app.tareas.sincronizar_bcn import TERMINOS

URL_ADMIN = os.getenv(
    "DATABASE_ADMIN_URL",
    "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
)


@pytest.fixture
def db():
    engine = create_engine(URL_ADMIN)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    sesion = Session(bind=conexion)
    try:
        yield sesion
    finally:
        # Siempre `rollback`: el catalogo es global y lo comparten todas las
        # empresas y el resto de la suite.
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


def _fuente_y_pais(db: Session) -> tuple[int, int]:
    return (
        db.execute(
            text("SELECT id FROM legal_sources WHERE code = 'BCN_LEYCHILE'")
        ).scalar_one(),
        db.execute(text("SELECT id FROM countries WHERE name = 'Chile'")).scalar_one(),
    )


def _sembrar(db: Session, numero: str) -> None:
    """Una norma como la deja el seed: sin identificador externo."""
    fuente, pais = _fuente_y_pais(db)
    db.execute(
        text(
            "INSERT INTO legal_norms "
            "(country_id, source_id, norm_type, norm_number, title, status) "
            "VALUES (:p, :f, 'decreto_supremo', :n, 'SEMBRADA', 'vigente')"
        ),
        {"p": pais, "f": fuente, "n": numero},
    )


def _norma_bcn(numero: str, *, anio: int | None, tipo: str = "dto") -> bcn.NormaBCN:
    return bcn.NormaBCN(
        uri=f"http://datos.bcn.cl/recurso/cl/{tipo}/org/2000-01-01/{numero}",
        leychile_code=f"c{uuid.uuid4().hex[:10]}",
        tipo=tipo,
        numero=numero,
        titulo=f"NORMA {numero}",
        organismo="org",
        publicacion=None,
        promulgacion=date(anio, 5, 30) if anio else None,
    )


class TestAdoptarLosDecretos:
    """El defecto que habria duplicado 6 de las 8 normas clasificadas."""

    def test_el_seed_usa_numero_barra_anio_y_la_bcn_solo_el_numero(
        self, db: Session
    ) -> None:
        """**El caso que fallaba.** `148/2003` contra `148` no son iguales como
        texto, y comparandolos asi solo calzaban las dos leyes."""
        numero = uuid.uuid4().hex[:6]
        _sembrar(db, f"{numero}/2003")

        r = bcn.sincronizar(
            db, [_norma_bcn(numero, anio=2003)], con_texto=False
        )

        assert r.adoptadas == 1, "No reconocio el decreto sembrado con su anio"
        assert r.nuevas == 0, "Creo una fila al lado en vez de adoptar"

    def test_el_mismo_numero_de_OTRO_anio_no_se_adopta(self, db: Session) -> None:
        """**La negacion que importa mas que la adopcion.**

        Hay un DS 90 de 2000 y otros DS 90 de otros anos. Adoptar por numero a
        secas le cambiaria la identidad a una norma **ya clasificada**, y eso es
        peor que duplicarla: la clasificacion se quedaria apuntando a otra ley.
        """
        numero = uuid.uuid4().hex[:6]
        _sembrar(db, f"{numero}/2003")

        r = bcn.sincronizar(
            db, [_norma_bcn(numero, anio=2015)], con_texto=False
        )

        assert r.adoptadas == 0
        assert r.nuevas == 1, "Deberia entrar como norma distinta, que es lo que es"

    def test_sin_anio_no_se_adivina(self, db: Session) -> None:
        """Sin promulgacion no hay como desambiguar. Se prefiere una fila de mas
        a una identidad cambiada."""
        numero = uuid.uuid4().hex[:6]
        _sembrar(db, f"{numero}/2003")

        r = bcn.sincronizar(db, [_norma_bcn(numero, anio=None)], con_texto=False)

        assert r.adoptadas == 0

    def test_la_clasificacion_por_sector_sobrevive_a_la_adopcion(
        self, db: Session
    ) -> None:
        """**Es el punto entero de adoptar.**

        `norm_sectors` es trabajo humano y es lo que hace funcionar el CORE. Si
        la adopcion la perdiera, la matriz de las empresas se vaciaria sin
        ningun error a la vista.
        """
        numero = uuid.uuid4().hex[:6]
        _sembrar(db, f"{numero}/2003")
        norma_id = db.execute(
            text("SELECT id FROM legal_norms WHERE norm_number = :n"),
            {"n": f"{numero}/2003"},
        ).scalar_one()
        sector = db.execute(text("SELECT id FROM sectors LIMIT 1")).scalar_one()
        db.execute(
            text(
                "INSERT INTO norm_sectors (norm_id, sector_id, applicability_level) "
                "VALUES (:n, :s, 'directa')"
            ),
            {"n": norma_id, "s": sector},
        )

        bcn.sincronizar(db, [_norma_bcn(numero, anio=2003)], con_texto=False)

        sigue = db.execute(
            text("SELECT count(*) FROM norm_sectors WHERE norm_id = :n"),
            {"n": norma_id},
        ).scalar_one()
        assert sigue == 1, "La adopcion perdio la clasificacion por sector"


class TestElTipoDeNorma:
    """Nueve decretos supremos guardados como resolucion, sin ningun error."""

    def test_dto_es_decreto_supremo(self) -> None:
        """**`dto` es lo que usa la BCN**, no `ds` ni `decreto`.

        Medido: de 23 normas sincronizadas, 9 traen `/recurso/cl/dto/` y
        **ninguna** trae `ds` ni `decreto`. Sin esa entrada en el mapa, el RSEIA,
        el reglamento de residuos peligrosos y la norma de ruidos quedaban
        guardados como resoluciones.
        """
        assert bcn.TIPO_DE_NORMA["dto"] == "decreto_supremo"

    def test_el_tipo_sale_de_la_uri_y_no_del_rdf_type(self) -> None:
        """La Ley 19.300 **no declara** su tipo; una resolucion si. Confiar en el
        tipo declarado dejaba las leyes cayendo al valor por defecto."""
        assert (
            bcn._tipo_desde_uri(
                "http://datos.bcn.cl/recurso/cl/dto/org/2012-08-12/40", None
            )
            == "dto"
        )
        assert (
            bcn._tipo_desde_uri(
                "http://datos.bcn.cl/recurso/cl/ley/org/1994-03-09/19300", None
            )
            == "ley"
        )

    def test_guardar_un_dto_lo_deja_como_decreto_supremo(self, db: Session) -> None:
        """De punta a punta, no solo el mapa."""
        numero = uuid.uuid4().hex[:6]

        bcn.sincronizar(db, [_norma_bcn(numero, anio=2012, tipo="dto")], con_texto=False)

        guardado = db.execute(
            text("SELECT norm_type FROM legal_norms WHERE norm_number = :n"),
            {"n": numero},
        ).scalar_one()
        assert guardado == "decreto_supremo"


class TestLosTerminosDeLaTarea:
    """La lista de que traer. **Sin acentos, y cada uno con su norma.**"""

    def test_ningun_termino_lleva_letras_acentuadas(self) -> None:
        """**La trampa que devuelve cero sin error.**

        `FILTER(CONTAINS(LCASE(...)))` de SPARQL no normaliza tildes: buscar
        `"norma de emision para centrales termoelectricas"` devuelve **cero**
        porque el titulo dice `EMISIÓN` y `TERMOELÉCTRICAS`. Y cero se lee como
        "esa norma no esta en la BCN".
        """
        acentos = set("áéíóúüñÁÉÍÓÚÜÑ")
        for termino, _ in TERMINOS:
            assert not (set(termino) & acentos), (
                f"El termino {termino!r} lleva acentos: la busqueda de la BCN "
                f"distingue tildes y devolveria cero sin fallar"
            )

    def test_cada_termino_declara_que_norma_debe_encontrar(self) -> None:
        """El segundo valor **no es documentacion**: es lo que la tarea comprueba
        despues de cada busqueda, y lo que hace que un catalogo incompleto se
        note en vez de pasar por exito."""
        for termino, esperado in TERMINOS:
            assert esperado, f"{termino!r} no dice que norma tiene que traer"

    def test_estan_las_normas_del_seed_que_llevan_clasificacion(self) -> None:
        """Traer otras normas es opcional; **estas no**.

        Son las que tienen clasificacion por sector, o sea las unicas con las
        que el CORE puede proponer algo hoy.
        """
        numeros = {n for _, n in TERMINOS}
        assert {"19300", "20920", "148", "90", "38", "13", "40"} <= numeros


class TestQueBuscarNoRepitaLaMismaNorma:
    """De 5 filas por la Ley 19.300, **4 eran la misma norma**.

    Sin red: se sustituye la consulta y se le dan las filas duplicadas que
    devuelve SPARQL de verdad. Lo que se prueba es el tratamiento, no que la BCN
    responda — eso son las pruebas marcadas `red`.
    """

    def _fila(self, codigo, *, numero=None, organismo=None, tipo=None):
        f = {
            "norma": {"value": f"http://datos.bcn.cl/recurso/cl/ley/org/1994/{codigo}"},
            "codigo": {"value": codigo},
            "titulo": {"value": "APRUEBA LEY SOBRE BASES GENERALES"},
        }
        if numero:
            f["numero"] = {"value": numero}
        if organismo:
            f["organismo"] = {"value": f"http://x/{organismo}"}
        if tipo:
            f["tipo"] = {"value": f"http://x/norma/tipo#{tipo}"}
        return f

    def test_cuatro_filas_de_la_misma_norma_dan_una_sola(self, monkeypatch) -> None:
        """**El `LIMIT` de SPARQL cuenta filas, no normas.**

        Pedir 50 podia traer 8 distintas, y quien leyera el resultado creeria que
        en la BCN solo hay 8 que coinciden.
        """
        monkeypatch.setattr(
            bcn,
            "_consultar",
            lambda *a, **k: [
                self._fila("30667"),
                self._fila("30667", numero="19300"),
                self._fila("30667", organismo="segpres"),
                self._fila("30739", numero="19372"),
            ],
        )

        r = bcn.buscar("lo que sea", limite=10)

        assert [n.leychile_code for n in r] == ["30667", "30739"]

    def test_al_deduplicar_gana_la_fila_con_mas_datos(self, monkeypatch) -> None:
        """**Las copias no son identicas.**

        Cada una resolvio distintos `OPTIONAL`: unas traen el numero, otras el
        organismo. Quedarse con la primera perderia datos que si estaban.
        """
        monkeypatch.setattr(
            bcn,
            "_consultar",
            lambda *a, **k: [
                self._fila("30667"),  # la mas pobre llega primero
                self._fila("30667", numero="19300", organismo="segpres"),
            ],
        )

        r = bcn.buscar("lo que sea", limite=10)

        assert len(r) == 1
        assert r[0].numero == "19300"
        assert r[0].organismo == "segpres"

    def test_una_fila_sin_codigo_se_descarta(self, monkeypatch) -> None:
        """Sin identificador estable no se puede deduplicar **ni reconocerla la
        proxima corrida**: entraria de nuevo en cada sincronizacion."""
        monkeypatch.setattr(
            bcn,
            "_consultar",
            lambda *a, **k: [
                {"norma": {"value": "http://x/y"}, "titulo": {"value": "SIN CODIGO"}},
                self._fila("30667", numero="19300"),
            ],
        )

        r = bcn.buscar("lo que sea", limite=10)

        assert [n.leychile_code for n in r] == ["30667"]
