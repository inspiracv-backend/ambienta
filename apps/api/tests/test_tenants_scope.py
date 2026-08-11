"""El router de empresas no puede quedar abierto otra vez.

`tenants` es la unica tabla de negocio sin `tenant_id`, asi que Row Level
Security no la cubre y toda la proteccion es explicita. Quedo sin ninguna: los
cuatro endpoints usaban `get_db` y respondian sin token, de modo que cualquiera
listaba la cartera de clientes con RUT y razon social, y podia crear o editar
empresas.

Estas comprobaciones son sobre el contrato, no sobre la base: miran que cada
operacion exija credenciales. Que ademas devuelva solo la empresa propia lo
cubre el escenario de aislamiento del smoke test de la base.
"""
from __future__ import annotations

import pytest

from app.main import app

RUTAS_DE_EMPRESAS = (
    ("get", "/api/v1/tenants/"),
    ("post", "/api/v1/tenants/"),
    ("get", "/api/v1/tenants/{tenant_id}"),
    ("patch", "/api/v1/tenants/{tenant_id}"),
)


@pytest.fixture(scope="module")
def esquema() -> dict:
    app.openapi_schema = None
    return app.openapi()


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS_DE_EMPRESAS)
def test_toda_operacion_de_empresas_exige_credenciales(
    esquema: dict, metodo: str, ruta: str
) -> None:
    operacion = esquema["paths"][ruta][metodo]
    assert operacion.get("security"), (
        f"{metodo.upper()} {ruta} quedo sin autenticacion. Es la cartera de "
        "clientes: RUT, razon social y giro de todas las empresas."
    )


def test_ningun_endpoint_de_negocio_queda_sin_credenciales(esquema: dict) -> None:
    """Barrido general: solo puede haber excepciones conocidas y justificadas.

    - `health` y la raiz de la API no exponen datos.
    - `catalog` es la ley, que es publica y compartida entre empresas.
    - `webhooks` lo llama Clerk, y se valida con firma HMAC del payload.

    Cualquier otra ruta abierta es un hallazgo, no una decision.
    """
    permitidas = ("/health", "/api/v1", "/api/v1/catalog", "/api/v1/webhooks")
    abiertas = [
        f"{metodo.upper()} {ruta}"
        for ruta, metodos in esquema["paths"].items()
        for metodo, op in metodos.items()
        if metodo in ("get", "post", "patch", "put", "delete")
        and not op.get("security")
        and not ruta.startswith(permitidas)
    ]
    assert not abiertas, f"Endpoints sin autenticacion: {abiertas}"
