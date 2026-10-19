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

from interfaz.interfaz_app import AppLaserCTk


def iniciar():
    """Inicializa la interfaz y enlaza el cierre seguro de ventana y hardware."""
    app = AppLaserCTk()
    # Interceptar protocolo de cierre para garantizar parada de láser y cierre limpio de hilos
    app.protocol("WM_DELETE_WINDOW", app._on_cerrar_aplicacion)
    app.mainloop()


if __name__ == "__main__":
    iniciar()
