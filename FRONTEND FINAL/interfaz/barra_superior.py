# -*- coding: utf-8 -*-
"""cyber brutalist top bar with logo device selectors and terminal toggle"""

import tkinter as tk
import customtkinter as ctk
from typing import Callable, List, Optional

from .constantes import (
    COLOR_BG, COLOR_CARD, COLOR_BORDER, COLOR_TEXT,
    COLOR_YELLOW, COLOR_GREEN, COLOR_RED,
    FONT_TEACHERS, BRUTAL_CORNER, BRUTAL_BORDER,
    BrutalOptionMenu, agregar_tooltip
)
from .i18n import (
    tr, cambiar_idioma, obtener_idioma,
    registrar_observador, IDIOMAS_DISPONIBLES
)


class BarraSuperior(ctk.CTkFrame):
    """top bar with logo segmented selectors and terminal toggle button"""

    def __init__(
        self,
        master,
        on_com_seleccionado: Optional[Callable[[str], None]] = None,
        on_dxf_seleccionado: Optional[Callable[[str], None]] = None,
        on_load_file_click: Optional[Callable[[], None]] = None,
        on_toggle_terminal: Optional[Callable[[], None]] = None,
        on_idioma_cambiado: Optional[Callable[[str], None]] = None,
        on_feedback_toggle: Optional[Callable[[bool], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", height=50, **kwargs)

        self.on_com_seleccionado = on_com_seleccionado
        self.on_dxf_seleccionado = on_dxf_seleccionado
        self.on_load_file_click = on_load_file_click
        self.on_toggle_terminal = on_toggle_terminal
        self.on_idioma_cambiado = on_idioma_cambiado
        self.on_feedback_toggle = on_feedback_toggle
        self._fb_disponible = False
        self._fb_clave = "checking"

        self._cached_puertos: List[str] = []
        self._cached_seleccionado_com: Optional[str] = None
        self._cached_nombres_dxf: List[str] = []
        self._cached_seleccionado_dxf: Optional[str] = None

        self.f_bold = ctk.CTkFont(family=FONT_TEACHERS, size=12, weight="bold")

        self._crear_widgets()
        registrar_observador(self.actualizar_idioma)

    def _crear_widgets(self):
        #logo box
        self.logo_box = ctk.CTkFrame(self, fg_color="transparent", width=96, height=44)
        self.logo_box.pack(side="left", padx=(2, 16))
        self.logo_box.pack_propagate(False)

        self.logo_canvas = tk.Canvas(self.logo_box, bg=COLOR_BG, highlightthickness=0, width=96, height=44)
        self.logo_canvas.pack(fill="both", expand=True)
        #top yellow bar
        self.logo_canvas.create_rectangle(6, 6, 26, 11, fill=COLOR_YELLOW, outline="")
        #logo text
        self.logo_canvas.create_text(8, 26, text="U", font=(FONT_TEACHERS, 18, "bold"), fill=COLOR_TEXT, anchor="w")
        self.logo_canvas.create_text(28, 26, text="FE", font=(FONT_TEACHERS, 18, "bold"), fill=COLOR_TEXT, anchor="w")

        #segmented central capsule
        self.capsule_box = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=38
        )
        self.capsule_box.pack(side="left", padx=4)

        #com port segment with led indicator
        self.com_frame = ctk.CTkFrame(self.capsule_box, fg_color="transparent")
        self.com_frame.pack(side="left", padx=(8, 2), pady=3)

        self.led_com = tk.Canvas(self.com_frame, width=16, height=16, bg=COLOR_CARD, highlightthickness=0)
        self.led_com.pack(side="left", padx=(4, 2))
        self._led_circle = self.led_com.create_oval(2, 2, 14, 14, fill=COLOR_RED, outline=COLOR_BORDER, width=1.5)

        self.opt_com = BrutalOptionMenu(
            self.com_frame,
            values=[tr("ports_scanning")],
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

        #separator 1
        sep1 = ctk.CTkFrame(self.capsule_box, width=2, fg_color=COLOR_BORDER, height=20)
        sep1.pack(side="left", pady=4)

        #dxf selector segment
        self.opt_dxf = BrutalOptionMenu(
            self.capsule_box,
            values=[tr("dxf_loading")],
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
        self.opt_dxf.pack(side="left", padx=(4, 4), pady=3)

        #separator 2
        sep2 = ctk.CTkFrame(self.capsule_box, width=2, fg_color=COLOR_BORDER, height=20)
        sep2.pack(side="left", pady=4)

        #language selector segment
        self.opt_lang = BrutalOptionMenu(
            self.capsule_box,
            values=IDIOMAS_DISPONIBLES,
            command=self._cb_lang,
            fg_color=COLOR_CARD,
            text_color=COLOR_TEXT,
            button_color=COLOR_CARD,
            button_hover_color="#F1F5F9",
            dropdown_fg_color=COLOR_CARD,
            dropdown_text_color=COLOR_TEXT,
            dropdown_hover_color=COLOR_YELLOW,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            width=65,
            height=32
        )
        self.opt_lang.set(obtener_idioma())
        self.opt_lang.pack(side="left", padx=(4, 6), pady=3)

        #separator 3
        sep3 = ctk.CTkFrame(self.capsule_box, width=2, fg_color=COLOR_BORDER, height=20)
        sep3.pack(side="left", pady=4)

        #hardware feedback tracking segment
        self.sw_feedback = ctk.CTkSwitch(
            self.capsule_box,
            text=tr("feedback_toggle"),
            command=self._cb_feedback,
            font=self.f_bold,
            text_color=COLOR_TEXT,
            progress_color="#D946EF",
            switch_width=34,
            switch_height=16
        )
        self.sw_feedback.pack(side="left", padx=(8, 10), pady=3)
        self.sw_feedback.configure(state="disabled")

        #terminal button
        self.btn_terminal = ctk.CTkButton(
            self,
            text=tr("btn_terminal"),
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

        #tooltips
        agregar_tooltip(self.com_frame, tr("tooltip_com"))
        agregar_tooltip(self.opt_dxf, tr("tooltip_dxf"))
        agregar_tooltip(self.opt_lang, tr("tooltip_lang"))
        agregar_tooltip(self.btn_terminal, tr("tooltip_terminal"))
        self._actualizar_tooltip_feedback()

    #internal callbacks
    def _cb_com(self, val: str):
        if getattr(self, "bloqueado_ejecucion", False):
            return
        if val in ("Scan...", "Skenovat...", tr("ports_scan")):
            val = "Scan..."
        if self.on_com_seleccionado:
            self.on_com_seleccionado(val)

    def _cb_dxf(self, val: str):
        if getattr(self, "bloqueado_ejecucion", False) or getattr(self, "bloqueado_carga", False):
            return
        if val in ("[ Load File... ]", "[ Načíst soubor... ]", tr("dxf_load_file")):
            self._cb_load_file()
        elif self.on_dxf_seleccionado:
            self.on_dxf_seleccionado(val)

    def _cb_lang(self, val: str):
        if getattr(self, "bloqueado_ejecucion", False):
            return
        cambiar_idioma(val)
        if self.on_idioma_cambiado:
            self.on_idioma_cambiado(val)

    def _cb_feedback(self):
        """toggle hardware feedback tracking"""
        if getattr(self, "bloqueado_ejecucion", False) or not self._fb_disponible:
            self.sw_feedback.deselect()
            return
        if self.on_feedback_toggle:
            self.on_feedback_toggle(bool(self.sw_feedback.get()))

    def _actualizar_tooltip_feedback(self):
        clave = {
            "ok": "tooltip_feedback_ok",
            "simulation": "tooltip_feedback_simulation",
            "no_driver": "tooltip_feedback_no_driver",
            "no_device": "tooltip_feedback_no_device",
        }.get(self._fb_clave, "tooltip_feedback_checking")
        agregar_tooltip(self.sw_feedback, tr(clave))

    def set_feedback_disponible(self, disponible: bool, clave: str = "ok"):
        """enable or disable feedback switch based on hardware availability"""
        self._fb_disponible = bool(disponible)
        self._fb_clave = clave if clave else ("ok" if disponible else "no_device")
        if not disponible:
            self.sw_feedback.deselect()
        bloqueado = getattr(self, "bloqueado_ejecucion", False)
        self.sw_feedback.configure(state="normal" if (disponible and not bloqueado) else "disabled")
        self._actualizar_tooltip_feedback()

    def forzar_feedback(self, activo: bool):
        """set visual feedback switch state"""
        if activo:
            self.sw_feedback.select()
        else:
            self.sw_feedback.deselect()

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

    def actualizar_idioma(self):
        """update texts tooltips and dropdown options on language change"""
        self.opt_lang.set(obtener_idioma())
        self.btn_terminal.configure(text=tr("btn_terminal"))

        #update dropdown texts keeping current selection
        if self._cached_puertos:
            self.set_puertos_com(self._cached_puertos, self._cached_seleccionado_com)
        elif self.opt_com.get() in ("Scanning ports...", "Skenování portů..."):
            self.opt_com.configure(values=[tr("ports_scanning")])
            self.opt_com.set(tr("ports_scanning"))

        if self._cached_nombres_dxf:
            self.set_lista_dxf(self._cached_nombres_dxf, self._cached_seleccionado_dxf)
        elif self.opt_dxf.get() in ("Loading...", "Načítání..."):
            self.opt_dxf.configure(values=[tr("dxf_loading")])
            self.opt_dxf.set(tr("dxf_loading"))

        agregar_tooltip(self.com_frame, tr("tooltip_com"))
        agregar_tooltip(self.opt_dxf, tr("tooltip_dxf"))
        agregar_tooltip(self.opt_lang, tr("tooltip_lang"))
        agregar_tooltip(self.btn_terminal, tr("tooltip_terminal"))
        self.sw_feedback.configure(text=tr("feedback_toggle"))
        self._actualizar_tooltip_feedback()

    #public update methods
    def set_bloqueo_carga(self, bloqueado: bool):
        """temporarily lock or unlock dxf dropdown during async loading"""
        self.bloqueado_carga = bloqueado
        estado = "disabled" if (bloqueado or getattr(self, "bloqueado_ejecucion", False)) else "normal"
        self.opt_dxf.configure(state=estado)

    def set_bloqueo_ejecucion(self, bloqueado: bool):
        """lock or unlock selectors during execution"""
        self.bloqueado_ejecucion = bloqueado
        estado = "disabled" if bloqueado else "normal"
        self.opt_com.configure(state=estado)
        self.opt_dxf.configure(state=estado)
        self.opt_lang.configure(state=estado)
        #feedback enabled only if ai hardware available and not executing
        self.sw_feedback.configure(state="normal" if (not bloqueado and self._fb_disponible) else "disabled")

    def set_estado_com(self, conectado_fisico: bool):
        """set led green if connected or red if disconnected"""
        color = COLOR_GREEN if conectado_fisico else COLOR_RED
        self.led_com.itemconfig(self._led_circle, fill=color)

    def set_puertos_com(self, puertos: List[str], seleccionado: Optional[str] = None):
        self._cached_puertos = list(puertos)
        self._cached_seleccionado_com = seleccionado
        valores = puertos + [tr("ports_scan")]
        self.opt_com.configure(values=valores)
        if seleccionado:
            self.opt_com.set(seleccionado)
        elif puertos:
            self.opt_com.set(puertos[0])

    def set_lista_dxf(self, nombres_dxf: List[str], seleccionado: Optional[str] = None):
        self._cached_nombres_dxf = list(nombres_dxf)
        self._cached_seleccionado_dxf = seleccionado
        valores = nombres_dxf + [tr("dxf_load_file")]
        self.opt_dxf.configure(values=valores)
        if seleccionado:
            self.opt_dxf.set(seleccionado)

    def set_terminal_activo(self, activo: bool):
        self.btn_terminal.configure(fg_color=COLOR_YELLOW if activo else COLOR_CARD)

