"""Comprueba que el correo sale de verdad.

    python -m app.tareas.comprobar_correo destino@ejemplo.cl

**Manda un correo real.** Es lo unico que demuestra que la configuracion sirve:
que la llave tenga la forma correcta no prueba nada, y el error mas comun
—dominio del remitente sin verificar en Resend— **no se detecta hasta el primer
envio**, que sin esto seria el primer aviso de vencimiento de un cliente.

Las pruebas de `test_correo.py` no salen a internet a proposito: comprueban la
clasificacion de la respuesta, que es donde puede haber un error nuestro. Que
Resend acepte una peticion no es algo que podamos arreglar. Esto se corre a
mano, una vez, al configurar.
"""
from __future__ import annotations

import sys

from ..services import correo
from ..services.despacho import ErrorDeConfiguracion, ErrorDeEnvio, ErrorPermanente

ASUNTO = "Ambienta · comprobacion del envio de correo"

CUERPO = """Esto es una comprobacion de la configuracion de correo de Ambienta.

Si llego, el envio de avisos de vencimiento funciona: la llave sirve y el
dominio del remitente esta verificado.

No hay que responder este mensaje.
"""


def main(argv: list[str] | None = None) -> int:
    argumentos = argv if argv is not None else sys.argv[1:]
    if len(argumentos) != 1 or "@" not in argumentos[0]:
        print("\n  Uso: python -m app.tareas.comprobar_correo destino@ejemplo.cl\n")
        print("  Hace falta una direccion real: la comprobacion manda un correo.\n")
        return 2

    destino = argumentos[0]
    print("\nComprobando el envio de correo\n")

    if not correo.esta_configurado():
        print("  NO CONFIGURADO.")
        print(f"  Faltan {', '.join(correo._faltantes())} en el `.env`.")
        print("  Ver `.env.example` para que va en cada una.\n")
        return 1

    transporte = correo.transporte_configurado()
    assert transporte is not None  # `esta_configurado` ya lo garantizo

    print(f"  remitente: {transporte._remitente}")
    print(f"  destino  : {destino}")
    print("  enviando...")

    try:
        identificador = transporte.enviar(
            destino=destino, asunto=ASUNTO, cuerpo=CUERPO, contexto={}
        )
    except ErrorDeConfiguracion as exc:
        print(f"\n  LA CONFIGURACION NO SIRVE.\n  {exc}\n")
        print("  Lo que suele ser:")
        print("   - La llave de Resend esta mal copiada o fue revocada.")
        print("   - El dominio de CORREO_REMITENTE no esta verificado en Resend.")
        print("     Resend solo deja enviar desde dominios que uno probo que controla.")
        return 1
    except ErrorPermanente as exc:
        print(f"\n  RECHAZADO SIN REINTENTO.\n  {exc}\n")
        print("  Suele ser la direccion de destino, o el formato del remitente:")
        print("  tiene que ser `Nombre <buzon@dominio.cl>` o `buzon@dominio.cl`.")
        return 1
    except ErrorDeEnvio as exc:
        print(f"\n  NO SE PUDO ENTREGAR AHORA.\n  {exc}\n")
        print("  Esto el despachador lo reintentaria solo. Si persiste, mirar")
        print("  el estado de Resend o la salida a internet del servidor.")
        return 1

    print(f"  aceptado por Resend con id {identificador}")
    print("\n  Resend lo acepto. **Eso no es lo mismo que entregado**: revisa la")
    print(f"  bandeja de {destino}, y el spam. Si no llego, el problema esta en")
    print("  la reputacion del dominio (SPF/DKIM), no en esta configuracion.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
