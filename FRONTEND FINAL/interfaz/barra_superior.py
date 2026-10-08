# -*- coding: utf-8 -*-
"""
interfaz/barra_superior.py — Barra Superior (Cyber-Brutalism)
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
    """Barra superior con logo, selectores segmentados y botón de terminal."""

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

        self.on_hal_cambiado = on_hal_cambiado
        self.on_com_seleccionado = on_com_seleccionado
        self.on_dxf_seleccionado = on_dxf_seleccionado
        self.on_toggle_terminal = on_toggle_terminal

        self.f_bold = ctk.CTkFont(family=FONT_TEACHERS, size=12, weight="bold")

        self._crear_widgets()

    def _crear_widgets(self):
        # 1. Logo "ŪFE" con barra amarilla exactamente sobre la U
        self.logo_box = ctk.CTkFrame(self, fg_color="transparent", width=96, height=44)
        self.logo_box.pack(side="left", padx=(2, 16))
        self.logo_box.pack_propagate(False)

        self.logo_canvas = tk.Canvas(self.logo_box, bg=COLOR_BG, highlightthickness=0, width=96, height=44)
        self.logo_canvas.pack(fill="both", expand=True)
        # Barra amarilla superior
        self.logo_canvas.create_rectangle(6, 6, 26, 11, fill=COLOR_YELLOW, outline="")
        # Tipografía UFE
        self.logo_canvas.create_text(8, 26, text="U", font=(FONT_TEACHERS, 18, "bold"), fill=COLOR_TEXT, anchor="w")
        self.logo_canvas.create_text(28, 26, text="FE", font=(FONT_TEACHERS, 18, "bold"), fill=COLOR_TEXT, anchor="w")

        # 2. Cápsula segmentada central (HAL, COM, DXF) con bordes rectos y borde grueso
        self.capsule_box = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=38
        )
        self.capsule_box.pack(side="left", padx=4)

        # Segmento 1: HAL (BrutalOptionMenu interactivo con auto-cierre)
        self.opt_hal = BrutalOptionMenu(
            self.capsule_box,
            values=["Maqueta Servos", "Thorlabs Galvo"],
            command=self._cb_hal,
            fg_color=COLOR_CARD,
            text_color=COLOR_TEXT,
            button_color=COLOR_CARD,
            button_hover_color="#F1F5F9",
            dropdown_fg_color=COLOR_CARD,
            dropdown_text_color=COLOR_TEXT,
            dropdown_hover_color=COLOR_YELLOW,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            width=140,
            height=32
        )
        self.opt_hal.pack(side="left", padx=(6, 2), pady=3)

        # Separador vertical 1
        sep1 = ctk.CTkFrame(self.capsule_box, width=2, fg_color=COLOR_BORDER, height=20)
        sep1.pack(side="left", pady=4)

        # Segmento 2: Puerto COM con indicador LED circular (Verde: Conectado / Rojo: Desconectado)
        self.com_frame = ctk.CTkFrame(self.capsule_box, fg_color="transparent")
        self.com_frame.pack(side="left", padx=(6, 2), pady=3)

        self.led_com = tk.Canvas(self.com_frame, width=16, height=16, bg=COLOR_CARD, highlightthickness=0)
        self.led_com.pack(side="left", padx=(4, 2))
        self._led_circle = self.led_com.create_oval(2, 2, 14, 14, fill=COLOR_RED, outline=COLOR_BORDER, width=1.5)

        self.opt_com = BrutalOptionMenu(
            self.com_frame,
            values=["Buscando puertos..."],
            command=self._cb_com,
            fg_color=COLOR_CARD,
            text_color=COLOR_TEXT,
            button_color=COLOR_CARD,
            button_hover_color="#F1F5F9",
            dropdown_fg_color=COLOR_CARD,
            dropdown_text_color=COLOR_TEXT,
            dropdown_hover_color=COLOR_YELLOW,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            width=100,
            height=32
        )
        self.opt_com.pack(side="left", padx=(0, 4))

        # Separador vertical 2
        sep2 = ctk.CTkFrame(self.capsule_box, width=2, fg_color=COLOR_BORDER, height=20)
        sep2.pack(side="left", pady=4)

        # Segmento 3: Selector DXF (BrutalOptionMenu interactivo con auto-cierre)
        self.opt_dxf = BrutalOptionMenu(
            self.capsule_box,
            values=["Cargando..."],
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
            width=165,
            height=32
        )
        self.opt_dxf.pack(side="left", padx=(4, 6), pady=3)

        # 3. Botón Terminal rectangular con borde grueso
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

    # Métodos de callback internos
    def _cb_hal(self, val: str):
        if self.on_hal_cambiado:
            self.on_hal_cambiado(val)

    def _cb_com(self, val: str):
        if self.on_com_seleccionado:
            self.on_com_seleccionado(val)

    def _cb_dxf(self, val: str):
        if self.on_dxf_seleccionado:
            self.on_dxf_seleccionado(val)

    def _cb_toggle_terminal(self):
        if self.on_toggle_terminal:
            self.on_toggle_terminal()

    # Métodos públicos para actualización
    def set_estado_com(self, conectado_fisico: bool):
        """Pone el LED en Verde intenso (#5DFF34) si está conectado físicamente, o Rojo (#FF3434) si no."""
        color = COLOR_GREEN if conectado_fisico else COLOR_RED
        self.led_com.itemconfig(self._led_circle, fill=color)

    def set_puertos_com(self, puertos: List[str], seleccionado: Optional[str] = None):
        valores = puertos + ["Escanear..."]
        self.opt_com.configure(values=valores)
        if seleccionado:
            self.opt_com.set(seleccionado)
        elif puertos:
            self.opt_com.set(puertos[0])

    def set_lista_dxf(self, nombres_dxf: List[str], seleccionado: Optional[str] = None):
        valores = nombres_dxf + ["[ Open Explorer... ]"]
        self.opt_dxf.configure(values=valores)
        if seleccionado:
            self.opt_dxf.set(seleccionado)

    def set_terminal_activo(self, activo: bool):
        self.btn_terminal.configure(fg_color=COLOR_YELLOW if activo else COLOR_CARD)
