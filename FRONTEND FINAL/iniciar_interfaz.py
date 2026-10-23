# -*- coding: utf-8 -*-
"""launcher for laser ufe gui"""

import sys
import os

#add project root to sys path
directorio_raiz = os.path.dirname(os.path.abspath(__file__))
if directorio_raiz not in sys.path:
    sys.path.insert(0, directorio_raiz)

from interfaz.interfaz_app import AppLaserCTk


def iniciar():
    """init app and bind safe close event"""
    app = AppLaserCTk()
    #intercept close event for clean shutdown
    app.protocol("WM_DELETE_WINDOW", app._on_cerrar_aplicacion)
    app.mainloop()


if __name__ == "__main__":
    iniciar()
