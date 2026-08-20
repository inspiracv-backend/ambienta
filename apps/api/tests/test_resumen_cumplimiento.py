"""El porcentaje de cumplimiento: que entra al denominador y que no (#109).

Este numero es el que la empresa muestra ante un fiscalizador, asi que las
pruebas no comprueban "que devuelva algo": comprueban **la aritmetica exacta**
sobre un conteo armado a mano, donde cada estado esta puesto a proposito.

Lo que mas facil se rompe sin que nadie lo note es el denominador. Un cambio
que meta `not_applicable` al conteo, o que ignore la exclusion de RF-24, no
tumba ninguna pantalla: solo hace que el porcentaje mienta. Por eso cada regla
tiene su propia prueba y su propio numero esperado.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.resumen_cumplimiento import Conteo, cuenta_para_el_calculo, resumir

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
TENANT = uuid.UUID("a0000000-0000-0000-0000-000000000001")

#: Mismo motivo que en `test_sincronizar_matriz`: `uq_matrices_periodo` choca
#: con la matriz sembrada si se usa el ano en curso.
ANO_DE_PRUEBA = 2098

EXCLUIDO = '{"incluidoEnCalculo": false}'


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    sesion = Session(bind=conexion)
    sesion.execute(text("SET LOCAL ROLE ambienta_app"))
    sesion.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(TENANT)}
    )
    try:
        yield sesion
    finally:
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


def _articulos(db: Session, cuantos: int):
    """Una norma vigente con exactamente `cuantos` articulos, sembrados aca.

    **El arnes siembra su propio articulado en vez de buscarlo.** El catalogo
    tiene cuatro articulos repartidos en dos normas, asi que pedir "una norma
    con cinco" se saltaba la prueba — y una prueba saltada se lee igual que una
    que pasa en el resumen de pytest. Justo las dos que verifican la aritmetica
    completa eran las que no corrian.

    Devuelve tambien la version: `matrix_norms.selected_version_id` es NOT NULL
    —la matriz guarda **contra que texto** se evaluo, no solo que norma.
    """
    fila = db.execute(
        text(
            "SELECT norm_id, id FROM legal_norm_versions "
            "WHERE is_current AND deleted_at IS NULL LIMIT 1"
        )
    ).first()
    if fila is None:
        pytest.skip("Sin versiones de norma vigentes en el catalogo")
    norm_id, version_id = fila

    arts = [
        db.execute(
            text(
                "INSERT INTO legal_articles "
                "(norm_version_id, article_number, content, display_order) "
                "VALUES (:v, :n, 'Articulo de prueba', :o) RETURNING id"
            ),
            {"v": version_id, "n": f"P-{uuid.uuid4().hex[:8]}", "o": 9000 + i},
        ).scalar_one()
        for i in range(cuantos)
    ]
    return norm_id, version_id, arts


def _matriz(
    db: Session,
    estados: list[tuple[str, bool]],
    facility_id=None,
    ano: int = ANO_DE_PRUEBA,
) -> uuid.UUID:
    """Una matriz con una norma y un articulo por cada `(estado, incluido)`.

    El conteo esperado se escribe en cada prueba, no se calcula aca: una prueba
    que deriva su esperado del mismo dato que verifica pasa siempre.
    """
    norm_id, version_id, arts = _articulos(db, len(estados))
    matrix_id, mn_id = uuid.uuid4(), uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO tenant_legal_matrices (id, tenant_id, name, period_year) "
            "VALUES (:i, :t, 'Matriz de resumen', :a)"
        ),
        {"i": matrix_id, "t": TENANT, "a": ano},
    )
    db.execute(
        text(
            "INSERT INTO matrix_norms "
            "(id, tenant_id, matrix_id, norm_id, selected_version_id, applicability) "
            "VALUES (:i, :t, :m, :n, :v, 'applicable')"
        ),
        {"i": mn_id, "t": TENANT, "m": matrix_id, "n": norm_id, "v": version_id},
    )
    for art, (estado, incluido) in zip(arts, estados):
        db.execute(
            text(
                "INSERT INTO article_compliance "
                "(tenant_id, matrix_norm_id, article_id, facility_id, "
                " compliance_status, attributes) "
                "VALUES (:t, :mn, :a, :f, :s, CAST(:at AS jsonb))"
            ),
            {
                "t": TENANT,
                "mn": mn_id,
                "a": art,
                "f": facility_id,
                "s": estado,
                "at": "{}" if incluido else EXCLUIDO,
            },
        )
    return matrix_id


class TestQueCuentaParaElCalculo:
    """RF-24. Ausente significa incluido; solo `false` excluye."""

    def test_sin_attributes_cuenta(self) -> None:
        assert cuenta_para_el_calculo(None) is True

    def test_vacio_cuenta(self) -> None:
        assert cuenta_para_el_calculo({}) is True

    def test_solo_false_excluye(self) -> None:
        assert cuenta_para_el_calculo({"incluidoEnCalculo": False}) is False

    def test_true_explicito_cuenta(self) -> None:
        assert cuenta_para_el_calculo({"incluidoEnCalculo": True}) is True

    def test_attributes_con_basura_no_tumba_el_calculo(self) -> None:
        """Una clave rara no debe sacar el articulo del conteo.

        Es un cajon sin esquema en la base: si cualquier cosa excluyera, un dato
        viejo bajaria el porcentaje sin que nadie entienda por que.
        """
        assert cuenta_para_el_calculo({"otraCosa": "x"}) is True
        assert cuenta_para_el_calculo("texto suelto") is True


class TestElDenominador:
    def test_sin_articulos_el_porcentaje_es_none_no_cero(self) -> None:
        """Cero significa "no cumple nada". `None` significa "no hay nada que medir"."""
        assert Conteo().porcentaje is None

    def test_parcial_cuenta_como_no_cumplido(self) -> None:
        c = Conteo()
        c.sumar("partial", incluido=True)
        c.sumar("compliant", incluido=True)
        assert c.no_cumplen == 1
        assert c.porcentaje == 50.0

    def test_pendiente_cuenta_en_el_denominador(self) -> None:
        """Sin evaluar no es cumplir: si no, quien no evaluo nada daria 100 %."""
        c = Conteo()
        c.sumar("compliant", incluido=True)
        c.sumar("pending", incluido=True)
        assert c.evaluables == 2
        assert c.porcentaje == 50.0

    def test_no_aplicable_sale_del_denominador(self) -> None:
        """No es una obligacion de la empresa; contarla la penalizaria."""
        c = Conteo()
        c.sumar("compliant", incluido=True)
        c.sumar("not_applicable", incluido=True)
        assert c.evaluables == 1
        assert c.no_aplican == 1
        assert c.porcentaje == 100.0

    def test_excluido_sale_del_denominador_sea_cual_sea_su_estado(self) -> None:
        c = Conteo()
        c.sumar("non_compliant", incluido=False)
        c.sumar("compliant", incluido=True)
        assert c.excluidos == 1
        assert c.evaluables == 1
        assert c.porcentaje == 100.0


class TestResumenSobreLaBase:
    def test_los_cinco_estados_dan_el_porcentaje_esperado(self, db: Session) -> None:
        """2 cumplen de 4 evaluables: `not_applicable` no entra, `partial` no cumple."""
        matrix_id = _matriz(
            db,
            [
                ("compliant", True),
                ("compliant", True),
                ("non_compliant", True),
                ("partial", True),
                ("not_applicable", True),
            ],
        )

        r = resumir(db, matrix_id)

        assert (r.total.cumplen, r.total.no_cumplen) == (2, 2)
        assert r.total.no_aplican == 1
        assert r.total.evaluables == 4
        assert r.total.porcentaje == 50.0

    def test_excluir_un_articulo_mueve_el_porcentaje(self, db: Session) -> None:
        """La prueba de que #108 no es decorativo.

        Sin esto se podria marcar "excluir del calculo" en la pantalla y el
        numero no cambiaria — que es exactamente lo que hacia
        `get_compliance_stats` antes de este cambio.
        """
        base = _matriz(db, [("compliant", True), ("non_compliant", True)])
        assert resumir(db, base).total.porcentaje == 50.0

        # El mismo par, con el incumplido fuera del calculo.
        excluido = _matriz(
            db, [("compliant", True), ("non_compliant", False)], ano=ANO_DE_PRUEBA + 3
        )
        r = resumir(db, excluido)
        assert r.total.excluidos == 1
        assert r.total.evaluables == 1
        assert r.total.porcentaje == 100.0

    def test_el_desglose_por_norma_suma_lo_mismo_que_el_total(self, db: Session) -> None:
        matrix_id = _matriz(
            db, [("compliant", True), ("non_compliant", True), ("pending", True)]
        )

        r = resumir(db, matrix_id)

        assert len(r.por_norma) == 1
        assert r.por_norma[0].conteo.evaluables == r.total.evaluables
        assert r.por_norma[0].title != ""
        assert r.por_norma[0].applicability == "applicable"

    def test_sin_planta_se_agrupa_como_toda_la_empresa(self, db: Session) -> None:
        """`facility_id` nulo no es un dato faltante: es evaluacion a nivel empresa."""
        r = resumir(db, _matriz(db, [("compliant", True)]))

        assert len(r.por_instalacion) == 1
        assert r.por_instalacion[0].facility_id is None
        assert r.por_instalacion[0].nombre == "Toda la empresa"

    def test_con_planta_toma_su_nombre(self, db: Session) -> None:
        fila = db.execute(
            text("SELECT id, name FROM facilities WHERE deleted_at IS NULL LIMIT 1")
        ).first()
        if fila is None:
            pytest.skip("Sin instalaciones sembradas")

        r = resumir(db, _matriz(db, [("compliant", True)], facility_id=fila[0]))

        assert r.por_instalacion[0].facility_id == fila[0]
        assert r.por_instalacion[0].nombre == fila[1]

    def test_matriz_sin_normas_no_revienta_y_no_inventa_cero(self, db: Session) -> None:
        matrix_id = uuid.uuid4()
        db.execute(
            text(
                "INSERT INTO tenant_legal_matrices (id, tenant_id, name, period_year) "
                "VALUES (:i, :t, 'Vacia', :a)"
            ),
            {"i": matrix_id, "t": TENANT, "a": ANO_DE_PRUEBA + 1},
        )

        r = resumir(db, matrix_id)

        assert r.por_norma == []
        assert r.total.porcentaje is None

    def test_una_norma_sin_articulos_aparece_pero_no_suma(self, db: Session) -> None:
        """Que este en la matriz y sin evaluar es informacion, no un hueco."""
        matrix_id, mn_id = uuid.uuid4(), uuid.uuid4()
        norm_id, version_id, _ = _articulos(db, 1)
        db.execute(
            text(
                "INSERT INTO tenant_legal_matrices (id, tenant_id, name, period_year) "
                "VALUES (:i, :t, 'Sin articulos', :a)"
            ),
            {"i": matrix_id, "t": TENANT, "a": ANO_DE_PRUEBA + 2},
        )
        db.execute(
            text(
                "INSERT INTO matrix_norms "
                "(id, tenant_id, matrix_id, norm_id, selected_version_id, applicability) "
                "VALUES (:i, :t, :m, :n, :v, 'applicable')"
            ),
            {"i": mn_id, "t": TENANT, "m": matrix_id, "n": norm_id, "v": version_id},
        )

        r = resumir(db, matrix_id)

        assert len(r.por_norma) == 1
        assert r.por_norma[0].conteo.evaluables == 0
        assert r.total.porcentaje is None

    def test_el_borrado_logico_no_entra_al_conteo(self, db: Session) -> None:
        matrix_id = _matriz(db, [("compliant", True), ("non_compliant", True)])
        db.execute(
            text(
                "UPDATE article_compliance SET deleted_at = now() "
                "WHERE compliance_status = 'non_compliant' AND matrix_norm_id IN "
                "(SELECT id FROM matrix_norms WHERE matrix_id = :m)"
            ),
            {"m": matrix_id},
        )

        r = resumir(db, matrix_id)

        assert r.total.evaluables == 1
        assert r.total.porcentaje == 100.0


class TestStatsUsaElMismoCalculo:
    """`/stats` y `/resumen` no pueden dar numeros distintos.

    Eran dos calculos separados del mismo dato, y el viejo estaba mal: ignoraba
    la exclusion de RF-24 y metia `partial` con `pending`. Arreglar la copia
    habria dejado dos implementaciones que se desincronizan sin aviso, asi que
    `get_compliance_stats` delega. Esta prueba es lo que impide que alguien
    vuelva a separarlos.
    """

    def test_stats_coincide_con_el_resumen(self, db: Session) -> None:
        from app.services.compliance import get_compliance_stats

        matrix_id = _matriz(
            db,
            [
                ("compliant", True),
                ("non_compliant", True),
                ("partial", True),
                ("not_applicable", True),
                ("pending", True),
                ("non_compliant", False),
            ],
        )

        s = get_compliance_stats(db, matrix_id)
        r = resumir(db, matrix_id)

        assert s["compliance_percentage"] == r.total.porcentaje
        assert s["compliant"] == r.total.cumplen
        assert s["non_compliant"] == r.total.no_cumplen
        assert s["evaluable_articles"] == r.total.evaluables

    def test_stats_respeta_la_exclusion(self, db: Session) -> None:
        """La comprobacion de que RF-24 llega hasta el numero que se muestra."""
        from app.services.compliance import get_compliance_stats

        matrix_id = _matriz(db, [("compliant", True), ("non_compliant", False)])

        s = get_compliance_stats(db, matrix_id)

        assert s["excluded"] == 1
        assert s["total_articles"] == 2
        assert s["evaluable_articles"] == 1
        assert s["compliance_percentage"] == 100.0

    def test_partial_ya_no_se_confunde_con_sin_evaluar(self, db: Session) -> None:
        from app.services.compliance import get_compliance_stats

        matrix_id = _matriz(db, [("partial", True), ("pending", True)])

        s = get_compliance_stats(db, matrix_id)

        assert s["non_compliant"] == 1
        assert s["not_evaluated"] == 1


class TestLaRespuestaDelEndpoint:
    """Que el resumen sobreviva la serializacion, no solo el calculo.

    El servicio devuelve dataclasses y el endpoint arma modelos Pydantic: entre
    los dos hay un paso donde un campo renombrado o un `None` no declarado
    revienta en produccion y en ninguna prueba del servicio. Se llama a la
    funcion del router directo —sin cliente HTTP— porque lo que se verifica aca
    es la forma de la respuesta, no la autenticacion, que ya tiene sus pruebas.
    """

    def test_arma_el_modelo_completo(self, db: Session) -> None:
        from app.routers.compliance import resumen_de_la_matriz

        matrix_id = _matriz(
            db, [("compliant", True), ("partial", True), ("not_applicable", True)]
        )

        r = resumen_de_la_matriz(matrix_id, db=db)
        cuerpo = r.model_dump()

        assert cuerpo["total"]["porcentaje"] == 50.0
        assert cuerpo["total"]["evaluables"] == 2
        assert len(cuerpo["por_norma"]) == 1
        assert cuerpo["por_instalacion"][0]["nombre"] == "Toda la empresa"

    def test_porcentaje_nulo_sobrevive_la_serializacion(self, db: Session) -> None:
        """`None` tiene que llegar como `null`, no romper ni volverse cero."""
        from app.routers.compliance import resumen_de_la_matriz

        matrix_id = uuid.uuid4()
        db.execute(
            text(
                "INSERT INTO tenant_legal_matrices (id, tenant_id, name, period_year) "
                "VALUES (:i, :t, 'Vacia', :a)"
            ),
            {"i": matrix_id, "t": TENANT, "a": ANO_DE_PRUEBA + 5},
        )

        assert resumen_de_la_matriz(matrix_id, db=db).total.porcentaje is None

    def test_matriz_inexistente_da_404(self, db: Session) -> None:
        from fastapi import HTTPException

        from app.routers.compliance import resumen_de_la_matriz

        with pytest.raises(HTTPException) as exc:
            resumen_de_la_matriz(uuid.uuid4(), db=db)
        assert exc.value.status_code == 404


class TestLosTresNumerosNoSeContradicen:
    """La pantalla y el resumen calculaban lo mismo con denominadores distintos.

    Una empresa con un articulo cumplido y diecinueve sin evaluar veia **100 %**
    en la matriz y **5 %** en el resumen. Los dos eran correctos y respondian
    preguntas distintas; el problema era que salian de dos calculos separados,
    asi que nadie podia saber cual mirar.

    Ahora los tres salen del mismo conteo, ligados por una identidad que se
    comprueba aca: **el conservador es el producto de los otros dos, sobre las
    razones sin redondear**. Si alguien cambia un denominador, estas pruebas lo
    dicen.

    Sobre los porcentajes publicados la identidad **no** se sostiene, y eso
    tambien esta fijado abajo: el redondeo por separado desvia hasta 0,14
    puntos, y con nada evaluado el producto queda indefinido.
    """

    def test_el_conservador_es_el_producto_de_los_otros_dos(self) -> None:
        c = Conteo()
        c.sumar("compliant", incluido=True)
        for _ in range(19):
            c.sumar("pending", incluido=True)

        assert c.porcentaje_sobre_evaluados == 100.0
        assert c.cobertura == 5.0
        assert c.porcentaje == 5.0
        assert c.razon_cumplimiento * c.razon_cobertura == pytest.approx(0.05)

    def test_el_producto_de_los_redondeados_NO_vuelve_al_tercero(self) -> None:
        """La identidad vale sobre las razones, **no sobre lo que se publica**.

        El docstring de este modulo llego a decir "salvo una decima". Es falso:
        el error de redondeo se acumula hasta 0,14 puntos. Esta prueba fija el
        contraejemplo para que nadie vuelva a escribir la tolerancia.
        """
        c = Conteo(cumplen=57, no_cumplen=22, sin_evaluar=1)

        assert (c.porcentaje, c.porcentaje_sobre_evaluados, c.cobertura) == (
            71.2,
            72.2,
            98.8,
        )
        desvio = abs(c.porcentaje_sobre_evaluados * c.cobertura / 100 - c.porcentaje)
        assert desvio > 0.1
        # Sobre las razones si cierra.
        assert c.razon_cumplimiento * c.razon_cobertura == pytest.approx(57 / 80)

    def test_con_nada_evaluado_el_producto_queda_indefinido(self) -> None:
        """**Las guardas son asimetricas y hay que saberlo.**

        Con articulos que cumplir y ninguno evaluado —una matriz recien
        generada— `porcentaje_sobre_evaluados` es `None` mientras los otros dos
        valen 0,0. Un cliente que multiplique para derivar el tercero revienta
        justo en el estado mas comun de una empresa nueva.
        """
        c = Conteo(sin_evaluar=10)

        assert c.porcentaje_sobre_evaluados is None
        assert c.porcentaje == 0.0
        assert c.cobertura == 0.0

    def test_la_identidad_se_mantiene_con_los_cinco_estados(self) -> None:
        c = Conteo()
        for estado, incluido in [
            ("compliant", True),
            ("compliant", True),
            ("non_compliant", True),
            ("partial", True),
            ("pending", True),
            ("pending", True),
            ("not_applicable", True),
            ("compliant", False),
        ]:
            c.sumar(estado, incluido)

        assert (c.evaluados, c.evaluables) == (4, 6)
        assert c.porcentaje_sobre_evaluados == 50.0
        # **La identidad se comprueba sobre las razones, no sobre los
        # porcentajes publicados.** Los tres se redondean por separado, asi que
        # el producto de dos redondeados no vuelve al tercero.
        assert c.razon_cumplimiento * c.razon_cobertura == pytest.approx(
            c.cumplen / c.evaluables
        )

    def test_sin_evaluar_nada_el_cumplimiento_es_none_y_la_cobertura_cero(self) -> None:
        """Distintos a proposito: no hay respuesta a "cuanto cumplimos", pero si
        a "cuanto revisamos" — y la respuesta es cero, que es un dato."""
        c = Conteo()
        for _ in range(3):
            c.sumar("pending", incluido=True)

        assert c.porcentaje_sobre_evaluados is None
        assert c.cobertura == 0.0
        assert c.porcentaje == 0.0

    def test_la_cobertura_no_esconde_lo_excluido(self) -> None:
        """Excluir del cumplimiento es legitimo; esconder que nadie lo miro, no.

        Aun asi el excluido sale de los dos denominadores: si contara en la
        cobertura, excluir un articulo bajaria la cobertura sin que nadie dejara
        de revisar nada. Lo que la prueba fija es que **la exclusion no inventa
        cobertura tampoco**.
        """
        c = Conteo()
        c.sumar("compliant", incluido=True)
        c.sumar("pending", incluido=True)
        c.sumar("pending", incluido=False)

        assert c.excluidos == 1
        assert c.evaluables == 2
        assert c.cobertura == 50.0

    def test_el_endpoint_devuelve_los_tres(self, db: Session) -> None:
        from app.routers.compliance import resumen_de_la_matriz

        matrix_id = _matriz(db, [("compliant", True), ("pending", True)])

        cuerpo = resumen_de_la_matriz(matrix_id, db=db).model_dump()["total"]

        assert cuerpo["porcentaje_sobre_evaluados"] == 100.0
        assert cuerpo["cobertura"] == 50.0
        assert cuerpo["porcentaje"] == 50.0
