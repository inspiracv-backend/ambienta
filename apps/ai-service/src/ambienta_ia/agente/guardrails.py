"""
Chequeos antes y después del modelo.

La entrada: corta lo obvio y lo registra. **No es la defensa**: un filtro de texto siempre se
esquiva reformulando. La defensa es que las herramientas no pueden salirse de la empresa del
token (D-12) y que ninguna ejecuta SQL (D-11).

La salida: si no hubo evidencia normativa, no puede haber afirmaciones normativas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

LARGO_MAXIMO = 2000

PATRONES_SOSPECHOSOS = [
    r"ignor[áa]\s+(todas?\s+)?(las\s+)?instrucciones",
    r"olvid[áa]\s+(todo|las\s+instrucciones)",
    r"system\s*prompt",
    r"actu[áa]\s+como\s+(si\s+fueras\s+)?(administrador|superadmin|root)",
    r"(empresa|tenant)[_\s]?id\s*[=:]",
    r"\bDROP\s+TABLE\b",
    r"\bSELECT\b.+\bFROM\b",
]

AFIRMACIONES_NORMATIVAS = [
    r"\bart[íi]culo\s+\d+",
    r"seg[úu]n\s+(la\s+|el\s+)?(norma|ley|reglamento|decreto)",
    r"est[áa]s?\s+obligad",
    r"\bdeber[áa]n?\b",
    r"el\s+plazo\s+es",
]


@dataclass
class Veredicto:
    pasa: bool
    motivo: str | None = None


def validar_entrada(texto: str) -> Veredicto:
    if not texto or len(texto.strip()) < 2:
        return Veredicto(False, "La consulta está vacía.")
    if len(texto) > LARGO_MAXIMO:
        return Veredicto(False, f"La consulta supera los {LARGO_MAXIMO} caracteres.")
    for patron in PATRONES_SOSPECHOSOS:
        if re.search(patron, texto, re.IGNORECASE):
            return Veredicto(False, "La consulta contiene instrucciones no permitidas.")
    return Veredicto(True)


def afirma_normativa(texto: str) -> bool:
    return any(re.search(p, texto, re.IGNORECASE) for p in AFIRMACIONES_NORMATIVAS)
