"""El Perfil Empresa como primer flujo obligatorio (RF-10, #100).

## Lo que estaba mal y estas pruebas impiden que vuelva

La marca de "perfil completo" la calculaba el **navegador**:

    perfilEmpresaCompleto = Boolean(business_activity && rut_tax_id)

`rut_tax_id` es `NOT NULL`, asi que nunca falta: la condicion colapsaba a "tiene
giro", y las dos empresas del seed lo tienen. **La marca daba `true` para todas
y el flujo obligatorio no bloqueaba a nadie.** Nunca se le vio funcionar contra
datos reales — el propio analisis dice que se comprobaba alternando el valor por
la consola del navegador.

## Las dos mitades

1. **Que cuenta como completo**, ahora calculado en el servidor contra los
   cuatro puntos que el wizard exige.
2. **Que el bloqueo exista de verdad**, no solo como redireccion del navegador.
   Con `curl` la API respondia igual con el perfil vacio.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.perfil_empresa import estado

TENANT_1 = "a0000000-0000-0000-0000-000000000001"
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


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
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT_1}
    )
    try:
        yield sesion
    finally:
        # Todo lo que escriban estas pruebas se deshace: tocan `tenants`, que es
        # dato compartido por el resto de la suite.
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


class TestQueCuentaComoCompleto:
    """Los cuatro puntos del wizard, decididos por el equipo el 25-ago-2026."""

    def test_sin_sector_no_esta_completa_aunque_tenga_giro(
        self, db: Session
    ) -> None:
        """**Esto es lo que la formula vieja daba por completo.**

        Giro, plantas y departamentos, pero sin sector — que es justo lo que
        hace que el CORE no le proponga normativa. `Boolean(giro && rut)` decia
        que si.

        La prueba **pone el estado que quiere medir** en vez de confiar en el
        seed: la empresa sembrada ya cambio de sector una vez, y una prueba que
        asume datos ajenos mide otra cosa el dia que alguien los toca. Ya paso:
        la primera version de este archivo afirmaba `sector_id IS NULL` y fallo.
        """
        db.execute(
            text("UPDATE tenants SET sector_id = NULL WHERE id = :t"),
            {"t": TENANT_1},
        )

        resultado = estado(db, TENANT_1)

        assert resultado.tiene_giro
        assert resultado.tiene_instalaciones
        assert resultado.tiene_departamentos
        assert not resultado.tiene_sector
        assert not resultado.completo

    def test_dice_que_falta_en_el_idioma_de_quien_lo_lee(self, db: Session) -> None:
        """Un booleano solo obligaria a la pantalla a recalcular los cuatro
        puntos para poder explicar — y ahi empiezan las dos verdades."""
        db.execute(
            text("UPDATE tenants SET sector_id = NULL WHERE id = :t"),
            {"t": TENANT_1},
        )
        resultado = estado(db, TENANT_1)

        assert resultado.faltantes
        texto = " ".join(resultado.faltantes)
        assert "sector" in texto.lower()
        # En castellano, no en nombres de columna.
        assert "sector_id" not in texto
        assert "business_activity" not in texto

    def test_con_los_cuatro_puntos_queda_completa(self, db: Session) -> None:
        sector = db.execute(text("SELECT id FROM sectors LIMIT 1")).scalar()
        assert sector is not None, "El catalogo de sectores esta vacio."
        db.execute(
            text("UPDATE tenants SET sector_id = :s WHERE id = :t"),
            {"s": sector, "t": TENANT_1},
        )

        resultado = estado(db, TENANT_1)

        assert resultado.completo, resultado.faltantes
        assert resultado.faltantes == []

    def test_sin_giro_no_alcanza_aunque_tenga_lo_demas(self, db: Session) -> None:
        sector = db.execute(text("SELECT id FROM sectors LIMIT 1")).scalar()
        db.execute(
            text(
                "UPDATE tenants SET sector_id = :s, business_activity = NULL "
                "WHERE id = :t"
            ),
            {"s": sector, "t": TENANT_1},
        )

        resultado = estado(db, TENANT_1)

        assert not resultado.completo
        assert not resultado.tiene_giro

    def test_un_giro_en_blanco_no_cuenta_como_declarado(self, db: Session) -> None:
        """**Espacios no son un giro.**

        La formula vieja usaba `Boolean(business_activity)`, que da `true` para
        `"   "`. Quien escribe un espacio para pasar el paso no declaro nada.
        """
        sector = db.execute(text("SELECT id FROM sectors LIMIT 1")).scalar()
        db.execute(
            text(
                "UPDATE tenants SET sector_id = :s, business_activity = '   ' "
                "WHERE id = :t"
            ),
            {"s": sector, "t": TENANT_1},
        )

        assert not estado(db, TENANT_1).tiene_giro

    def test_sin_instalaciones_no_esta_completa(self, db: Session) -> None:
        """Aparecio con una mutacion: **nada probaba este punto.**

        Se dan de baja dentro de la transaccion de la prueba, que hace
        `rollback`. Tocar `facilities` de verdad afectaria al resto de la suite.
        """
        sector = db.execute(text("SELECT id FROM sectors LIMIT 1")).scalar()
        db.execute(
            text("UPDATE tenants SET sector_id = :s WHERE id = :t"),
            {"s": sector, "t": TENANT_1},
        )
        db.execute(
            text(
                "UPDATE facilities SET deleted_at = now() "
                "WHERE tenant_id = :t AND deleted_at IS NULL"
            ),
            {"t": TENANT_1},
        )

        resultado = estado(db, TENANT_1)

        assert not resultado.tiene_instalaciones
        assert not resultado.completo
        assert any("planta" in f.lower() for f in resultado.faltantes)

    def test_sin_departamentos_no_esta_completa(self, db: Session) -> None:
        """El punto que RF-11 agrega al perfil. Tambien estaba sin probar."""
        sector = db.execute(text("SELECT id FROM sectors LIMIT 1")).scalar()
        db.execute(
            text("UPDATE tenants SET sector_id = :s WHERE id = :t"),
            {"s": sector, "t": TENANT_1},
        )
        # Primero la gente: desde RF-11 un interno no puede quedar sin
        # departamento, asi que darlos de baja sin mas viola el CHECK.
        db.execute(
            text(
                "UPDATE users SET user_type = 'guest', department_id = NULL "
                "WHERE tenant_id = :t AND deleted_at IS NULL"
            ),
            {"t": TENANT_1},
        )
        db.execute(
            text(
                "UPDATE departments SET deleted_at = now() "
                "WHERE tenant_id = :t AND deleted_at IS NULL"
            ),
            {"t": TENANT_1},
        )

        resultado = estado(db, TENANT_1)

        assert not resultado.tiene_departamentos
        assert not resultado.completo
        assert any("departamento" in f.lower() for f in resultado.faltantes)

    def test_una_empresa_que_no_se_ve_sale_incompleta_y_no_revienta(
        self, db: Session
    ) -> None:
        """Preguntar por una empresa ajena no dice si existe.

        Devolver un error distinto para "no existe" y "existe pero no la ves"
        seria un oraculo, el mismo problema que ya cerro `validar_visible`.
        """
        resultado = estado(db, uuid.uuid4())

        assert not resultado.completo
        assert len(resultado.faltantes) == 4


class TestElBloqueoDelServidor:
    """RF-10 pide *forzar* el flujo, no sugerirlo.

    Hasta hoy solo existia como redireccion del navegador: con `curl` la API
    respondia igual con el perfil vacio. Un flujo obligatorio que solo se aplica
    en el cliente no es obligatorio.

    ## Como se monta el escenario, y por que asi

    La guarda solo actua con proveedor de identidad configurado y sobre un
    `tenant_admin`. Montar eso de verdad exigiria un JWT firmado por Clerk, que
    esta suite no tiene. Se sustituye **la dependencia de identidad** —no la
    guarda— con `dependency_overrides`: el camino que se prueba es el de la
    guarda entera, y lo unico simulado es de donde sale el nombre de quien
    llama.

    Estas pruebas **escriben y confirman** en `tenants` y `users`, porque la
    guarda corre en la sesion del request y no ve una transaccion abierta
    aparte. El fixture restaura todo lo que toca.
    """

    @pytest.fixture
    def entorno(self):
        """Clerk "encendido", un `tenant_admin` identificable, y limpieza."""
        from fastapi.testclient import TestClient

        from app.auth import CurrentUser
        from app.config import get_settings
        from app.db import SessionLocal
        from app.deps import get_current_user
        from app.main import app

        motor = create_engine(URL)
        try:
            motor.connect().close()
        except Exception as exc:  # pragma: no cover - entorno sin base
            pytest.skip(f"Sin base de datos disponible: {exc}")

        ajustes = get_settings()
        jwks_previo = ajustes.clerk_jwks_url
        original = SessionLocal.kw.get("bind")
        SessionLocal.configure(bind=motor)

        def con_tenant(consulta, parametros=None):
            with motor.begin() as c:
                c.execute(text("SET LOCAL ROLE ambienta_app"))
                c.execute(
                    text("SELECT set_config('ambienta.tenant_id', :t, true)"),
                    {"t": TENANT_1},
                )
                return c.execute(text(consulta), parametros or {}).first()

        fila = con_tenant(
            "SELECT id, clerk_id FROM users WHERE tenant_id = :t "
            "AND user_type = 'tenant_admin' AND deleted_at IS NULL LIMIT 1",
            {"t": TENANT_1},
        )
        sector_previo = con_tenant(
            "SELECT sector_id FROM tenants WHERE id = :t", {"t": TENANT_1}
        )[0]

        if fila is None:  # pragma: no cover
            SessionLocal.configure(bind=original)
            pytest.skip("El seed no tiene un tenant_admin en esta empresa.")

        user_id, clerk_previo = fila
        clerk_id = clerk_previo or f"user_prueba_{uuid.uuid4().hex[:10]}"
        con_tenant(
            "UPDATE users SET clerk_id = :c WHERE id = :u RETURNING id",
            {"c": clerk_id, "u": user_id},
        )

        # `clerk_configured` se deriva de esta variable: con algo puesto, la
        # guarda deja de salir temprano.
        ajustes.clerk_jwks_url = "https://prueba.clerk/jwks"
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            user_id=clerk_id, tenant_id=TENANT_1
        )

        def poner_sector(valor):
            con_tenant(
                "UPDATE tenants SET sector_id = :s WHERE id = :t RETURNING id",
                {"s": valor, "t": TENANT_1},
            )

        def poner_tipo(valor):
            con_tenant(
                "UPDATE users SET user_type = :v WHERE id = :u RETURNING id",
                {"v": valor, "u": user_id},
            )

        try:
            yield TestClient(app), poner_sector, poner_tipo
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            ajustes.clerk_jwks_url = jwks_previo
            poner_sector(sector_previo)
            poner_tipo("tenant_admin")
            con_tenant(
                "UPDATE users SET clerk_id = :c WHERE id = :u RETURNING id",
                {"c": clerk_previo, "u": user_id},
            )
            SessionLocal.configure(bind=original)
            motor.dispose()

    def test_escribir_con_el_perfil_incompleto_se_bloquea(self, entorno) -> None:
        """**El bloqueo que no existia.** Antes esto respondia como si nada."""
        cliente, poner_sector, _ = entorno
        poner_sector(None)

        r = cliente.post("/api/v1/compliance/matrices", json={"period_year": 2099})

        assert r.status_code == 409, f"No bloqueo: {r.status_code} {r.text}"
        detalle = r.json()["detail"]
        # Dice **que** falta, no solo que falta algo: un 409 sin explicacion deja
        # a la persona sin saber que hacer.
        assert detalle["faltantes"], detalle

    def test_con_el_perfil_completo_deja_pasar(self, entorno, db) -> None:
        """La guarda no puede impedir el trabajo legitimo, que es el caso normal."""
        cliente, poner_sector, _ = entorno
        sector = db.execute(text("SELECT id FROM sectors LIMIT 1")).scalar()
        poner_sector(sector)

        r = cliente.post("/api/v1/compliance/matrices", json={"period_year": 2099})

        assert r.status_code != 409, r.text

    def test_leer_nunca_se_bloquea(self, entorno) -> None:
        """**`GET` pasa siempre, incluso con el perfil vacio.**

        Impedir mirar no acerca a nadie a completar el perfil, y deja a la
        persona sin el contexto para saber que le falta.
        """
        cliente, poner_sector, _ = entorno
        poner_sector(None)

        r = cliente.get("/api/v1/compliance/resumen")

        assert r.status_code != 409, r.text

    def test_un_encargado_no_queda_bloqueado(self, entorno) -> None:
        """**Solo el Admin Empresa.** Es el texto literal de RF-10.

        Bloquear a un Encargado seria castigarlo por algo que **no puede
        arreglar**: completar el perfil no esta entre sus atribuciones.
        """
        cliente, poner_sector, poner_tipo = entorno
        poner_sector(None)
        poner_tipo("internal")

        r = cliente.post("/api/v1/compliance/matrices", json={"period_year": 2099})

        assert r.status_code != 409, r.text

    def test_sin_proveedor_de_identidad_no_se_bloquea_a_nadie(
        self, entorno, monkeypatch
    ) -> None:
        """**La acotacion que evita romper el desarrollo local.**

        Sin Clerk la sesion no identifica a nadie, asi que no se puede saber si
        quien llama es Admin Empresa. Bloquear a todos haria imposible trabajar
        en local.

        Es la clase de guarda que este repo ya advierte en `exigir_permiso`:
        **en local anda perfecto y en produccion no deja pasar a nadie**, o al
        reves. Por eso los dos modos tienen prueba, no solo el que interesa.
        """
        from app.config import get_settings

        cliente, poner_sector, _ = entorno
        poner_sector(None)
        monkeypatch.setattr(get_settings(), "clerk_jwks_url", "", raising=False)

        r = cliente.post("/api/v1/compliance/matrices", json={"period_year": 2099})

        assert r.status_code != 409, r.text
