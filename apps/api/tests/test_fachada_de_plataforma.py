"""La fachada de plataforma: el estado de los agentes del AI Service.

## Por que este archivo existe aparte

La guarda que protege esta ruta **no se puede probar en modo desarrollo**.
`exigir_admin_global` empieza con `if not clerk_configured: return user`, porque
sin Clerk la API ya confia enteramente en quien llama y exigir ahi un rol que
nadie puede probar haria imposible trabajar en local.

O sea que el resto de la suite —que corre sin Clerk— atravesaria esta ruta sin
mirar nada, y la guarda estaria **escrita, en verde y sin ejecutarse nunca**. Es
exactamente lo que paso con el limite del Admin Global hasta que aparecio
`test_admin_global_no_edita.py`, de donde sale el arnes de abajo.

## Lo que se protege

1. **Que un usuario normal no vea el estado de los trabajos.** Que trabajos
   existen y cuando corrieron dice como esta armado el sistema.
   `test_un_usuario_de_empresa_recibe_403`.
2. **Que la identidad de plataforma funcione sin inventarle una empresa.** El
   informe de integracion lo marca como un problema a resolver; en este esquema
   `users.tenant_id` es `NOT NULL`, asi que un `platform_admin` siempre tiene
   empresa. `test_el_admin_global_ve_el_estado`.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.auth import CurrentUser  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.deps import declarar, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.services import ai_service as svc  # noqa: E402

EMPRESA = "a0000000-0000-0000-0000-000000000001"
RUTA = "/api/v1/system/agentes-ia"
AI = "http://ai-service-de-prueba:8100"

ESTADO_OK = {
    "agentes": [
        {
            "nombre": "ingesta_pdf",
            "estado": "ok",
            "iniciado_en": "2026-10-15T02:00:00Z",
            "finalizado_en": "2026-10-15T02:04:00Z",
            "elementos": 12,
            "detalle": None,
        },
        {
            "nombre": "monitoreo_bcn",
            "estado": "error",
            "iniciado_en": "2026-10-15T03:00:00Z",
            "finalizado_en": None,
            "elementos": 0,
            "detalle": "la BCN no respondio",
        },
    ]
}


class _RespuestaFalsa:
    def __init__(self, status_code=200, cuerpo=None, texto=""):
        self.status_code = status_code
        self._cuerpo = cuerpo
        self.text = texto

    def json(self):
        if self._cuerpo is None:
            raise ValueError("sin cuerpo")
        return self._cuerpo


def _sesion_simulada(tipo: str):
    """Un cliente con Clerk simulado como configurado y el usuario en `tipo`.

    **`dependency_overrides` es global**, asi que se limpia en el `finally` pase
    lo que pase: una prueba de este repositorio ya dejo a un cliente actuando
    como el usuario de otra empresa por olvidarlo.
    """
    import psycopg

    try:
        psycopg.connect(
            os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")
        ).close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible ({exc}). Hace falta docker compose.")

    ajustes = get_settings()
    jwks_previo = ajustes.clerk_jwks_url

    with SessionLocal() as db:
        declarar(db, EMPRESA)
        fila = db.execute(
            text(
                "SELECT id, clerk_id, user_type FROM users "
                "WHERE deleted_at IS NULL ORDER BY created_at, id LIMIT 1"
            )
        ).first()
        if fila is None:  # pragma: no cover - seed sin usuarios
            pytest.skip("el seed no tiene usuarios")
        uid, clerk_previo, tipo_previo = fila
        clerk_id = clerk_previo or f"user_prueba_{uuid.uuid4().hex[:10]}"
        db.execute(
            text("UPDATE users SET clerk_id = :c, user_type = :t WHERE id = :u"),
            {"c": clerk_id, "t": tipo, "u": uid},
        )
        db.commit()

    ajustes.clerk_jwks_url = "https://prueba.clerk/jwks"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id=clerk_id, tenant_id=EMPRESA
    )
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        ajustes.clerk_jwks_url = jwks_previo
        with SessionLocal() as db:
            declarar(db, EMPRESA)
            db.execute(
                text("UPDATE users SET clerk_id = :c, user_type = :t WHERE id = :u"),
                {"c": clerk_previo, "t": tipo_previo, "u": uid},
            )
            db.commit()


@pytest.fixture
def como_admin_global():
    yield from _sesion_simulada("platform_admin")


@pytest.fixture
def como_usuario_de_empresa():
    yield from _sesion_simulada("internal")


@pytest.fixture
def con_ai_service():
    """Un AI Service configurado, **mutando los ajustes en vez de recargarlos**.

    `get_settings` esta cacheado con `lru_cache` y el arnes de arriba simula a
    Clerk escribiendo `clerk_jwks_url` sobre ese mismo objeto. Un
    `cache_clear()` aca reconstruiria los ajustes desde el entorno —donde no hay
    `CLERK_JWKS_URL`— y la guarda volveria a su modo desarrollo: `403` esperado,
    `200` recibido, y la prueba acusando a la guarda de un problema que causo la
    prueba. Es la version sutil de la trampa que este archivo existe para evitar.
    """
    ajustes = get_settings()
    previo = ajustes.ai_service_url
    ajustes.ai_service_url = AI
    yield
    ajustes.ai_service_url = previo


@pytest.fixture
def espia(monkeypatch):
    capturado: dict = {}

    def falso_get(url, headers=None, timeout=None):
        capturado["url"] = url
        capturado["cabeceras"] = headers or {}
        capturado["timeout"] = timeout
        return _RespuestaFalsa(cuerpo=ESTADO_OK)

    monkeypatch.setattr(svc.httpx, "get", falso_get)
    return capturado


class TestSoloPlataforma:
    def test_un_usuario_de_empresa_recibe_403(
        self, como_usuario_de_empresa, con_ai_service, espia
    ) -> None:
        """**La prueba por la que este archivo simula Clerk.**

        Sin el arnes, la suite entera atraviesa esta ruta sin mirar nada y la
        guarda queda escrita, en verde y sin ejecutarse.
        """
        r = como_usuario_de_empresa.get(RUTA)

        assert r.status_code == 403, r.text
        # Y no se consulto al AI Service: se autoriza **antes** de reenviar.
        assert espia == {}

    def test_el_admin_global_ve_el_estado(
        self, como_admin_global, con_ai_service, espia
    ) -> None:
        """Y de paso: la identidad de plataforma no necesita contrato nuevo.

        El informe de integracion propone "emitir un tenant tecnico" o "aceptar
        plataforma sin `tenant_id`". Ninguna hace falta: `users.tenant_id` es
        `NOT NULL` y la cuenta global vive en la empresa `platform`, asi que el
        claim viaja igual.
        """
        r = como_admin_global.get(RUTA)

        assert r.status_code == 200, r.text
        cuerpo = r.json()
        assert [a["nombre"] for a in cuerpo["agentes"]] == ["ingesta_pdf", "monitoreo_bcn"]
        # El `detalle` del que fallo llega: es lo unico que dice por que.
        assert cuerpo["agentes"][1]["detalle"] == "la BCN no respondio"

    def test_pide_el_estado_y_no_otra_cosa(
        self, como_admin_global, con_ai_service, espia
    ) -> None:
        como_admin_global.get(RUTA)

        assert espia["url"] == f"{AI}/agentes/estado"
        # **El timeout de lectura es corto, al contrario que en una consulta.**
        # Aca no hay un modelo generando: una espera de tres minutos por un
        # estado es un panel colgado.
        assert espia["timeout"].read <= 30


class TestSinConfigurarLoDice:
    def test_responde_503_y_nombra_la_variable(self, como_admin_global) -> None:
        """Sin `con_ai_service`: los ajustes ya traen la variable vacia.

        Y se afirma **despues de la guarda**: un 403 aca tambien daria "no 200"
        sin que el 503 exista.
        """
        ajustes = get_settings()
        previo = ajustes.ai_service_url
        ajustes.ai_service_url = ""
        try:
            r = como_admin_global.get(RUTA)
        finally:
            ajustes.ai_service_url = previo

        assert r.status_code == 503, r.text
        assert r.json()["detail"]["codigo"] == "ai_service_sin_configurar"
        assert "AI_SERVICE_URL" in r.json()["detail"]["mensaje"]


class TestLosErroresNoFiltranNada:
    def test_un_500_del_ai_service_sale_como_503_sin_su_cuerpo(
        self, como_admin_global, con_ai_service, monkeypatch
    ) -> None:
        traza = 'Traceback: File "/app/ambienta_ia/monitoreo.py", clave=sk-abc123'
        monkeypatch.setattr(
            svc.httpx, "get", lambda *a, **k: _RespuestaFalsa(status_code=500, texto=traza)
        )

        r = como_admin_global.get(RUTA)

        assert r.status_code == 503, r.text
        assert "Traceback" not in r.text
        assert "sk-abc123" not in r.text
