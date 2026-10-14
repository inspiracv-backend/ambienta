"""
Adaptador SNIFA / SMA (issue #134 de Ambienta, SPEC-10).

La SMA publica sus datos abiertos como archivos CSV en carpetas públicas de Google Drive,
enlazadas desde https://snifa.sma.gob.cl/DatosAbiertos. No hay API. Se usan tres conjuntos:

- **Unidades fiscalizables e instrumentos** (~33.700 filas): cada unidad con sus RCA, planes, etc.
- **Sancionatorios** (~3.500): procesos con estado, multa en UTA y enlace a la ficha.
- **Fiscalizaciones** (~59.000): inspecciones por año y organismo.

Ninguno trae RUT. El cruce con una empresa se hace por el id de unidad fiscalizable guardado en
`facilities.environmental_identifiers` del backend; si no está, se proponen candidatas por
nombre y ubicación, como sugerencia y no como dato.
"""

from .carga import ResultadoCarga, cargar_conjunto, sincronizar_snifa
from .consulta import Antecedentes, antecedentes, candidatas, unidades_por_id_sea

__all__ = ["ResultadoCarga", "cargar_conjunto", "sincronizar_snifa", "Antecedentes", "antecedentes", "candidatas", "unidades_por_id_sea"]
