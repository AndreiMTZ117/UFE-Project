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
    BrutalOptionMenu, agregar_tooltip
)


class BarraSuperior(ctk.CTkFrame):
    """Barra superior con logo, selectores segmentados y botón de terminal."""

    def __init__(
        self,
        master,
        on_com_seleccionado: Optional[Callable[[str], None]] = None,
        on_dxf_seleccionado: Optional[Callable[[str], None]] = None,
        on_load_file_click: Optional[Callable[[], None]] = None,
        on_toggle_terminal: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", height=50, **kwargs)

        self.on_com_seleccionado = on_com_seleccionado
        self.on_dxf_seleccionado = on_dxf_seleccionado
        self.on_load_file_click = on_load_file_click
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

        # 2. Cápsula segmentada central (Puerto, DXF, Load File) con bordes rectos
        self.capsule_box = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=38
        )
        self.capsule_box.pack(side="left", padx=4)

        # Segmento 1: Puerto COM con indicador LED circular (Verde: Conectado / Rojo: Desconectado)
        self.com_frame = ctk.CTkFrame(self.capsule_box, fg_color="transparent")
        self.com_frame.pack(side="left", padx=(8, 2), pady=3)

        self.led_com = tk.Canvas(self.com_frame, width=16, height=16, bg=COLOR_CARD, highlightthickness=0)
        self.led_com.pack(side="left", padx=(4, 2))
        self._led_circle = self.led_com.create_oval(2, 2, 14, 14, fill=COLOR_RED, outline=COLOR_BORDER, width=1.5)

        self.opt_com = BrutalOptionMenu(
            self.com_frame,
            values=["Scanning ports..."],
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
            width=110,
            height=32
        )
        self.opt_com.pack(side="left", padx=(0, 4))

        # Separador vertical
        sep2 = ctk.CTkFrame(self.capsule_box, width=2, fg_color=COLOR_BORDER, height=20)
        sep2.pack(side="left", pady=4)

        # Segmento 2: Selector DXF (BrutalOptionMenu interactivo con auto-cierre)
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
            width=180,
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

        # Text helpers
        agregar_tooltip(self.com_frame, "Communication interface with Thorlabs GVS112/M hardware.\n"
                                        "Green LED = physical DAQ hardware active; Red LED = virtual simulation mode.\n"
                                        "'Scan...' refreshes hardware ports.")
        agregar_tooltip(self.opt_dxf, "Active DXF file to trace. Choose from cached list or select '[ Load File... ]' to open from explorer.")
        agregar_tooltip(self.btn_terminal, "Toggle floating diagnostic terminal and event log view.")

    # Métodos de callback internos
    def _cb_com(self, val: str):
        if getattr(self, "bloqueado_ejecucion", False):
            return
        if self.on_com_seleccionado:
            self.on_com_seleccionado(val)

    def _cb_dxf(self, val: str):
        if getattr(self, "bloqueado_ejecucion", False) or getattr(self, "bloqueado_carga", False):
            return
        if val == "[ Load File... ]":
            self._cb_load_file()
        elif self.on_dxf_seleccionado:
            self.on_dxf_seleccionado(val)

    def _cb_load_file(self):
        if getattr(self, "bloqueado_ejecucion", False) or getattr(self, "bloqueado_carga", False):
            return
        if self.on_load_file_click:
            self.on_load_file_click()
        elif self.on_dxf_seleccionado:
            self.on_dxf_seleccionado("[ Load File... ]")

    def _cb_toggle_terminal(self):
        if self.on_toggle_terminal:
            self.on_toggle_terminal()

    # Métodos públicos para actualización
    def set_bloqueo_carga(self, bloqueado: bool):
        """Bloquea o habilita temporalmente el menú DXF durante la carga asíncrona."""
        self.bloqueado_carga = bloqueado
        estado = "disabled" if (bloqueado or getattr(self, "bloqueado_ejecucion", False)) else "normal"
        self.opt_dxf.configure(state=estado)

    def set_bloqueo_ejecucion(self, bloqueado: bool):
        """Bloquea o habilita la selección de hardware y archivos durante la ejecución."""
        self.bloqueado_ejecucion = bloqueado
        estado = "disabled" if bloqueado else "normal"
        self.opt_com.configure(state=estado)
        self.opt_dxf.configure(state=estado)

    def set_estado_com(self, conectado_fisico: bool):
        """Pone el LED en Verde (#16A34A) si está conectado físicamente, o Rojo (#DC2626) si no."""
        color = COLOR_GREEN if conectado_fisico else COLOR_RED
        self.led_com.itemconfig(self._led_circle, fill=color)

    def set_puertos_com(self, puertos: List[str], seleccionado: Optional[str] = None):
        valores = puertos + ["Scan..."]
        self.opt_com.configure(values=valores)
        if seleccionado:
            self.opt_com.set(seleccionado)
        elif puertos:
            self.opt_com.set(puertos[0])

    def set_lista_dxf(self, nombres_dxf: List[str], seleccionado: Optional[str] = None):
        valores = nombres_dxf + ["[ Load File... ]"]
        self.opt_dxf.configure(values=valores)
        if seleccionado:
            self.opt_dxf.set(seleccionado)

    def set_terminal_activo(self, activo: bool):
        self.btn_terminal.configure(fg_color=COLOR_YELLOW if activo else COLOR_CARD)
