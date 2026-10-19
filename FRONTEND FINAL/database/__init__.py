# -*- coding: utf-8 -*-
"""
database/__init__.py — API pública del módulo de persistencia SQLite3

Exporta las clases y funciones principales para uso desde la HMI
y la lógica del sistema láser.
"""

from .gestor_db import GestorDB
from .recetas import GestorRecetas, MODOS_PROCESO_VALIDOS
from .trazabilidad import GestorTrazabilidad

__all__ = [
    "GestorDB",
    "GestorRecetas",
    "GestorTrazabilidad",
    "MODOS_PROCESO_VALIDOS",
]
