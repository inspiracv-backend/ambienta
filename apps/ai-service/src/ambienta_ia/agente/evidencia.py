"""
El registro de evidencia de una consulta.

Cada fragmento que una herramienta devuelve recibe una etiqueta `[F1]`, `[F2]`... y el modelo
tiene que citar con esas etiquetas. Después, en código, se verifica que cada etiqueta citada
exista en este registro (D-08): el modelo puede escribir "artículo 99 de la Ley 19.300" con
total naturalidad; lo que no puede es inventar una etiqueta que ninguna herramienta devolvió
sin que se note.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..recuperacion import Cita

RE_ETIQUETA = re.compile(r"\[F(\d+)\]")


@dataclass
class Registro:
    fragmentos: dict[int, Cita] = field(default_factory=dict)
    llamadas_normativas: int = 0
    llamadas_normativas_vacias: int = 0
    datos_estructurados: int = 0  # respuestas de herramientas que no son normativa (obligaciones, etc.)
    datos: list[str] = field(default_factory=list)  # su texto, para que el revisor lo vea

    def agregar_datos(self, herramienta: str, texto: str) -> None:
        self.datos_estructurados += 1
        self.datos.append(f"[{herramienta}]\n{texto}")

    def agregar(self, cita: Cita) -> str:
        for n, c in self.fragmentos.items():
            if c == cita:
                return f"[F{n}]"
        n = len(self.fragmentos) + 1
        self.fragmentos[n] = cita
        return f"[F{n}]"

    @property
    def hay_evidencia(self) -> bool:
        return bool(self.fragmentos) or self.datos_estructurados > 0

    def etiquetas_citadas(self, texto: str) -> list[int]:
        return [int(m) for m in RE_ETIQUETA.findall(texto)]

    def etiquetas_invalidas(self, texto: str) -> list[int]:
        return [n for n in self.etiquetas_citadas(texto) if n not in self.fragmentos]

    def citas_de(self, texto: str) -> list[Cita]:
        vistas: list[Cita] = []
        for n in self.etiquetas_citadas(texto):
            c = self.fragmentos.get(n)
            if c is not None and c not in vistas:
                vistas.append(c)
        return vistas

    def texto_legible(self, texto: str) -> str:
        """Reemplaza [F3] por (Ley 19.300, art. 11) para mostrarle al usuario."""

        def reemplazo(m: re.Match[str]) -> str:
            c = self.fragmentos.get(int(m.group(1)))
            if c is None:
                return ""
            return f"({c.norma}, art. {c.articulo})" if c.articulo else f"({c.norma})"

        return re.sub(r"\s*\[F(\d+)\]", lambda m: " " + reemplazo(m), texto).replace("  ", " ").strip()

    def resumen(self) -> str:
        """
        Lo que ve el revisor: los fragmentos con su etiqueta y los datos de la empresa que
        devolvieron las herramientas. Sin los datos, una respuesta correcta sobre obligaciones
        se rechazaba por "no hay evidencia".
        """
        partes = [f"[F{n}] {c.etiqueta}\n{c.texto}" for n, c in self.fragmentos.items()]
        if self.datos:
            partes.append("Datos de la empresa (no llevan etiqueta [F#]):\n\n" + "\n\n".join(self.datos))
        return "\n\n".join(partes)
