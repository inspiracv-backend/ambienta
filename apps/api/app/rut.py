"""El RUT: validarlo, normalizarlo y darle formato.

Es credencial de acceso —el Cliente Invitado entra con RUT y clave (RF-01,
RF-02), y quien entro por Google puede fijar una clave local asociada a su RUT
(RF-06)— y ademas dato de negocio que aparece en informes.

## El mismo calculo esta escrito dos veces, a proposito

El gemelo vive en `apps/web/lib/rut.ts`. No pueden importarse entre si, asi que
la sincronia es manual — **y este repositorio ya se quemo con eso**: hubo codigo
leyendo columnas que no existian sin que nada lo detectara.

Aca el riesgo es peor que una columna. Si las dos implementaciones difieren,
**un RUT valido en la pantalla es invalido en la API**, y la persona ve "RUT
incorrecto" sobre un RUT que es suyo — un fallo que se lee como un error de
quien escribe y no del sistema.

Por eso los dos lados comparten los mismos casos de prueba, incluido el
verificador `K` y los tres formatos de escritura. Si alguien toca uno solo, la
suite del otro lo dice.

## Lo que el verificador prueba y lo que no

El digito verificador es lo unico comprobable sin consultar al Registro Civil.
**No prueba que el RUT sea de quien lo escribe**: solo que no es un numero
inventado al azar. Cuando el RUT es credencial, esa distincion importa — y hoy
nada mas la cubre.
"""
from __future__ import annotations

import re

#: Multiplicadores del modulo 11, de derecha a izquierda: 2,3,4,5,6,7 y vuelve.
_CICLO = (2, 3, 4, 5, 6, 7)

_SEPARADORES = re.compile(r"[.\-\s]")
_SOLO_DIGITOS = re.compile(r"^\d+$")
_VERIFICADOR = re.compile(r"^[0-9K]$")


def digito_verificador(cuerpo: int) -> str:
    """El digito que le corresponde a ese numero, por modulo 11.

    `11` da `0` y `10` da `K`. Es la convencion chilena y no es arbitraria: el
    resto solo puede valer de 0 a 10, y con once simbolos posibles sobre diez
    digitos hace falta una letra.
    """
    suma = 0
    n = cuerpo
    i = 0
    while n > 0:
        suma += (n % 10) * _CICLO[i % len(_CICLO)]
        n //= 10
        i += 1

    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def normalizar(rut: str | None) -> str | None:
    """El RUT en su forma canonica: `12345678-K`, sin puntos.

    **Se guarda normalizado, no como lo escribio la persona.** El mismo RUT se
    escribe de tres formas —`12.345.678-5`, `12345678-5`, `123456785`— y sin
    normalizar la comprobacion de "este RUT ya esta en uso" no encuentra el
    duplicado: para la base son tres cadenas distintas.

    Devuelve `None` si no se puede interpretar. **No lanza**: quien llama suele
    estar validando lo que alguien escribio, y una excepcion ahi obliga a
    envolver cada uso en un `try`.
    """
    if not rut:
        return None

    limpio = _SEPARADORES.sub("", rut).upper()
    if len(limpio) < 2:
        return None

    cuerpo, dv = limpio[:-1], limpio[-1]
    if not _SOLO_DIGITOS.match(cuerpo) or not _VERIFICADOR.match(dv):
        return None

    # Se quitan los ceros a la izquierda: `01.234.567-4` y `1.234.567-4` son el
    # mismo RUT, y guardarlos distinto los volveria dos personas.
    sin_ceros = cuerpo.lstrip("0")
    if not sin_ceros:
        return None

    return f"{sin_ceros}-{dv}"


def es_valido(rut: str | None) -> bool:
    """Si el RUT se puede interpretar **y** su digito verificador cierra."""
    normalizado = normalizar(rut)
    if normalizado is None:
        return False

    cuerpo, dv = normalizado.split("-")
    return digito_verificador(int(cuerpo)) == dv


def con_formato(rut: str | None) -> str | None:
    """El RUT como se muestra a una persona: `12.345.678-5`.

    Solo para mostrar. **Lo que se guarda y lo que se compara es
    `normalizar()`**, sin puntos: los separadores son decoracion y meterlos en
    la base convierte cada consulta en una adivinanza de formato.
    """
    normalizado = normalizar(rut)
    if normalizado is None:
        return None

    cuerpo, dv = normalizado.split("-")
    grupos = []
    while len(cuerpo) > 3:
        grupos.insert(0, cuerpo[-3:])
        cuerpo = cuerpo[:-3]
    grupos.insert(0, cuerpo)
    return f"{'.'.join(grupos)}-{dv}"
