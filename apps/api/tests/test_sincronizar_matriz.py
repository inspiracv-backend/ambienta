"""Sincronizar la matriz: agrega, nunca borra (RF-19, RF-29).

Spec: `openspec/changes/normativa-aplicable-por-empresa/specs/normativa-aplicable/spec.md`.

La promesa de este servicio es que **correrlo no destruye trabajo**. Es facil
de romper sin notarlo —basta un `DELETE` "para dejar la matriz limpia"— y el
dano solo se ve cuando alguien busca la evaluacion de un periodo pasado y ya no
esta. Por eso el viaje completo esta cubierto: generar, evaluar, regenerar, y
comprobar que la evaluacion sigue ahi.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.sincronizar_matriz import (
    MOTIVO_YA_NO_APLICA,
    actualizar_a_version_vigente,
    desactualizadas,
    sincronizar,
)

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
TENANT = uuid.UUID("a0000000-0000-0000-0000-000000000001")


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
        # Rollback siempre: estas pruebas clasifican normas y generan matrices.
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


def _sector_manufactura(db: Session) -> int:
    sid = db.execute(text("SELECT id FROM sectors WHERE code = 'C'")).scalar()
    if sid is None:
        pytest.skip("Sin el sector CIIU C sembrado")
    return sid


def _norma_con_articulos(db: Session):
    """Una norma que tenga version vigente y articulado. Sin eso no hay que sembrar."""
    fila = db.execute(
        text(
            "SELECT v.norm_id FROM legal_norm_versions v "
            "JOIN legal_articles a ON a.norm_version_id = v.id "
            "WHERE v.is_current AND v.deleted_at IS NULL AND a.deleted_at IS NULL "
            "GROUP BY v.norm_id LIMIT 1"
        )
    ).scalar()
    if fila is None:
        pytest.skip("Sin normas con articulado vigente")
    return fila


#: Ano que no usa el seed. `uq_matrices_periodo` es UNIQUE sobre
#: (tenant, ano, planta, version) con NULLS NOT DISTINCT, asi que una matriz de
#: prueba en 2026 choca con la sembrada — y el fallo se lee como un error del
#: servicio cuando en realidad es del arnes.
ANO_DE_PRUEBA = 2099


def _matriz_vacia(db: Session) -> uuid.UUID:
    mid = uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO tenant_legal_matrices (id, tenant_id, name, period_year) "
            "VALUES (:i, :t, 'Matriz de prueba', :a)"
        ),
        {"i": mid, "t": TENANT, "a": ANO_DE_PRUEBA},
    )
    return mid


def _preparar(db: Session, nivel: str = "directa"):
    """Empresa con sector, una norma clasificada, y una matriz vacia."""
    sid = _sector_manufactura(db)
    norm_id = _norma_con_articulos(db)
    db.execute(
        text("UPDATE tenants SET sector_id = :s WHERE id = :t"), {"s": sid, "t": TENANT}
    )
    db.execute(text("DELETE FROM norm_sectors WHERE sector_id = :s"), {"s": sid})
    db.execute(
        text(
            "INSERT INTO norm_sectors (norm_id, sector_id, applicability_level, rationale) "
            "VALUES (:n, :s, :l, 'prueba de sincronizacion')"
        ),
        {"n": norm_id, "s": sid, "l": nivel},
    )
    return _matriz_vacia(db), norm_id, sid


def _evaluaciones(db: Session, matrix_id) -> int:
    return db.execute(
        text(
            "SELECT count(*) FROM article_compliance ac "
            "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
            "WHERE mn.matrix_id = :m"
        ),
        {"m": matrix_id},
    ).scalar_one()


class TestGeneracion:
    def test_crea_la_norma_y_sus_articulos_sin_evaluar(self, db: Session) -> None:
        matrix_id, _, _ = _preparar(db)

        r = sincronizar(db, matrix_id, TENANT)

        assert r.normas_agregadas == 1
        assert r.articulos_agregados > 0
        pendientes = db.execute(
            text(
                "SELECT count(*) FROM article_compliance ac "
                "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
                "WHERE mn.matrix_id = :m AND ac.compliance_status = 'pending'"
            ),
            {"m": matrix_id},
        ).scalar_one()
        assert pendientes == r.articulos_agregados

    def test_ninguno_entra_como_incumplido(self, db: Session) -> None:
        """No haber evaluado no es incumplir.

        Con `non_compliant` por defecto, el porcentaje de la empresa caeria a
        cero el dia que se le carga la matriz — y seria mentira.
        """
        matrix_id, _, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)

        incumplidos = db.execute(
            text(
                "SELECT count(*) FROM article_compliance ac "
                "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
                "WHERE mn.matrix_id = :m AND ac.compliance_status = 'non_compliant'"
            ),
            {"m": matrix_id},
        ).scalar_one()
        assert incumplidos == 0

    def test_registra_que_la_incluyo_el_calculo(self, db: Session) -> None:
        matrix_id, _, sid = _preparar(db)
        sincronizar(db, matrix_id, TENANT)

        origen, sector = db.execute(
            text(
                "SELECT inclusion_source, sector_id FROM matrix_norms WHERE matrix_id = :m"
            ),
            {"m": matrix_id},
        ).first()
        assert origen == "automatic"
        assert sector == sid

    def test_las_recomendadas_tambien_entran(self, db: Session) -> None:
        """Obligatoria y recomendada es una distincion para la pantalla.

        Las dos van a la matriz: la diferencia es como se presentan, no si se
        evaluan.
        """
        matrix_id, _, _ = _preparar(db, nivel="referencial")

        r = sincronizar(db, matrix_id, TENANT)

        assert r.normas_agregadas == 1


class TestIdempotencia:
    def test_correrlo_dos_veces_no_duplica(self, db: Session) -> None:
        matrix_id, _, _ = _preparar(db)
        primera = sincronizar(db, matrix_id, TENANT)

        segunda = sincronizar(db, matrix_id, TENANT)

        assert segunda.normas_agregadas == 0
        assert segunda.normas_ya_estaban == 1
        assert segunda.articulos_agregados == 0
        assert _evaluaciones(db, matrix_id) == primera.articulos_agregados

    def test_la_evaluacion_sobrevive_al_recalculo(self, db: Session) -> None:
        """El viaje completo, y la razon de ser de todo el servicio.

        Generar, evaluar, regenerar: lo evaluado sigue evaluado. Si esto falla,
        cada recalculo le borra el trabajo a quien evaluo.
        """
        matrix_id, _, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        db.execute(
            text(
                "UPDATE article_compliance SET compliance_status = 'compliant' "
                "WHERE matrix_norm_id IN "
                "(SELECT id FROM matrix_norms WHERE matrix_id = :m)"
            ),
            {"m": matrix_id},
        )
        evaluados_antes = db.execute(
            text(
                "SELECT count(*) FROM article_compliance ac "
                "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
                "WHERE mn.matrix_id = :m AND ac.compliance_status = 'compliant'"
            ),
            {"m": matrix_id},
        ).scalar_one()

        sincronizar(db, matrix_id, TENANT)

        evaluados_despues = db.execute(
            text(
                "SELECT count(*) FROM article_compliance ac "
                "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
                "WHERE mn.matrix_id = :m AND ac.compliance_status = 'compliant'"
            ),
            {"m": matrix_id},
        ).scalar_one()
        assert evaluados_despues == evaluados_antes > 0


class TestNuncaBorra:
    def test_lo_que_deja_de_aplicar_se_marca_y_se_conserva(self, db: Session) -> None:
        """Borrarla eliminaria la evidencia de que en su momento se evaluo."""
        matrix_id, norm_id, sid = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        db.execute(text("DELETE FROM norm_sectors WHERE sector_id = :s"), {"s": sid})
        # Se deja otra clasificada para que el calculo no devuelva vacio: sin
        # normativa el servicio no toca nada, y no se probaria el marcado.
        otra = db.execute(
            text(
                "SELECT v.norm_id FROM legal_norm_versions v "
                "JOIN legal_articles a ON a.norm_version_id = v.id "
                "WHERE v.is_current AND v.norm_id <> :n GROUP BY v.norm_id LIMIT 1"
            ),
            {"n": norm_id},
        ).scalar()
        if otra is None:
            pytest.skip("Se necesita una segunda norma con articulado")
        db.execute(
            text(
                "INSERT INTO norm_sectors (norm_id, sector_id, applicability_level, rationale) "
                "VALUES (:n, :s, 'directa', 'la que queda')"
            ),
            {"n": otra, "s": sid},
        )

        r = sincronizar(db, matrix_id, TENANT)

        assert r.normas_marcadas_no_aplicables == 1
        estado, motivo = db.execute(
            text(
                "SELECT applicability, applicability_reason FROM matrix_norms "
                "WHERE matrix_id = :m AND norm_id = :n"
            ),
            {"m": matrix_id, "n": norm_id},
        ).first()
        assert estado == "not_applicable"
        assert motivo == MOTIVO_YA_NO_APLICA

    def test_un_recalculo_no_quita_lo_agregado_a_mano(self, db: Session) -> None:
        """Que el calculo no la encuentre no significa que no aplique.

        Puede venir de un contrato o de la RCA de la empresa.
        """
        matrix_id, norm_id, sid = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        db.execute(
            text(
                "UPDATE matrix_norms SET inclusion_source = 'manual' "
                "WHERE matrix_id = :m AND norm_id = :n"
            ),
            {"m": matrix_id, "n": norm_id},
        )
        db.execute(text("DELETE FROM norm_sectors WHERE sector_id = :s"), {"s": sid})
        otra = db.execute(
            text(
                "SELECT v.norm_id FROM legal_norm_versions v "
                "JOIN legal_articles a ON a.norm_version_id = v.id "
                "WHERE v.is_current AND v.norm_id <> :n GROUP BY v.norm_id LIMIT 1"
            ),
            {"n": norm_id},
        ).scalar()
        if otra is None:
            pytest.skip("Se necesita una segunda norma con articulado")
        db.execute(
            text(
                "INSERT INTO norm_sectors (norm_id, sector_id, applicability_level, rationale) "
                "VALUES (:n, :s, 'directa', 'la que queda')"
            ),
            {"n": otra, "s": sid},
        )

        sincronizar(db, matrix_id, TENANT)

        estado = db.execute(
            text(
                "SELECT applicability FROM matrix_norms WHERE matrix_id = :m AND norm_id = :n"
            ),
            {"m": matrix_id, "n": norm_id},
        ).scalar()
        assert estado == "applicable", "una norma manual no se marca por un recalculo"


class TestSinNormativa:
    def test_sector_sin_clasificar_no_toca_nada(self, db: Session) -> None:
        """El caso peligroso: 0 normas que NO significa "sin obligaciones".

        Si se marcaran como no aplicables las que ya estan, un sector sin
        clasificar vaciaria la matriz de una empresa que si tiene obligaciones.
        """
        matrix_id, _, sid = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        antes = _evaluaciones(db, matrix_id)
        db.execute(text("DELETE FROM norm_sectors WHERE sector_id = :s"), {"s": sid})

        r = sincronizar(db, matrix_id, TENANT)

        assert r.sin_calcular == "sector_sin_clasificar"
        assert r.normas_marcadas_no_aplicables == 0
        assert _evaluaciones(db, matrix_id) == antes

    def test_empresa_sin_perfil_no_toca_nada(self, db: Session) -> None:
        matrix_id, _, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        antes = _evaluaciones(db, matrix_id)
        db.execute(text("UPDATE tenants SET sector_id = NULL WHERE id = :t"), {"t": TENANT})

        r = sincronizar(db, matrix_id, TENANT)

        assert r.sin_calcular == "sin_perfil"
        assert _evaluaciones(db, matrix_id) == antes


class TestVersionDesactualizada:
    """Avisar que hay version nueva, sin invalidar lo evaluado (grupo 6)."""

    def _version_nueva(self, db: Session, norm_id):
        """Publica una version mas nueva y la deja como vigente."""
        nueva = uuid.uuid4()
        db.execute(text("UPDATE legal_norm_versions SET is_current = false WHERE norm_id = :n"),
                   {"n": norm_id})
        db.execute(
            text(
                "INSERT INTO legal_norm_versions "
                "(id, norm_id, valid_from, is_current, content_hash) "
                "VALUES (:i, :n, CURRENT_DATE, true, :h)"
            ),
            {"i": nueva, "n": norm_id, "h": uuid.uuid4().hex + uuid.uuid4().hex},
        )
        return nueva

    def test_sin_version_nueva_no_marca_nada(self, db: Session) -> None:
        matrix_id, _, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)

        assert desactualizadas(db, matrix_id) == []

    def test_una_version_nueva_marca_la_norma(self, db: Session) -> None:
        matrix_id, norm_id, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        nueva = self._version_nueva(db, norm_id)

        avisos = desactualizadas(db, matrix_id)

        assert len(avisos) == 1
        assert avisos[0].norm_id == norm_id
        assert avisos[0].version_vigente == nueva
        assert avisos[0].version_evaluada != nueva

    def test_las_evaluaciones_de_la_version_anterior_siguen_visibles(
        self, db: Session
    ) -> None:
        """No se invalidan solas.

        Se hicieron sobre el texto que regia entonces, y esa es la respuesta
        correcta ante una auditoria de ese periodo.
        """
        matrix_id, norm_id, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        db.execute(
            text(
                "UPDATE article_compliance SET compliance_status = 'compliant' "
                "WHERE matrix_norm_id IN (SELECT id FROM matrix_norms WHERE matrix_id = :m)"
            ),
            {"m": matrix_id},
        )
        self._version_nueva(db, norm_id)

        avisos = desactualizadas(db, matrix_id)

        assert avisos[0].evaluaciones_sobre_la_anterior > 0
        siguen = db.execute(
            text(
                "SELECT count(*) FROM article_compliance ac "
                "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
                "WHERE mn.matrix_id = :m AND ac.compliance_status = 'compliant'"
            ),
            {"m": matrix_id},
        ).scalar_one()
        assert siguen == avisos[0].evaluaciones_sobre_la_anterior

    def test_una_norma_que_ya_no_aplica_no_genera_aviso(self, db: Session) -> None:
        """No se esta evaluando contra ninguna version: el aviso seria ruido."""
        matrix_id, norm_id, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        db.execute(
            text(
                "UPDATE matrix_norms SET applicability = 'not_applicable' "
                "WHERE matrix_id = :m"
            ),
            {"m": matrix_id},
        )
        self._version_nueva(db, norm_id)

        assert desactualizadas(db, matrix_id) == []


class TestActualizarALaVersionVigente:
    """Mover la norma al texto de hoy **sin perder lo evaluado**.

    ## Por que hacia falta

    La matriz **ya mostraba los articulos del texto vigente**: la pantalla los
    pide por `/catalog/norms/{id}/articles`, que devuelve los de `is_current`.
    O sea que `selected_version_id` quedaba como un dato que solo miraba el
    aviso, y las evaluaciones viejas eran invisibles sin que nada lo dijera.

    Medido en la base de desarrollo antes de escribir esto: la Ley 19.300
    apuntaba a una version con **2 articulos** mientras la vigente tenia
    **151**, y de sus 4 evaluaciones **ninguna** estaba en la vigente.

    ## Lo que NO hace, y es la prueba que manda

    No migra las evaluaciones anteriores y no las borra. Migrarlas seria
    inventar —entre versiones los articulos se renumeran, se parten y
    desaparecen— y borrarlas destruiria la respuesta ante una auditoria del
    periodo en que se hicieron.
    """

    def _version_nueva_con_articulos(self, db: Session, norm_id, cuantos: int):
        """Publica una version nueva **con articulado propio** y la deja vigente."""
        nueva = uuid.uuid4()
        db.execute(
            text("UPDATE legal_norm_versions SET is_current = false WHERE norm_id = :n"),
            {"n": norm_id},
        )
        db.execute(
            text(
                "INSERT INTO legal_norm_versions "
                "(id, norm_id, valid_from, is_current, content_hash) "
                "VALUES (:i, :n, CURRENT_DATE, true, :h)"
            ),
            {"i": nueva, "n": norm_id, "h": uuid.uuid4().hex + uuid.uuid4().hex},
        )
        for i in range(cuantos):
            db.execute(
                text(
                    "INSERT INTO legal_articles "
                    "(id, norm_version_id, article_number, heading, content, display_order) "
                    "VALUES (:i, :v, :num, :h, :c, :o)"
                ),
                {
                    "i": uuid.uuid4(),
                    "v": nueva,
                    "num": "Art. " + str(i + 1) + " (texto nuevo)",
                    "h": "Articulo nuevo " + str(i + 1),
                    # `content` es NOT NULL: un articulo sin texto no es un
                    # articulo, y la base no deja escribirlo.
                    "c": "Texto del articulo " + str(i + 1) + " de la version nueva.",
                    "o": i,
                },
            )
        db.flush()
        return nueva

    def _evaluar_todo(self, db: Session, matrix_id) -> int:
        db.execute(
            text(
                "UPDATE article_compliance SET compliance_status = 'compliant' "
                "WHERE matrix_norm_id IN (SELECT id FROM matrix_norms WHERE matrix_id = :m)"
            ),
            {"m": matrix_id},
        )
        return db.execute(
            text(
                "SELECT count(*) FROM article_compliance ac "
                "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
                "WHERE mn.matrix_id = :m AND ac.compliance_status = 'compliant'"
            ),
            {"m": matrix_id},
        ).scalar_one()

    def test_LAS_EVALUACIONES_ANTERIORES_NO_SE_PIERDEN(self, db: Session) -> None:
        """La afirmacion central. Si esto falla, la funcion destruye trabajo."""
        matrix_id, norm_id, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        evaluadas_antes = self._evaluar_todo(db, matrix_id)
        assert evaluadas_antes > 0, "la preparacion no dejo nada evaluado"
        self._version_nueva_con_articulos(db, norm_id, 3)

        actualizar_a_version_vigente(db, matrix_id, TENANT)

        siguen = db.execute(
            text(
                "SELECT count(*) FROM article_compliance ac "
                "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
                "WHERE mn.matrix_id = :m AND ac.compliance_status = 'compliant'"
            ),
            {"m": matrix_id},
        ).scalar_one()
        assert siguen == evaluadas_antes

    def test_la_norma_queda_apuntando_al_texto_vigente(self, db: Session) -> None:
        matrix_id, norm_id, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        nueva = self._version_nueva_con_articulos(db, norm_id, 3)

        r = actualizar_a_version_vigente(db, matrix_id, TENANT)

        assert r.actualizadas == 1
        apunta = db.execute(
            text(
                "SELECT selected_version_id FROM matrix_norms "
                "WHERE matrix_id = :m AND norm_id = :n"
            ),
            {"m": matrix_id, "n": norm_id},
        ).scalar_one()
        assert apunta == nueva

    def test_siembra_las_evaluaciones_del_articulado_nuevo(self, db: Session) -> None:
        """Sin esto, la norma queda apuntando al texto nuevo y sin filas que
        evaluar: la pantalla mostraria los articulos y la API contaria cero.
        """
        matrix_id, norm_id, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        nueva = self._version_nueva_con_articulos(db, norm_id, 3)

        r = actualizar_a_version_vigente(db, matrix_id, TENANT)

        assert r.articulos_nuevos == 3
        en_la_nueva = db.execute(
            text(
                "SELECT count(*) FROM article_compliance ac "
                "JOIN legal_articles a ON a.id = ac.article_id "
                "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
                "WHERE mn.matrix_id = :m AND a.norm_version_id = :v"
            ),
            {"m": matrix_id, "v": nueva},
        ).scalar_one()
        assert en_la_nueva == 3

    def test_lo_nuevo_nace_pendiente_y_no_incumplido(self, db: Session) -> None:
        """No haber evaluado no es incumplir.

        Si naciera `non_compliant`, actualizar una norma llenaria de golpe la
        pantalla de incumplimientos con articulos que nadie miro todavia — y el
        tablero mostraria a la empresa en rojo por haber actualizado.
        """
        matrix_id, norm_id, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        nueva = self._version_nueva_con_articulos(db, norm_id, 3)

        actualizar_a_version_vigente(db, matrix_id, TENANT)

        estados = (
            db.execute(
                text(
                    "SELECT DISTINCT ac.compliance_status FROM article_compliance ac "
                    "JOIN legal_articles a ON a.id = ac.article_id "
                    "WHERE a.norm_version_id = :v"
                ),
                {"v": nueva},
            )
            .scalars()
            .all()
        )
        assert estados == ["pending"]

    def test_informa_cuantas_evaluaciones_conservo(self, db: Session) -> None:
        """El numero que le dice a la persona que no perdio nada."""
        matrix_id, norm_id, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        evaluadas = self._evaluar_todo(db, matrix_id)
        self._version_nueva_con_articulos(db, norm_id, 2)

        r = actualizar_a_version_vigente(db, matrix_id, TENANT)

        assert r.evaluaciones_conservadas == evaluadas

    def test_correrlo_dos_veces_no_hace_nada_la_segunda(self, db: Session) -> None:
        matrix_id, norm_id, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        self._version_nueva_con_articulos(db, norm_id, 2)

        primera = actualizar_a_version_vigente(db, matrix_id, TENANT)
        segunda = actualizar_a_version_vigente(db, matrix_id, TENANT)

        assert primera.actualizadas == 1
        assert segunda.actualizadas == 0
        assert segunda.articulos_nuevos == 0

    def test_el_aviso_desaparece_despues_de_actualizar(self, db: Session) -> None:
        matrix_id, norm_id, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        self._version_nueva_con_articulos(db, norm_id, 2)
        assert desactualizadas(db, matrix_id) != []

        actualizar_a_version_vigente(db, matrix_id, TENANT)

        assert desactualizadas(db, matrix_id) == []

    def test_se_puede_actualizar_UNA_sola(self, db: Session) -> None:
        """Actualizar todo de golpe no siempre es lo que se quiere: una norma
        con cien evaluaciones se revisa cuando hay tiempo de leerla.
        """
        matrix_id, norm_id, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        self._version_nueva_con_articulos(db, norm_id, 2)
        aviso = desactualizadas(db, matrix_id)[0]

        r = actualizar_a_version_vigente(db, matrix_id, TENANT, [aviso.matrix_norm_id])

        assert r.actualizadas == 1
        assert r.titulos == [aviso.title]

    def test_pedir_una_que_ya_estaba_al_dia_no_es_un_error(self, db: Session) -> None:
        """Entre que se dibuja la pantalla y se aprieta el boton, otra persona
        pudo actualizarla. Eso no es un fallo: se informa y se sigue.
        """
        matrix_id, _, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        al_dia = db.execute(
            text("SELECT id FROM matrix_norms WHERE matrix_id = :m LIMIT 1"),
            {"m": matrix_id},
        ).scalar_one()

        r = actualizar_a_version_vigente(db, matrix_id, TENANT, [al_dia])

        assert r.actualizadas == 0
        assert r.ya_estaban_al_dia == 1

    def test_una_norma_de_OTRA_matriz_no_se_toca(self, db: Session) -> None:
        """Y el aislamiento viene de `desactualizadas`, no de un `if` en el bucle.

        Esta prueba decia que cubria una comprobacion de pertenencia a la
        matriz. **Era falso**, y lo encontro el arnes de mutacion: quitar ese
        `if` del servicio no la rompia. La razon es que la lista sale de
        `desactualizadas(db, matrix_id)`, que ya filtra por matriz, asi que el
        `if` era inalcanzable. Se quito del servicio y este texto dice de donde
        sale el aislamiento de verdad.
        """
        matrix_id, norm_id, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        self._version_nueva_con_articulos(db, norm_id, 2)

        # Otro periodo: `uq_matrices_periodo` impide dos matrices del mismo ano
        # en la misma empresa, y `_matriz_vacia` usa siempre el mismo.
        otra_matriz = uuid.uuid4()
        db.execute(
            text(
                "INSERT INTO tenant_legal_matrices (id, tenant_id, name, period_year) "
                "VALUES (:i, :t, 'Otra matriz', :a)"
            ),
            {"i": otra_matriz, "t": TENANT, "a": ANO_DE_PRUEBA - 1},
        )
        ajena = db.execute(
            text("SELECT id FROM matrix_norms WHERE matrix_id = :m LIMIT 1"),
            {"m": matrix_id},
        ).scalar_one()

        r = actualizar_a_version_vigente(db, otra_matriz, TENANT, [ajena])

        assert r.actualizadas == 0, "se actualizo una norma que no es de esa matriz"
