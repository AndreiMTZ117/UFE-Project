# -*- coding: utf-8 -*-
"""
database/__init__.py — API pública del módulo de persistencia SQLite3

Exporta las clases y funciones principales para uso desde principal.py
y desde la futura GUI/HMI.
"""

from .gestor_db import GestorDB
from .recetas import GestorRecetas
from .trazabilidad import GestorTrazabilidad

__all__ = [
    "GestorDB",
    "GestorRecetas",
    "GestorTrazabilidad",
]
