# -*- coding: utf-8 -*-
"""
interfaz/barra_superior.py — Barra Superior (Cyber-Brutalism)

Indicador de estado del sistema Thorlabs GVS112/M en la barra superior.
Reemplaza el dropdown de selección de hardware por un badge de modo:
  · MODO: SIMULACIÓN  (fondo gris)
  · MODO: PXI-6229 REAL (fondo verde)
"""

import tkinter as tk
import customtkinter as ctk
from typing import Callable, List, Optional

from .constantes import (
    COLOR_BG, COLOR_CARD, COLOR_BORDER, COLOR_TEXT,
    COLOR_YELLOW, COLOR_GREEN, COLOR_RED,
    FONT_TEACHERS, BRUTAL_CORNER, BRUTAL_BORDER,
    BrutalOptionMenu
)


class BarraSuperior(ctk.CTkFrame):
    """Barra superior con logo, indicador de estado Thorlabs y selector de archivo."""

    def __init__(
        self,
        master,
        on_hal_cambiado: Optional[Callable[[str], None]] = None,
        on_com_seleccionado: Optional[Callable[[str], None]] = None,
        on_dxf_seleccionado: Optional[Callable[[str], None]] = None,
        on_toggle_terminal: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", height=50, **kwargs)

        # Callbacks públicos (mantenidos por compatibilidad con interfaz_app.py)
        self.on_hal_cambiado = on_hal_cambiado
        self.on_com_seleccionado = on_com_seleccionado
        self.on_dxf_seleccionado = on_dxf_seleccionado
        self.on_toggle_terminal = on_toggle_terminal

        self.f_bold = ctk.CTkFont(family=FONT_TEACHERS, size=12, weight="bold")
        self.f_badge = ctk.CTkFont(family=FONT_TEACHERS, size=11, weight="bold")

        self._crear_widgets()

    def _crear_widgets(self):
        # ── 1. Logo «ŪFE» ──────────────────────────────────────────────────────
        self.logo_box = ctk.CTkFrame(self, fg_color="transparent", width=96, height=44)
        self.logo_box.pack(side="left", padx=(2, 16))
        self.logo_box.pack_propagate(False)

        self.logo_canvas = tk.Canvas(self.logo_box, bg=COLOR_BG, highlightthickness=0, width=96, height=44)
        self.logo_canvas.pack(fill="both", expand=True)
        # Barra amarilla sobre la U
        self.logo_canvas.create_rectangle(6, 6, 26, 11, fill=COLOR_YELLOW, outline="")
        self.logo_canvas.create_text(8,  26, text="U",  font=(FONT_TEACHERS, 18, "bold"), fill=COLOR_TEXT, anchor="w")
        self.logo_canvas.create_text(28, 26, text="FE", font=(FONT_TEACHERS, 18, "bold"), fill=COLOR_TEXT, anchor="w")

        # ── 2. Cápsula central ─────────────────────────────────────────────────
        self.capsule_box = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=38
        )
        self.capsule_box.pack(side="left", padx=4)

        # ── 2a. Badge de estado del sistema Thorlabs ───────────────────────────
        self.estado_frame = ctk.CTkFrame(self.capsule_box, fg_color="transparent")
        self.estado_frame.pack(side="left", padx=(6, 4), pady=3)

        # LED de estado
        self.led_canvas = tk.Canvas(
            self.estado_frame, width=14, height=14,
            bg=COLOR_CARD, highlightthickness=0
        )
        self.led_canvas.pack(side="left", padx=(4, 4))
        self._led_circle = self.led_canvas.create_oval(
            2, 2, 12, 12, fill="#64748B", outline=COLOR_BORDER, width=1.5
        )

        # Etiqueta de modo
        self.lbl_modo = ctk.CTkLabel(
            self.estado_frame,
            text="MODE: SIMULATION",
            font=self.f_badge,
            text_color=COLOR_TEXT,
            width=190,
            anchor="w"
        )
        self.lbl_modo.pack(side="left")

        # Separador vertical
        sep1 = ctk.CTkFrame(self.capsule_box, width=2, fg_color=COLOR_BORDER, height=20)
        sep1.pack(side="left", pady=4)

        # ── 2b. Selector de archivo DXF / G-code ──────────────────────────────
        self.opt_dxf = BrutalOptionMenu(
            self.capsule_box,
            values=["Loading..."],
            command=self._cb_dxf,
            fg_color=COLOR_CARD,
            text_color=COLOR_TEXT,
            button_color=COLOR_CARD,
            button_hover_color="#F1F5F9",
            dropdown_fg_color=COLOR_CARD,
            dropdown_text_color=COLOR_TEXT,
            dropdown_hover_color=COLOR_YELLOW,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            width=200,
            height=32
        )
        self.opt_dxf.pack(side="left", padx=(4, 6), pady=3)

        # ── 3. Botón Terminal ──────────────────────────────────────────────────
        self.btn_terminal = ctk.CTkButton(
            self,
            text="Terminal",
            command=self._cb_toggle_terminal,
            fg_color=COLOR_CARD,
            text_color=COLOR_TEXT,
            hover_color=COLOR_YELLOW,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            width=110,
            height=38
        )
        self.btn_terminal.pack(side="right", padx=(8, 2))

    # ── Callbacks internos ─────────────────────────────────────────────────────
    def _cb_dxf(self, val: str):
        if self.on_dxf_seleccionado:
            self.on_dxf_seleccionado(val)

    def _cb_toggle_terminal(self):
        if self.on_toggle_terminal:
            self.on_toggle_terminal()

    # ── Métodos públicos ───────────────────────────────────────────────────────
    def set_modo_thorlabs(self, modo: str):
        """
        Actualiza el indicador de estado del sistema Thorlabs.

        Parámetros
        ----------
        modo : str
            'SIMULACION' → LED gris + etiqueta «MODE: SIMULATION»
            'REAL'       → LED verde + etiqueta «MODE: PXI-6229 REAL»
        """
        if modo.upper() == 'REAL':
            color_led   = COLOR_GREEN
            texto_modo  = "MODE: PXI-6229 REAL"
            color_texto = COLOR_GREEN
        else:
            color_led   = "#64748B"
            texto_modo  = "MODE: SIMULATION"
            color_texto = "#64748B"

        self.led_canvas.itemconfig(self._led_circle, fill=color_led)
        self.lbl_modo.configure(text=texto_modo, text_color=color_texto)

    # Alias: set_estado_com se mantiene para no romper código existente en interfaz_app
    def set_estado_com(self, conectado_fisico: bool):
        """Alias de compatibilidad → actualiza el indicador de modo según estado de conexión."""
        self.set_modo_thorlabs('REAL' if conectado_fisico else 'SIMULACION')

    # set_puertos_com se mantiene como stub para no romper interfaz_app.py
    def set_puertos_com(self, puertos: List[str], seleccionado: Optional[str] = None):
        """Stub de compatibilidad — no opera (puertos COM eliminados en Thorlabs)."""
        pass

    def set_lista_dxf(self, nombres_dxf: List[str], seleccionado: Optional[str] = None):
        """Actualiza el selector de archivos DXF / G-code."""
        valores = nombres_dxf + ["[ Open Explorer... ]"]
        self.opt_dxf.configure(values=valores)
        if seleccionado:
            self.opt_dxf.set(seleccionado)
        elif nombres_dxf:
            self.opt_dxf.set(nombres_dxf[0])

    def set_terminal_activo(self, activo: bool):
        self.btn_terminal.configure(fg_color=COLOR_YELLOW if activo else COLOR_CARD)
