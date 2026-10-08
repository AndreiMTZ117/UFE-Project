# -*- coding: utf-8 -*-
"""
iniciar_interfaz.py — Lanzador directo de la HMI UFE Laser (CustomTkinter)

Ejecución:
    python iniciar_interfaz.py
"""

import sys
import os

# Añadir directorio raíz al PYTHONPATH
directorio_raiz = os.path.dirname(os.path.abspath(__file__))
if directorio_raiz not in sys.path:
    sys.path.insert(0, directorio_raiz)

from interfaz.interfaz_app import iniciar

if __name__ == "__main__":
    iniciar()
