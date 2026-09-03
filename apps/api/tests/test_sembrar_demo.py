"""La semilla de demostracion no puede inventar ni pisar nada.

## Que protege

La tarea existe para que el sistema se pueda **mostrar**: con la base recien
creada, ninguna empresa tiene sector declarado, el CORE responde `sin_perfil` y
el tablero se ve vacio por falta de datos, no de funcionalidad.

Pero una tarea que siembra tiene dos formas de hacer dano, y las dos son
silenciosas:

1. **Correr donde no debe.** Datos de ejemplo en la base de un cliente no se
   deshacen con una disculpa.
2. **Sembrar sobre un catalogo falso.** Con las 8 normas de ejemplo, la
   demostracion mostraria normativa que no existe — y quien la vea va a creer
   que el sistema trae normativa real.

Estas pruebas fijan las dos negativas, que son mas importantes que lo que la
tarea hace cuando todo esta bien.
"""
from __future__ import annotations

import pytest

from app.config import get_settings
from app.tareas import sembrar_demo


class TestNoCorreDondeNoDebe:
    def test_en_produccion_se_niega(self, monkeypatch) -> None:
        """La negativa mas importante del modulo."""
        monkeypatch.setattr(get_settings(), "environment", "production", raising=False)

        with pytest.raises(sembrar_demo.NoSePuedeSembrar, match="production"):
            sembrar_demo.sembrar(db=None)  # ni siquiera llega a tocar la sesion

    def test_comprueba_el_entorno_ANTES_de_abrir_la_sesion(self, monkeypatch) -> None:
        """Se le pasa `None` como sesion a proposito: si la comprobacion
        estuviera despues de la primera consulta, esto reventaria con
        `AttributeError` en vez de con el mensaje que explica por que."""
        monkeypatch.setattr(get_settings(), "environment", "production", raising=False)

        with pytest.raises(sembrar_demo.NoSePuedeSembrar):
            sembrar_demo.sembrar(db=None)


class TestElSectorSaleDelGiro:
    """El sector tiene que ser coherente con la empresa, no el que da mas normas.

    La primera version elegia el sector con mas normativa clasificada, y a una
    minera le dejaba declarado *suministro de agua y gestion de residuos*.
    Nadie que mire la demostracion se lo cree, y una demostracion que no se cree
    no demuestra nada.
    """

    @pytest.mark.parametrize(
        "giro,esperado",
        [
            ("Extracción de minerales metálicos no ferrosos", 2),
            ("Extraccion de minerales metalicos no ferrosos", 2),  # sin tildes
            ("Cultivo de frutales y ganadería menor", 1),
            ("Fabricación de productos manufacturados", 3),
            ("Generación de electricidad y distribución de gas", 4),
            ("Tratamiento de aguas servidas y residuos", 5),
            ("Construcción de obras civiles", 6),
            ("Comercio al por mayor de insumos", 7),
            ("Transporte y logística de carga", 8),
        ],
    )
    def test_reconoce_el_rubro(self, giro, esperado) -> None:
        sector, motivo = sembrar_demo._sector_segun_el_giro(giro)

        assert sector == esperado
        assert "por el giro" in motivo

    def test_un_giro_que_no_dice_nada_cae_al_de_respaldo(self) -> None:
        """Y lo **dice**, en vez de aparentar que lo dedujo."""
        sector, motivo = sembrar_demo._sector_segun_el_giro("Servicios varios")

        assert sector == sembrar_demo.SECTOR_DE_RESPALDO
        assert "respaldo" in motivo

    def test_sin_giro_tampoco_inventa(self) -> None:
        sector, motivo = sembrar_demo._sector_segun_el_giro(None)

        assert sector == sembrar_demo.SECTOR_DE_RESPALDO
        assert "respaldo" in motivo


class TestLaMezclaDeEstados:
    """Lo que se siembra tiene que parecerse a una empresa a mitad de camino."""

    def test_los_estados_existen_en_la_base(self) -> None:
        """El CHECK de `article_compliance` admite estos cinco y ninguno mas.
        Un estado inventado no falla al escribirlo desde Python: falla en el
        `INSERT`, con un mensaje que no se parece a la causa."""
        admitidos = {"compliant", "non_compliant", "partial", "not_applicable", "pending"}

        assert {estado for estado, _ in sembrar_demo.MEZCLA} <= admitidos

    def test_hay_de_los_tres_colores_y_ademas_pendientes(self) -> None:
        """Una matriz toda en verde no muestra el producto; una toda en rojo
        tampoco; y una sin nada pendiente esconde justo lo que el sistema
        organiza, que es el trabajo que falta."""
        estados = {estado for estado, _ in sembrar_demo.MEZCLA}

        assert {"compliant", "partial", "non_compliant", "pending"} <= estados

    def test_toda_evaluacion_sembrada_lleva_su_motivo(self) -> None:
        """Menos las pendientes, que no se evaluaron y por eso no tienen que
        explicar nada."""
        sin_motivo = [e for e, motivo in sembrar_demo.MEZCLA if e != "pending" and not motivo]

        assert sin_motivo == []

    def test_las_sembradas_se_pueden_distinguir_de_las_reales(self) -> None:
        """`assessment_reason` lleva la marca. Sin ella, nadie puede separar
        despues lo que sembro una tarea de lo que evaluo una persona."""
        assert sembrar_demo.MARCA
        for estado, motivo in sembrar_demo.MEZCLA:
            if estado != "pending":
                assert motivo  # el prefijo lo agrega la tarea al escribir


class TestLaClasificacionTransversalSeComprueba:
    """`db/23` corre al inicializar la base, y la BCN trae normas despues.

    Medido: tras sincronizar, el DS 1 quedaba con **cero** sectores y el DS 40
    con uno, porque no existian —o no tenian su tipo definitivo— cuando corrio
    la migracion. La demostracion seguia funcionando y la empresa recibia menos
    normativa de la que le corresponde, sin que nada fallara.

    Estas pruebas fijan la comprobacion, no la migracion: lo que importa es que
    el desfase **no pase inadvertido**.
    """

    def test_la_comprobacion_existe_y_se_llama_al_sembrar(self) -> None:
        import inspect

        assert hasattr(sembrar_demo, "_comprobar_clasificacion")
        cuerpo = inspect.getsource(sembrar_demo.sembrar)
        assert "_comprobar_clasificacion" in cuerpo, (
            "La comprobacion existe pero `sembrar` no la llama. Es exactamente "
            "el patron que este proyecto viene persiguiendo: la pieza escrita, "
            "probada, y sin nadie que la use."
        )

    def test_el_mensaje_dice_el_comando_para_arreglarlo(self) -> None:
        """Un error que no dice como salir de el obliga a leer el codigo."""
        import inspect

        fuente = inspect.getsource(sembrar_demo._comprobar_clasificacion)

        assert "23_normativa_transversal.sql" in fuente
        assert "psql" in fuente

    def test_se_comprueba_ANTES_de_escribir_nada(self) -> None:
        """Si se comprobara al final, la siembra ya habria dejado una matriz
        incompleta y el aviso llegaria tarde."""
        import inspect

        cuerpo = inspect.getsource(sembrar_demo.sembrar)
        assert cuerpo.index("_comprobar_clasificacion") < cuerpo.index("_declarar_perfil")
