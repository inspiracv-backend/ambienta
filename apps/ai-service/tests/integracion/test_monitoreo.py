"""SPEC-11 · Agente de monitoreo normativo (#137, RF-61)."""

from __future__ import annotations

import pathlib
import time
from datetime import date

import jwt
import pytest

from ambienta_ia.demo import datos as D
from ambienta_ia.monitoreo import CuentaDeEmpresa, CuentaDePlataforma, NovedadSMA, monitorear
from ambienta_ia.sincronizar.sincronizador import CambioDeNorma
from ambienta_ia.snifa import cargar_conjunto

pytestmark = pytest.mark.integracion

FIX = pathlib.Path(__file__).parents[1] / "unit" / "fixtures"
BACKEND = "http://backend/api/v1"


def _token(sub: str, tenant, **extra) -> str:
    return jwt.encode({"sub": sub, "tenant_id": str(tenant), "exp": int(time.time()) + 600, **extra},
                      "clave-de-prueba-de-32-bytes-o-mas!!", algorithm="HS256")


def _cambio_ds1() -> CambioDeNorma:
    ds1 = next(n for n in D.construir()["normas"] if n["norm_number"] == "1/2013")
    return CambioDeNorma(norm_id=ds1["id"], etiqueta="DS 1/2013", titulo=ds1["title"], version_anterior="v1",
                         version_nueva="v2", vigente_desde="2026-09-15", modificados=["18"], nuevos=["19 bis"])


@pytest.fixture
def cuentas():
    return [CuentaDeEmpresa(D.EMPRESA_A, _token("user_demo_a", D.EMPRESA_A)),
            CuentaDeEmpresa(D.EMPRESA_B, _token("user_demo_b", D.EMPRESA_B))]


@pytest.fixture
def opciones(transporte):
    return {"transporte": transporte}


async def test_avisa_solo_a_quien_tiene_la_norma_en_su_matriz(cuentas, opciones, base_consulta, estado_backend):
    inf = await monitorear(backend_url=BACKEND, cuentas=cuentas, base=base_consulta, cambios=[_cambio_ds1()],
                           novedades=[], opciones_cliente=opciones)
    notas = estado_backend.datos["notificaciones"]
    assert [n["tenant_id"] for n in notas] == [str(D.EMPRESA_A)]
    [n] = notas
    assert n["recipient_user_id"] == str(D.USUARIO_A)
    assert "DS 1/2013" in n["subject"] and "Artículos modificados: 18" in n["body"] and "19 bis" in n["body"]
    assert n["context"]["origen"] == "agente_monitoreo_normativo"
    assert inf.creados == 1 and not inf.errores


async def test_una_segunda_corrida_no_duplica(cuentas, opciones, base_consulta, estado_backend):
    for _ in range(2):
        inf = await monitorear(backend_url=BACKEND, cuentas=cuentas, base=base_consulta, cambios=[_cambio_ds1()],
                               novedades=[], opciones_cliente=opciones)
    assert len(estado_backend.datos["notificaciones"]) == 1
    assert inf.creados == 0 and [a.creado for a in inf.avisos] == [False]


async def test_novedad_sma_llega_a_quien_tiene_esa_unidad(cuentas, opciones, base_sincronizador, base_consulta,
                                                          estado_backend):
    await cargar_conjunto(base_sincronizador, "unidades", (FIX / "snifa_uf.csv").read_bytes())
    nv = NovedadSMA(1078, "A-002-2013", "Autodenuncia", "Terminado - Sanción", "En curso", 7021.0,
                    "https://snifa.sma.gob.cl/Sancionatorio/Ficha/1")
    await monitorear(backend_url=BACKEND, cuentas=cuentas, base=base_consulta, cambios=[], novedades=[nv],
                     opciones_cliente=opciones)
    [n] = estado_backend.datos["notificaciones"]
    assert n["tenant_id"] == str(D.EMPRESA_A)
    assert "Planta Norte" in n["subject"] and "«En curso» → «Terminado - Sanción»" in n["body"]
    assert "7021 UTA" in n["body"] and "snifa.sma.gob.cl" in n["body"]


async def test_el_ticket_de_plataforma_no_lleva_datos_de_las_empresas(cuentas, opciones, base_consulta,
                                                                      estado_backend):
    plataforma = CuentaDePlataforma(_token("user_demo_plataforma", "platform"))
    for _ in range(2):
        inf = await monitorear(backend_url=BACKEND, cuentas=cuentas, base=base_consulta, cambios=[_cambio_ds1()],
                               novedades=[], plataforma=plataforma, opciones_cliente=opciones,
                               hoy=lambda: date(2026, 9, 22))
    [t] = estado_backend.datos["tickets"]  # uno solo, aunque corra dos veces
    assert t["category"] == "legal" and "DS 1/2013" in t["description"]
    assert "empresas con la norma en su matriz: 1" in t["description"]
    for nombre in ("Minera Andes", "Pesquera Sur", str(D.EMPRESA_A)):
        assert nombre not in t["description"]
    assert inf.ticket == t["ticket_number"]


async def test_una_cuenta_sin_permiso_no_frena_a_las_demas(opciones, base_consulta, estado_backend):
    cuentas = [CuentaDeEmpresa(D.EMPRESA_B, _token("user_demo_b", D.EMPRESA_B, permisos_demo=["catalog.read"])),
               CuentaDeEmpresa(D.EMPRESA_A, _token("user_demo_a", D.EMPRESA_A))]
    inf = await monitorear(backend_url=BACKEND, cuentas=cuentas, base=base_consulta, cambios=[_cambio_ds1()],
                           novedades=[], opciones_cliente=opciones)
    assert len(inf.errores) == 1 and str(D.EMPRESA_B) in inf.errores[0]
    assert len(estado_backend.datos["notificaciones"]) == 1


async def test_sin_cambios_no_hace_nada(cuentas, opciones, base_consulta, estado_backend):
    inf = await monitorear(backend_url=BACKEND, cuentas=cuentas, base=base_consulta, cambios=[], novedades=[],
                           opciones_cliente=opciones)
    assert inf.avisos == [] and estado_backend.peticiones == []
