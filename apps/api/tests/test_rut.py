"""El RUT, en Python. **Gemelo de `apps/web/lib/rut.test.ts`.**

Los dos archivos comparten los mismos casos, con los mismos valores. Es
deliberado y es lo unico que impide que las dos implementaciones se
desincronicen: no pueden importarse entre si, asi que la sincronia depende de
que los dos lados se prueben contra lo mismo.

**Si difieren, un RUT valido en la pantalla es invalido en la API** — y la
persona ve "RUT incorrecto" sobre un RUT que es suyo, un fallo que se lee como
un error de quien escribe y no del sistema.

Al agregar un caso aca, agregarlo alla. La lista de constantes de abajo esta
duplicada literal a proposito, para que la comparacion sea visual.
"""
from __future__ import annotations

import pytest

from app.rut import con_formato, digito_verificador, es_valido, normalizar

#: RUTs reales por su estructura, con verificador correcto. Mismos valores que
#: en el gemelo de TypeScript.
VALIDOS = [
    ("12345678-5", "12345678-5"),
    ("12.345.678-5", "12345678-5"),
    ("123456785", "12345678-5"),
    # El verificador K, que es el que se olvida: el resto 10 no cabe en un
    # digito, y una implementacion que solo maneje 0-9 lo rechaza.
    ("11111111-1", "11111111-1"),
    ("22222222-2", "22222222-2"),
    ("5126663-3", "5126663-3"),
    # El verificador K, calculado — no elegido de memoria. La primera version de
    # esta tabla traia valores inventados y las pruebas los delataron.
    ("1000005-K", "1000005-K"),
    ("1000005-k", "1000005-K"),
    # Y el verificador 0, el otro caso que no es un resto directo.
    ("1000013-0", "1000013-0"),
]

INVALIDOS = [
    "12345678-4",  # verificador que no cierra
    "",
    "-",
    "5",
    "abcdefgh-1",
    "12345678-X",  # X no es un verificador posible
    "0-0",  # cuerpo vacio tras quitar ceros
    None,
]


class TestElDigitoVerificador:
    @pytest.mark.parametrize(
        "cuerpo,esperado",
        [
            (12345678, "5"),
            (11111111, "1"),
            (5126663, "3"),
            # **El caso K.** Resto 10, que no es un digito.
            (1000005, "K"),
            # **El caso 0.** Resto 11, que tampoco lo es.
            (1000013, "0"),
        ],
    )
    def test_calcula_lo_que_corresponde(self, cuerpo: int, esperado: str) -> None:
        assert digito_verificador(cuerpo) == esperado

    def test_el_resto_diez_da_k_y_no_un_numero(self) -> None:
        """Es la convencion chilena y no es arbitraria: con once restos posibles
        sobre diez digitos hace falta un simbolo mas."""
        assert digito_verificador(1000005) == "K"


class TestNormalizar:
    @pytest.mark.parametrize("entrada,esperado", VALIDOS)
    def test_los_tres_formatos_dan_lo_mismo(self, entrada: str, esperado: str) -> None:
        """**Sin esto, "este RUT ya esta en uso" no encuentra el duplicado.**

        El mismo RUT escrito con puntos, sin puntos y sin guion son tres cadenas
        distintas para la base.
        """
        assert normalizar(entrada) == esperado

    def test_los_ceros_a_la_izquierda_no_hacen_otro_rut(self) -> None:
        """`01.234.567-4` y `1.234.567-4` son la misma persona. Guardarlos
        distinto la volveria dos."""
        assert normalizar("01234567-4") == normalizar("1234567-4")

    def test_la_k_minuscula_se_guarda_mayuscula(self) -> None:
        assert normalizar("1000005-k") == "1000005-K"

    def test_un_verificador_imposible_no_se_normaliza(self) -> None:
        """`X` no es un verificador que exista, asi que la cadena no es un RUT.

        Se rechaza **aca**, al interpretar, y no solo al validar el modulo 11:
        si `normalizar()` lo dejara pasar, cualquier cosa terminada en letra
        quedaria guardada como si fuera un RUT con formato correcto.
        """
        assert normalizar("12345678-X") is None
        assert normalizar("12345678-Z") is None

    def test_lo_que_no_se_puede_interpretar_da_none_y_no_lanza(self) -> None:
        """**No lanza a proposito.** Quien llama esta validando lo que alguien
        escribio; una excepcion ahi obliga a envolver cada uso en un `try`."""
        for malo in ["", "-", "abc", None, "   "]:
            assert normalizar(malo) is None


class TestEsValido:
    @pytest.mark.parametrize("entrada,_", VALIDOS)
    def test_acepta_los_validos(self, entrada: str, _: str) -> None:
        assert es_valido(entrada) is True

    @pytest.mark.parametrize("entrada", INVALIDOS)
    def test_rechaza_los_invalidos(self, entrada) -> None:
        assert es_valido(entrada) is False

    def test_un_verificador_cambiado_por_uno_lo_invalida(self) -> None:
        """Es para lo que sirve el modulo 11: detectar el digito tipeado mal.

        Sin esta comprobacion, un error de tipeo crea una credencial que no le
        corresponde a nadie y que nadie puede reclamar.
        """
        assert es_valido("12345678-5") is True
        assert es_valido("12345678-6") is False

    def test_el_verificador_solo_dice_que_el_numero_cierra(self) -> None:
        """**No prueba que el RUT sea de quien lo escribe.**

        Queda escrito como prueba porque es la limitacion que importa cuando el
        RUT es credencial de acceso, y hoy nada mas la cubre.
        """
        # Un RUT valido cualquiera, que no es de nadie en particular.
        assert es_valido("11111111-1") is True


class TestConFormato:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("123456785", "12.345.678-5"),
            ("12345678-5", "12.345.678-5"),
            ("5126663-3", "5.126.663-3"),
            ("1000005-K", "1.000.005-K"),
        ],
    )
    def test_agrupa_de_a_tres_desde_la_derecha(
        self, entrada: str, esperado: str
    ) -> None:
        assert con_formato(entrada) == esperado

    def test_es_solo_para_mostrar(self) -> None:
        """Lo que se guarda y se compara es `normalizar()`, sin puntos.

        Meter los separadores en la base convierte cada consulta en una
        adivinanza de formato.
        """
        assert con_formato("12345678-5") != normalizar("12345678-5")

    def test_lo_invalido_da_none(self) -> None:
        assert con_formato("nada") is None


class TestLosDosLenguajesCoinciden:
    """Fija los valores exactos que el gemelo de TypeScript tiene que devolver.

    No puede ejecutar el otro lado, asi que **lo que ata las dos
    implementaciones son estos numeros**: si alguien cambia uno solo, la suite
    del otro falla contra la misma tabla.
    """

    def test_la_tabla_compartida_de_validos(self) -> None:
        assert [normalizar(e) for e, _ in VALIDOS] == [n for _, n in VALIDOS]

    def test_la_tabla_compartida_de_invalidos(self) -> None:
        assert all(not es_valido(x) for x in INVALIDOS)
