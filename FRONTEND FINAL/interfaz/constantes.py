# -*- coding: utf-8 -*-
"""
interfaz/constantes.py — Constantes de Diseño y Widgets (Cyber-Brutalism)
"""

import os
import sys
import time
import ctypes
import customtkinter as ctk

# =============================================================================
# CONSTANTES DE DISEÑO (CYBER-BRUTALISM)
# =============================================================================
COLOR_BG = "#EDF0F4"
COLOR_CARD = "#FFFFFF"
COLOR_BORDER = "#231F20"
COLOR_TEXT = "#231F20"

COLOR_YELLOW = "#FFB200"
COLOR_RED = "#FF3434"
COLOR_BLUE = "#3A43EF"
COLOR_GREEN = "#5DFF34"
COLOR_ORANGE = "#FF9A34"
COLOR_PAUSE = "#A5B4FC"
COLOR_TIMER_BG = "#C8CDD5"
COLOR_VECTOR_GRAY = "#CCD1D9"
COLOR_CYAN_HALO = "#B4E6FF"
COLOR_TERMINAL_BG = "#231F20"

FONT_BRUNO = "Bruno Ace"
FONT_TEACHERS = "Teachers"

# Geometría Cyber-Brutalist: Simples cuadrados sin bordes redondeados y mayor grosor
BRUTAL_CORNER = 0
BRUTAL_BORDER = 2
BRUTAL_BORDER_THICK = 3

_DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))


class BrutalOptionMenu(ctk.CTkOptionMenu):
    """
    CTkOptionMenu con comportamiento Cyber-Brutalism mejorado:
    - Se cierra automáticamente al presionar de nuevo sobre la flechita/botón.
    - Respeta esquinas cuadradas y estética brutalista.
    """
    def __init__(self, *args, **kwargs):
        if "corner_radius" not in kwargs:
            kwargs["corner_radius"] = BRUTAL_CORNER
        super().__init__(*args, **kwargs)
        self._last_close_time = 0.0

        if hasattr(self, "_dropdown_menu"):
            self._dropdown_menu.bind("<Unmap>", self._on_menu_unmap, add="+")

    def _on_menu_unmap(self, event=None):
        self._last_close_time = time.time()

    def _open_dropdown_menu(self):
        # Si se cerró hace menos de 350 ms, el usuario hizo clic para cerrar el menú
        if time.time() - self._last_close_time < 0.35:
            return
        super()._open_dropdown_menu()


def cargar_fuentes_windows():
    """Registra en memoria las tipografías TrueType para Tkinter en Windows."""
    rutas_fuentes = [
        os.path.join(_DIR_ACTUAL, "fonts", "BrunoAce-Regular.ttf"),
        os.path.join(_DIR_ACTUAL, "fonts", "Teachers-Regular.ttf"),
    ]
    for r in rutas_fuentes:
        if os.path.exists(r):
            try:
                ctypes.windll.gdi32.AddFontResourceExW(r, 0x10, 0)
            except Exception:
                pass


def configurar_dpi_awareness():
    """Habilita DPI Awareness en Windows para evitar distorsiones en pantallas de alta densidad."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
