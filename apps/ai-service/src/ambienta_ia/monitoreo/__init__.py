"""
Agente de monitoreo normativo (issue #137 de Ambienta, RF-61, SPEC-11).

Detecta cambios que afectan a una empresa y **escribe** en el sistema sin que un humano lo
dispare: notificaciones para cada empresa afectada y un ticket para el equipo de plataforma. Por
eso actúa con identidad propia (una cuenta por empresa), como pide el análisis de actores de
Ambienta: en el registro de actividades tiene que figurar el agente, no una persona.

Dos fuentes:

- El catálogo: una norma que cambió de versión (`sincronizar` devuelve qué artículos se
  modificaron, cuáles son nuevos y cuáles se derogaron). Se avisa a las empresas que la tienen
  en su matriz legal, al responsable de esa norma.
- SNIFA: un proceso sancionatorio nuevo, o que cambió de estado, en una unidad fiscalizable
  vinculada a una instalación de la empresa.
"""

from .agente import (
    AvisoEmitido,
    CuentaDeEmpresa,
    CuentaDePlataforma,
    InformeMonitoreo,
    NovedadSMA,
    monitorear,
)

__all__ = ["AvisoEmitido", "CuentaDeEmpresa", "CuentaDePlataforma", "InformeMonitoreo", "NovedadSMA", "monitorear"]
