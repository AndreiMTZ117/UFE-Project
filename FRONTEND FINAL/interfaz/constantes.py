# -*- coding: utf-8 -*-
"""cyber brutalism design constants and custom widgets"""

import os
import time
import ctypes
import tkinter as tk
import customtkinter as ctk

#design constants
COLOR_BG = "#D9D9E3"             #light bluish gray window canvas
COLOR_CARD = "#FFFFFF"           #panels containers and cards
COLOR_BORDER = "#2C2C3A"         #solid carbon border 2px
COLOR_TEXT = "#1E1E24"           #primary carbon black text

COLOR_YELLOW = "#F5A623"         #industrial amber accent
COLOR_RED = "#DC2626"            #alarm red
COLOR_BLUE = "#2563EB"           #electric blue active trace
COLOR_BLUE_FADED = "#92B1F5"     #faded blue previous passes
COLOR_GREEN = "#16A34A"          #industrial green ready state
COLOR_ORANGE = "#F97316"         #dashed orange rapid jump
COLOR_PAUSE = "#E2E8F0"          #neutral pause state
COLOR_TIMER_BG = "#F4F4F8"       #timer readout background
COLOR_BOX_BG = "#F4F4F8"         #box instrumentation background
COLOR_VECTOR_GRAY = "#CBD5E1"    #neutral cad background vector
COLOR_GRID = "#E2E8F0"           #metric millimeter grid line
COLOR_MUTED = "#64748B"          #secondary technical labels
COLOR_CYAN_HALO = "#93C5FD"      #beam cursor halo
COLOR_TERMINAL_BG = "#1E1E24"    #high contrast terminal background

#protected factory recipe names
RECETAS_PREDETERMINADAS = {
    "Acrílico — Estándar",
    "Policarbonato — Alta Precisión",
    "Nylon — Grabado Suave",
    "Simulación — Prueba Vectorial",
    "Acrylic — Standard",
    "Polycarbonate — High Precision",
    "Nylon — Soft Engraving",
    "Simulation — Vector Test",
}

FONT_BRUNO = "Bruno Ace"
FONT_TEACHERS = "Teachers"
FONT_CONSOLAS = "Consolas"
FONT_SEGOE = "Segoe UI"

#square geometry without rounded corners
BRUTAL_CORNER = 0
BRUTAL_BORDER = 2
BRUTAL_BORDER_THICK = 3

_DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))


class BrutalOptionMenu(ctk.CTkOptionMenu):
    """custom option menu with auto close and square borders"""
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
        #ignore if closed within last 350ms
        if time.time() - self._last_close_time < 0.35:
            return
        super()._open_dropdown_menu()


class ToolTip:
    """tooltip text helper for tkinter and customtkinter widgets"""

    def __init__(self, widget, texto: str, retardo_ms: int = 650, ancho_px: int = 300):
        self.widget = widget
        self.texto = texto
        self.retardo_ms = retardo_ms
        self.ancho_px = ancho_px
        self._after_id = None
        self._ventana = None
        self._last_x = 0
        self._last_y = 0
        self._enlazar_recursivo(widget)

    def _enlazar_recursivo(self, w):
        for evento, handler in (("<Enter>", self._on_motion),
                                ("<Motion>", self._on_motion),
                                ("<Leave>", self._salida),
                                ("<ButtonPress>", self._ocultar),
                                ("<Key>", self._ocultar)):
            try:
                w.bind(evento, handler, add="+")
            except Exception:
                pass
        try:
            hijos = w.winfo_children()
        except Exception:
            hijos = []
        for hijo in hijos:
            self._enlazar_recursivo(hijo)

    def _on_motion(self, event=None):
        #dismiss tooltip immediately on movement
        if self._ventana is not None:
            self._ocultar()
        elif self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

        if event is not None and hasattr(event, "x_root") and hasattr(event, "y_root"):
            self._last_x = event.x_root
            self._last_y = event.y_root

        #reset timer while mouse moves
        try:
            self._after_id = self.widget.after(self.retardo_ms, self._mostrar)
        except Exception:
            self._after_id = None

    def _salida(self, event=None):
        try:
            self.widget.after(50, self._ocultar_si_fuera)
        except Exception:
            self._ocultar()

    def _ocultar_si_fuera(self):
        try:
            px, py = self.widget.winfo_pointerxy()
            x0, y0 = self.widget.winfo_rootx(), self.widget.winfo_rooty()
            dentro = (x0 <= px < x0 + self.widget.winfo_width()
                      and y0 <= py < y0 + self.widget.winfo_height())
        except Exception:
            dentro = False
        if not dentro:
            self._ocultar()

    def _mostrar(self, event=None):
        self._after_id = None
        if self._ventana is not None:
            return

        #verify pointer is still inside widget boundary
        try:
            px, py = self.widget.winfo_pointerxy()
            x0, y0 = self.widget.winfo_rootx(), self.widget.winfo_rooty()
            dentro = (x0 <= px < x0 + self.widget.winfo_width()
                      and y0 <= py < y0 + self.widget.winfo_height())
            if not dentro:
                return
        except Exception:
            return

        try:
            ventana = tk.Toplevel(self.widget)
            ventana.wm_overrideredirect(True)
            try:
                ventana.attributes("-topmost", True)
            except Exception:
                pass
            etiqueta = tk.Label(
                ventana, text=self.texto, justify="left", anchor="w",
                bg=COLOR_TERMINAL_BG, fg="#FFFFFF", bd=0,
                font=(FONT_TEACHERS, 10), wraplength=self.ancho_px,
                padx=10, pady=6, highlightthickness=2, highlightbackground=COLOR_YELLOW
            )
            etiqueta.pack()
            ventana.update_idletasks()

            #dismiss if pointer touches tooltip window
            ventana.bind("<Enter>", lambda e: self._ocultar())
            ventana.bind("<Motion>", lambda e: self._ocultar())

            x = px + 14
            y = py + 18
            ancho, alto = ventana.winfo_reqwidth(), ventana.winfo_reqheight()
            pantalla_w = self.widget.winfo_screenwidth()
            pantalla_h = self.widget.winfo_screenheight()

            if x + ancho > pantalla_w - 6:
                x = px - ancho - 8
            if y + alto > pantalla_h - 6:
                y = py - alto - 8
            x = max(6, x)
            y = max(6, y)

            ventana.wm_geometry(f"+{x}+{y}")
            self._ventana = ventana
        except Exception:
            self._ventana = None

    def _ocultar(self, event=None):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._ventana is not None:
            try:
                self._ventana.destroy()
            except Exception:
                pass
            self._ventana = None


def agregar_tooltip(widget, texto: str, **kwargs) -> ToolTip:
    """attach hover tooltip to widget"""
    return ToolTip(widget, texto, **kwargs)


def cargar_fuentes_windows():
    """load truetype fonts into memory on windows"""
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
    """enable dpi awareness on windows"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
