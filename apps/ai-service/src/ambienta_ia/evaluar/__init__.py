"""
Evaluación (SPEC-08): recuperación, citas y abstención, con umbrales que no se pueden bajar.

La métrica que más importa es `falsos_positivos`: cuántas veces respondió cuando tenía que
abstenerse. Un "no sé" de más es una molestia; una respuesta inventada es una multa.
"""

from .correr import comparar_umbrales, evaluar_recuperacion, evaluar_respuestas
from .metricas import Caso, cargar_dataset, mrr, precision_en_k, recall_en_k

__all__ = [
    "Caso",
    "cargar_dataset",
    "recall_en_k",
    "precision_en_k",
    "mrr",
    "evaluar_recuperacion",
    "evaluar_respuestas",
    "comparar_umbrales",
]
