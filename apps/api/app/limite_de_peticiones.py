"""Un tope de peticiones para las rutas publicas del invitado.

## Que problema resuelve, y cual no

`POST /credenciales` no pide token: esa es la funcionalidad (RF-02). Sin tope,
quien tenga el enlace puede pedir credenciales sin parar. **Ninguna de ellas
abre nada de negocio** —esa sigue siendo la contencion de verdad— pero la tabla
crece, y con ella lo que hay que respaldar y rotar.

Tambien acota el probar claves al azar contra `/sesion`. Ahi el tope importa
mas: la clave son 6 caracteres de un alfabeto de 32, o sea 32^6 combinaciones.
Suena mucho, pero **sin limite un script las recorre**; con limite deja de ser
un camino.

**No es proteccion contra un ataque distribuido.** Cuenta por IP, y quien tenga
muchas IP pasa igual. Para eso hace falta algo delante de la aplicacion —el
proxy, o el proveedor— y no se resuelve aca. Se deja escrito para que nadie lea
"tiene rate limiting" y lo de por cerrado.

## En memoria, y eso tiene consecuencias

El contador vive en el proceso. Con varios trabajadores, cada uno lleva el suyo
y el tope efectivo se multiplica por la cantidad de procesos. Es aceptable para
lo que se quiere evitar —el abuso trivial y accidental— y **no lo seria** si
esto fuera la unica barrera de algo valioso.

Con Redis seria exacto, pero hoy no hay Redis en el despliegue y meterlo por
esto seria una pieza de infraestructura nueva para un tope aproximado. Cuando
entre el worker, este contador deberia mudarse ahi.
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock

from fastapi import HTTPException, Request, status


class Tope:
    """Cuenta peticiones por clave en una ventana deslizante.

    Ventana deslizante y no "N por hora en punto": con ventanas fijas se pueden
    hacer 2N peticiones seguidas cruzando el borde de la hora, que es
    exactamente el momento en que el tope deberia sostener.
    """

    def __init__(self, maximo: int, ventana_segundos: int) -> None:
        self.maximo = maximo
        self.ventana = ventana_segundos
        self._visto: dict[str, deque[float]] = {}
        # Uvicorn atiende varias peticiones en hilos: sin el candado, dos que
        # llegan juntas pueden leer el mismo contador y pasar las dos.
        self._candado = Lock()

    def _limpiar(self, marcas: deque[float], ahora: float) -> None:
        while marcas and ahora - marcas[0] > self.ventana:
            marcas.popleft()

    def permite(self, clave: str) -> bool:
        ahora = time.monotonic()
        with self._candado:
            marcas = self._visto.setdefault(clave, deque())
            self._limpiar(marcas, ahora)

            if len(marcas) >= self.maximo:
                return False

            marcas.append(ahora)

            # Se barren de paso las claves que ya no tienen nada dentro de la
            # ventana. Sin esto el diccionario crece con cada IP que pase una
            # vez y no vuelva: una fuga lenta que solo se nota en produccion.
            if len(self._visto) > 5_000:
                for k in [k for k, v in self._visto.items() if not v]:
                    del self._visto[k]

            return True

    def reiniciar(self) -> None:
        """Solo para las pruebas: si no, la primera deja sin cupo a la siguiente."""
        with self._candado:
            self._visto.clear()


#: Generar credenciales. Holgado: una persona real pide una, quizas dos si se
#: equivoco. Diez por hora ya no es alguien usando el sistema.
TOPE_DE_CREDENCIALES = Tope(maximo=10, ventana_segundos=3600)

#: Intentar entrar. Mas estrecho porque aca **se estan probando claves**, y hay
#: que dejar equivocarse unas cuantas veces sin dejar recorrer el espacio.
TOPE_DE_INGRESO = Tope(maximo=20, ventana_segundos=3600)


def _quien(request: Request) -> str:
    return request.client.host if request.client else "desconocido"


def exigir_cupo(tope: Tope, request: Request, que: str) -> None:
    """Corta con 429 si se paso del tope.

    El mensaje **no dice cuanto falta ni cuantas van**: seria decirle a quien
    prueba exactamente cada cuanto reintentar para no chocar.
    """
    if not tope.permite(f"{que}:{_quien(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas peticiones. Intenta mas tarde.",
            # `Retry-After` sí es estandar y lo esperan los clientes; decir la
            # ventana entera es honesto y no filtra nada util.
            headers={"Retry-After": str(tope.ventana)},
        )
