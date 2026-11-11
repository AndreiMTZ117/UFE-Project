# -*- coding: utf-8 -*-
"""configuration panel and recipe manager for sqlite3"""

import customtkinter as ctk
from typing import Callable, Dict, List, Optional, Any, Tuple

from .constants import (
    COLOR_CARD, COLOR_BORDER, COLOR_TEXT,
    COLOR_YELLOW, COLOR_RED, COLOR_BLUE, COLOR_PAUSE,
    FONT_TEACHERS, BRUTAL_CORNER, BRUTAL_BORDER,
    BrutalOptionMenu, agregar_tooltip
)
from .i18n import tr, registrar_observador


#multi-tier physical limits: recommended range vs physical hard limit
_LIMITES_PARAMETROS = {
    "velocidad_trazado":        {"min": 0.01, "rec_max": 500.0,  "hard_max": 1200.0, "unit": "mm/s", "warn_key": "warn_velocidad_trazado"},
    "velocidad_viaje":          {"min": 0.01, "rec_max": 2000.0, "hard_max": 3000.0, "unit": "mm/s", "warn_key": "warn_velocidad_viaje"},
    "duracion_min_segmento_ms": {"min": 0,    "rec_max": 100,    "hard_max": 300,    "unit": "ms",   "warn_key": "warn_duracion_min_segmento_ms"},
    "duracion_min_viaje_ms":    {"min": 0,    "rec_max": 300,    "hard_max": 1000,   "unit": "ms",   "warn_key": "warn_duracion_min_viaje_ms"},
    "laser_on_delay_ms":        {"min": 0,    "rec_max": 100,    "hard_max": 300,    "unit": "ms",   "warn_key": "warn_laser_on_delay_ms"},
    "laser_off_delay_ms":       {"min": 0,    "rec_max": 100,    "hard_max": 300,    "unit": "ms",   "warn_key": "warn_laser_off_delay_ms"},
    "mark_delay_ms":            {"min": 0,    "rec_max": 50,     "hard_max": 150,    "unit": "ms",   "warn_key": "warn_mark_delay_ms"},
    "jump_delay_ms":            {"min": 0,    "rec_max": 200,    "hard_max": 500,    "unit": "ms",   "warn_key": "warn_jump_delay_ms"},
    "num_pasadas":              {"min": 1,    "rec_max": 15,     "hard_max": 40,     "unit": "passes","warn_key": "warn_num_pasadas"},
    "cooling_delay_s":          {"min": 0.0,  "rec_max": 15.0,   "hard_max": 45.0,   "unit": "s",    "warn_key": "warn_cooling_delay_s"},
    "tolerancia_rdp":           {"min": 0.0,  "rec_max": 0.02,   "hard_max": 0.10,   "unit": "mm",   "warn_key": "warn_tolerancia_rdp"},
    "tolerancia_union":         {"min": 0.0,  "rec_max": 0.20,   "hard_max": 1.0,    "unit": "mm",   "warn_key": "warn_tolerancia_union"},
    "escala_dibujo":            {"min": 0.01, "rec_max": 0.92,   "hard_max": 1.0,    "unit": "ratio","warn_key": "warn_escala_dibujo"},
    "rotacion_grados":          {"min": 0.0,  "rec_max": 360.0,  "hard_max": 360.0,  "unit": "°",    "warn_key": None},
}
_PAREJAS_COMBINADAS = {
    "velocidad_trazado": "duracion_min_segmento_ms",
    "duracion_min_segmento_ms": "velocidad_trazado",
    "velocidad_viaje": "jump_delay_ms",
    "jump_delay_ms": "velocidad_viaje",
}


class PanelConfiguracion(ctk.CTkFrame):
    """left side panel for sqlite3 recipe management and cutting parameters"""

    def __init__(
        self,
        master,
        on_receta_seleccionada: Optional[Callable[[str], None]] = None,
        on_crear_receta: Optional[Callable[[], None]] = None,
        on_guardar_receta: Optional[Callable[[], None]] = None,
        on_eliminar_receta: Optional[Callable[[], None]] = None,
        on_parametro_cambiado: Optional[Callable[[str, Any], None]] = None,
        on_click_frame: Optional[Callable[[], None]] = None,
        on_click_pause_resume: Optional[Callable[[], None]] = None,
        on_click_stop: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_receta_seleccionada = on_receta_seleccionada
        self.on_crear_receta = on_crear_receta
        self.on_guardar_receta = on_guardar_receta
        self.on_eliminar_receta = on_eliminar_receta
        self.on_parametro_cambiado = on_parametro_cambiado
        self.on_click_frame = on_click_frame
        self.on_click_pause_resume = on_click_pause_resume
        self.on_click_stop = on_click_stop

        self.f_head = ctk.CTkFont(family=FONT_TEACHERS, size=13, weight="bold")
        self.f_bold = ctk.CTkFont(family=FONT_TEACHERS, size=11, weight="bold")
        self.f_regular = ctk.CTkFont(family=FONT_TEACHERS, size=11)
        self.f_unit = ctk.CTkFont(family=FONT_TEACHERS, size=10, weight="bold")
        self.f_div = ctk.CTkFont(family=FONT_TEACHERS, size=10, weight="bold")

        self.inputs: Dict[str, ctk.CTkEntry] = {}
        self._tooltips: Dict[str, Any] = {}
        self._ayudas_base: Dict[str, str] = {}
        self._div_labels: Dict[str, ctk.CTkLabel] = {}
        self._entry_labels: Dict[str, Any] = {}
        self.bloqueado_ejecucion = False

        self._crear_widgets()
        registrar_observador(self.actualizar_idioma)

    #widget construction
    def _crear_widgets(self):
        #header container
        header_container = ctk.CTkFrame(self, fg_color="transparent")
        header_container.pack(side="top", fill="x", padx=6, pady=(2, 4))

        self.lbl_sec = ctk.CTkLabel(
            header_container,
            text=tr("recipe_parameters"),
            font=self.f_head,
            text_color=COLOR_TEXT,
            anchor="w"
        )
        self.lbl_sec.pack(fill="x", pady=(0, 2))

        header_frame = ctk.CTkFrame(header_container, fg_color="transparent")
        header_frame.pack(fill="x")

        self.receta_box = ctk.CTkFrame(
            header_frame,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=34
        )
        self.receta_box.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.receta_box.pack_propagate(False)

        self.opt_receta = BrutalOptionMenu(
            self.receta_box,
            values=["Acrylic — Standard"],
            command=self._cb_receta_seleccionada,
            fg_color=COLOR_CARD,
            text_color=COLOR_TEXT,
            button_color="#F1F5F9",
            button_hover_color=COLOR_YELLOW,
            dropdown_fg_color=COLOR_CARD,
            dropdown_text_color=COLOR_TEXT,
            dropdown_hover_color=COLOR_YELLOW,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            height=30
        )
        self.opt_receta.pack(fill="both", expand=True, padx=2, pady=2)
        agregar_tooltip(self.receta_box, tr("tooltip_recipe"))

        self.btn_del_receta = ctk.CTkButton(
            header_frame,
            text="🗑",
            command=self._cb_eliminar_receta,
            fg_color=COLOR_CARD,
            text_color=COLOR_RED,
            hover_color="#FEE2E2",
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            width=34,
            height=34,
            font=ctk.CTkFont(size=14)
        )
        self.btn_del_receta.pack(side="right")
        agregar_tooltip(self.btn_del_receta, tr("tooltip_btn_del"))

        #new and save buttons
        btn_box = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=38
        )
        btn_box.pack(side="bottom", fill="x", padx=6, pady=(4, 8))
        btn_box.pack_propagate(False)

        self.btn_new = ctk.CTkButton(
            btn_box,
            text=tr("btn_new_recipe"),
            command=self._cb_crear_receta,
            fg_color=COLOR_YELLOW,
            text_color=COLOR_TEXT,
            hover_color="#E09612",
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            height=30
        )
        self.btn_new.pack(side="left", fill="both", expand=True, padx=(3, 2), pady=3)
        agregar_tooltip(self.btn_new, tr("tooltip_btn_new"))

        self.btn_save = ctk.CTkButton(
            btn_box,
            text=tr("btn_save_recipe"),
            command=self._cb_guardar_receta,
            fg_color="#F1F5F9",
            text_color=COLOR_TEXT,
            hover_color="#E2E8F0",
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            height=30
        )
        self.btn_save.pack(side="right", fill="both", expand=True, padx=(2, 3), pady=3)
        agregar_tooltip(self.btn_save, tr("tooltip_btn_save"))

        #scrollable parameter form with 6 sections
        self.scroll_params = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_params.pack(side="top", fill="both", expand=True, padx=2, pady=2)
        self.scroll_params._parent_canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

        #a kinematics
        self._crear_divisor(self.scroll_params, "sec_kinematics", es_primero=True)
        self._crear_campo_entry(self.scroll_params, "velocidad_trazado", "mm/s", "2.0")
        self._crear_campo_entry(self.scroll_params, "velocidad_viaje", "mm/s", "3.5")
        self._crear_campo_entry(self.scroll_params, "duracion_min_segmento_ms", "ms", "50")
        self._crear_campo_entry(self.scroll_params, "duracion_min_viaje_ms", "ms", "300")

        #b optical delays
        self._crear_divisor(self.scroll_params, "sec_optical_delays")
        self._crear_campo_entry(self.scroll_params, "laser_on_delay_ms", "ms", "50")
        self._crear_campo_entry(self.scroll_params, "laser_off_delay_ms", "ms", "30")
        self._crear_campo_entry(self.scroll_params, "mark_delay_ms", "ms", "20")
        self._crear_campo_entry(self.scroll_params, "jump_delay_ms", "ms", "100")

        #c process and passes
        self._crear_divisor(self.scroll_params, "sec_process_passes")

        #process mode selector
        self.card_proc = ctk.CTkFrame(
            self.scroll_params,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=BRUTAL_CORNER
        )
        self.card_proc.pack(fill="x", padx=4, pady=2)

        top_proc = ctk.CTkFrame(self.card_proc, fg_color="transparent")
        top_proc.pack(fill="x", padx=6, pady=(3, 1))
        self.lbl_proc_title = ctk.CTkLabel(top_proc, text=tr("param_modo_proceso"), font=self.f_regular, text_color=COLOR_TEXT)
        self.lbl_proc_title.pack(side="left")
        ctk.CTkLabel(top_proc, text="[preset]", font=self.f_unit, text_color="#64748B").pack(side="right")

        self.opt_modo_proceso = BrutalOptionMenu(
            self.card_proc,
            values=[tr("mode_cutting"), tr("mode_welding"), tr("mode_marking")],
            command=self._cb_modo_proceso_cambiado,
            fg_color="#F8FAFC",
            text_color=COLOR_TEXT,
            button_color="#F1F5F9",
            button_hover_color=COLOR_YELLOW,
            dropdown_fg_color=COLOR_CARD,
            dropdown_text_color=COLOR_TEXT,
            dropdown_hover_color=COLOR_YELLOW,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            height=26
        )
        self.opt_modo_proceso.set(tr("mode_cutting"))
        self.opt_modo_proceso.pack(fill="x", padx=6, pady=(1, 4))
        agregar_tooltip(self.card_proc, tr("help_modo_proceso"))

        self._crear_campo_entry(self.scroll_params, "num_pasadas", "passes", "1")
        self._crear_campo_entry(self.scroll_params, "cooling_delay_s", "s", "0.0")

        #d cad geometry
        self._crear_divisor(self.scroll_params, "sec_cad_geometry")
        self._crear_campo_entry(self.scroll_params, "tolerancia_rdp", "mm", "0.005")
        self._crear_campo_entry(self.scroll_params, "tolerancia_union", "mm", "0.08")

        #e spatial and axes
        self._crear_divisor(self.scroll_params, "sec_spatial_axes")
        self._crear_campo_entry(self.scroll_params, "escala_dibujo", "ratio", "0.78")
        self._crear_campo_entry(self.scroll_params, "rotacion_grados", "°", "0")

        #checkbox row for axis transforms
        self.card_axes = ctk.CTkFrame(
            self.scroll_params,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=BRUTAL_CORNER
        )
        self.card_axes.pack(fill="x", padx=4, pady=2)

        top_axes = ctk.CTkFrame(self.card_axes, fg_color="transparent")
        top_axes.pack(fill="x", padx=6, pady=(3, 1))
        self.lbl_axes_title = ctk.CTkLabel(top_axes, text=tr("sec_spatial_axes"), font=self.f_regular, text_color=COLOR_TEXT)
        self.lbl_axes_title.pack(side="left")
        ctk.CTkLabel(top_axes, text="[flips]", font=self.f_unit, text_color="#64748B").pack(side="right")

        chk_row = ctk.CTkFrame(self.card_axes, fg_color="transparent")
        chk_row.pack(fill="x", padx=6, pady=(2, 4))

        self.var_invert_x = ctk.BooleanVar(value=False)
        self.chk_invert_x = ctk.CTkCheckBox(
            chk_row,
            text=tr("param_invert_x"),
            variable=self.var_invert_x,
            command=lambda: self._cb_checkbox_cambiado("invert_x", self.var_invert_x.get()),
            font=self.f_regular,
            text_color=COLOR_TEXT,
            fg_color=COLOR_BLUE,
            hover_color="#1D4ED8",
            border_color="#CBD5E1",
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            width=58,
            height=20,
            checkbox_width=16,
            checkbox_height=16
        )
        self.chk_invert_x.pack(side="left", expand=True)
        agregar_tooltip(self.chk_invert_x, tr("help_invert_x"))

        self.var_invert_y = ctk.BooleanVar(value=False)
        self.chk_invert_y = ctk.CTkCheckBox(
            chk_row,
            text=tr("param_invert_y"),
            variable=self.var_invert_y,
            command=lambda: self._cb_checkbox_cambiado("invert_y", self.var_invert_y.get()),
            font=self.f_regular,
            text_color=COLOR_TEXT,
            fg_color=COLOR_BLUE,
            hover_color="#1D4ED8",
            border_color="#CBD5E1",
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            width=58,
            height=20,
            checkbox_width=16,
            checkbox_height=16
        )
        self.chk_invert_y.pack(side="left", expand=True)
        agregar_tooltip(self.chk_invert_y, tr("help_invert_y"))

        self.var_swap_xy = ctk.BooleanVar(value=False)
        self.chk_swap_xy = ctk.CTkCheckBox(
            chk_row,
            text=tr("param_swap_xy"),
            variable=self.var_swap_xy,
            command=lambda: self._cb_checkbox_cambiado("swap_xy", self.var_swap_xy.get()),
            font=self.f_regular,
            text_color=COLOR_TEXT,
            fg_color=COLOR_BLUE,
            hover_color="#1D4ED8",
            border_color="#CBD5E1",
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            width=68,
            height=20,
            checkbox_width=16,
            checkbox_height=16
        )
        self.chk_swap_xy.pack(side="left", expand=True)
        agregar_tooltip(self.chk_swap_xy, tr("help_swap_xy"))

        #f alignment
        self._crear_divisor(self.scroll_params, "sec_alignment")
        card_align = ctk.CTkFrame(
            self.scroll_params,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=BRUTAL_CORNER
        )
        card_align.pack(fill="x", padx=4, pady=(2, 8))

        self.btn_frame = ctk.CTkButton(
            card_align,
            text=f"⛶ {tr('btn_trace_box')}",
            command=self._cb_click_frame,
            fg_color="#F1F5F9",
            text_color=COLOR_TEXT,
            hover_color="#E2E8F0",
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            height=32
        )
        self.btn_frame.pack(fill="x", padx=6, pady=4)
        agregar_tooltip(self.btn_frame, tr("tooltip_btn_frame"))

        #dynamic framing container with pause and stop
        self.frame_running_box = ctk.CTkFrame(card_align, fg_color="transparent")
        self.frame_running_box.grid_columnconfigure(0, weight=1, uniform="frame_btn")
        self.frame_running_box.grid_columnconfigure(1, weight=1, uniform="frame_btn")
        self.frame_running_box.grid_rowconfigure(0, weight=1)

        self.btn_frame_pause = ctk.CTkButton(
            self.frame_running_box,
            text=f"⏸ {tr('btn_pause')}",
            command=self._cb_frame_pause,
            fg_color=COLOR_PAUSE,
            text_color=COLOR_TEXT,
            hover_color="#CBD5E1",
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            width=0,
            height=32
        )
        self.btn_frame_pause.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        agregar_tooltip(self.btn_frame_pause, tr("btn_pause_tooltip"))

        self.btn_frame_stop = ctk.CTkButton(
            self.frame_running_box,
            text=f"⏹ {tr('btn_framing_stop')}",
            command=self._cb_frame_stop,
            fg_color=COLOR_RED,
            text_color="#FFFFFF",
            hover_color="#B91C1C",
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            width=0,
            height=32
        )
        self.btn_frame_stop.grid(row=0, column=1, sticky="nsew", padx=(3, 0))
        agregar_tooltip(self.btn_frame_stop, tr("btn_framing_stop"))

    def _on_mousewheel(self, event):
        # Sensibilidad de la rueda del mouse (píxeles por muesca)
        sensibilidad_px = 36
        if self.winfo_rootx() <= event.x_root <= self.winfo_rootx() + self.winfo_width() and \
           self.winfo_rooty() <= event.y_root <= self.winfo_rooty() + self.winfo_height():
            self.scroll_params._parent_canvas.yview("scroll", -int((event.delta / 120.0) * sensibilidad_px), "units")

    #widget creation helpers
    def _crear_divisor(self, parent, div_key: str, es_primero: bool = False):
        """insert horizontal cyber brutalist section divider"""
        top_pad = 2 if es_primero else 8
        div_frame = ctk.CTkFrame(parent, fg_color="transparent", height=16)
        div_frame.pack(fill="x", padx=6, pady=(top_pad, 2))
        div_frame.pack_propagate(False)

        lbl = ctk.CTkLabel(
            div_frame,
            text=tr(div_key).upper(),
            font=self.f_div,
            text_color="#64748B"
        )
        lbl.pack(side="left", padx=(0, 6))
        self._div_labels[div_key] = lbl

        line = ctk.CTkFrame(div_frame, fg_color="#CBD5E1", height=1)
        line.pack(side="left", fill="x", expand=True, pady=7)
        return div_frame

    def _crear_campo_entry(self, parent, key: str, unit: str, val_def: str):
        """create standard numerical entry card with i18n support"""
        p_card = ctk.CTkFrame(
            parent,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=BRUTAL_CORNER
        )
        p_card.pack(fill="x", padx=4, pady=2)

        top_row = ctk.CTkFrame(p_card, fg_color="transparent")
        top_row.pack(fill="x", padx=6, pady=(3, 1))

        lbl_name = ctk.CTkLabel(top_row, text=tr(f"param_{key}"), font=self.f_regular, text_color=COLOR_TEXT)
        lbl_name.pack(side="left")
        lbl_unit = ctk.CTkLabel(top_row, text=f"[{unit}]", font=self.f_unit, text_color="#64748B")
        lbl_unit.pack(side="right")
        self._entry_labels[key] = (lbl_name, lbl_unit, unit, p_card)

        entry = ctk.CTkEntry(
            p_card,
            height=24,
            fg_color="#F8FAFC",
            border_color="#CBD5E1",
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            text_color=COLOR_TEXT
        )
        entry.insert(0, val_def)
        entry.pack(fill="x", padx=6, pady=(1, 4))
        self.inputs[key] = entry

        ayuda = tr(f"help_{key}")
        cfg = _LIMITES_PARAMETROS.get(key)
        if cfg:
            ayuda += (
                f"\n{tr('label_range_recommended')}: {cfg['min']} - {cfg['rec_max']} {unit}"
                f" ({tr('label_max_operable')}: {cfg['hard_max']} {unit})."
            )
        self._ayudas_base[key] = ayuda
        self._tooltips[key] = agregar_tooltip(p_card, ayuda)

        #interactive visual validation
        entry.bind("<KeyRelease>", lambda e, k=key: self._validar_campo(k))
        entry.bind("<FocusOut>", lambda e, k=key: self._validar_campo(k))
        entry.bind("<Return>", lambda e, k=key: self._validar_campo(k))
        return p_card

    #parameter visual validation
    def _validar_campo(self, key: str, revalidar_pareja: bool = True, notificar: bool = True):
        """validate field value against physical limits and apply visual border states"""
        if getattr(self, "bloqueado_ejecucion", False):
            return
        if key not in self.inputs:
            return
        entry = self.inputs[key]
        val_txt = entry.get().strip()
        cfg = _LIMITES_PARAMETROS.get(key)

        if cfg:
            try:
                val = float(val_txt)
                if val < cfg["min"] or val > cfg["hard_max"]:
                    entry.configure(border_color=COLOR_RED, border_width=2)
                elif val > cfg["rec_max"]:
                    entry.configure(border_color=COLOR_YELLOW, border_width=2)
                    if notificar and self.on_parametro_cambiado:
                        self.on_parametro_cambiado(key, val)
                else:
                    entry.configure(border_color="#CBD5E1", border_width=1)
                    if notificar and self.on_parametro_cambiado:
                        self.on_parametro_cambiado(key, val)
            except ValueError:
                entry.configure(border_color=COLOR_RED, border_width=2)
        else:
            try:
                val = float(val_txt)
                entry.configure(border_color="#CBD5E1", border_width=1)
                if notificar and self.on_parametro_cambiado:
                    self.on_parametro_cambiado(key, val)
            except ValueError:
                entry.configure(border_color=COLOR_RED, border_width=2)

        if revalidar_pareja:
            pareja = _PAREJAS_COMBINADAS.get(key)
            if pareja:
                self._validar_campo(pareja, revalidar_pareja=False, notificar=False)
            self._verificar_combinaciones_parametros()

    #internal callbacks
    def _cb_receta_seleccionada(self, val: str):
        if getattr(self, "bloqueado_ejecucion", False):
            return
        if self.on_receta_seleccionada:
            self.on_receta_seleccionada(val)

    def _cb_crear_receta(self):
        if getattr(self, "bloqueado_ejecucion", False):
            return
        if self.on_crear_receta:
            self.on_crear_receta()

    def _cb_guardar_receta(self):
        if getattr(self, "bloqueado_ejecucion", False):
            return
        if self.on_guardar_receta:
            self.on_guardar_receta()

    def _cb_eliminar_receta(self):
        if getattr(self, "bloqueado_ejecucion", False):
            return
        if self.on_eliminar_receta:
            self.on_eliminar_receta()

    def _cb_modo_proceso_cambiado(self, val: str):
        """update process mode selected in form without overriding other parameters"""
        if getattr(self, "bloqueado_ejecucion", False):
            return
        if self.opt_modo_proceso.get() != val:
            self.opt_modo_proceso.set(val)

        if self.on_parametro_cambiado:
            self.on_parametro_cambiado("modo_proceso", val)

    def _cb_checkbox_cambiado(self, key: str, val: bool):
        if getattr(self, "bloqueado_ejecucion", False):
            return
        if self.on_parametro_cambiado:
            self.on_parametro_cambiado(key, val)

    def _cb_click_frame(self):
        if getattr(self, "bloqueado_ejecucion", False):
            return
        if self.on_click_frame:
            self.on_click_frame()

    def _cb_frame_pause(self):
        if self.on_click_pause_resume:
            self.on_click_pause_resume()

    def _cb_frame_stop(self):
        if self.on_click_stop:
            self.on_click_stop()

    def set_modo_framing(self, activo: bool):
        """toggle between framing button and pause stop buttons during framing"""
        if activo:
            self.btn_frame.pack_forget()
            self.frame_running_box.pack(fill="x", padx=6, pady=4)
            self.btn_frame_pause.configure(text=f"⏸ {tr('btn_pause')}", fg_color=COLOR_PAUSE)
        else:
            self.frame_running_box.pack_forget()
            self.btn_frame.pack(fill="x", padx=6, pady=4)

    def set_estado_pausa(self, pausado: bool):
        """update pause resume button text in config panel"""
        if pausado:
            self.btn_frame_pause.configure(text=f"▶ {tr('btn_resume')}", fg_color=COLOR_YELLOW)
        else:
            self.btn_frame_pause.configure(text=f"⏸ {tr('btn_pause')}", fg_color=COLOR_PAUSE)

    #control locking and data queries
    def set_bloqueo_ejecucion(self, bloqueado: bool):
        """lock or unlock controls during active execution"""
        self.bloqueado_ejecucion = bloqueado
        estado = "disabled" if bloqueado else "normal"
        self.opt_receta.configure(state=estado)
        self.btn_del_receta.configure(state=estado)
        self.btn_new.configure(state=estado)
        self.btn_save.configure(state=estado)
        self.opt_modo_proceso.configure(state=estado)
        self.chk_invert_x.configure(state=estado)
        self.chk_invert_y.configure(state=estado)
        self.chk_swap_xy.configure(state=estado)
        self.btn_frame.configure(state=estado)

        for entry in self.inputs.values():
            entry.configure(state=estado)

    def poblar_formulario(self, receta: Dict):
        """populate form inputs and controls with recipe values"""
        for key, entry in self.inputs.items():
            if key in receta:
                entry.delete(0, "end")
                entry.insert(0, str(receta[key]))
                self._validar_campo(key, revalidar_pareja=False, notificar=False)

        #process mode
        modo = receta.get("modo_proceso", "Cutting")
        modo_display = tr("mode_cutting")
        if modo in ("Welding", "Svařování"):
            modo_display = tr("mode_welding")
        elif modo in ("Marking", "Značení"):
            modo_display = tr("mode_marking")
        self.opt_modo_proceso.set(modo_display)

        #hardware check boxes
        self.var_invert_x.set(bool(receta.get("invert_x", 0)))
        self.var_invert_y.set(bool(receta.get("invert_y", 0)))
        self.var_swap_xy.set(bool(receta.get("swap_xy", 0)))

        #rotation angle fallback
        if "rotacion_grados" in self.inputs and "rotacion_grados" not in receta:
            if "rotar_90_grados" in receta and bool(receta["rotar_90_grados"]):
                ang_val = "90"
            else:
                ang_val = "0"
            self.inputs["rotacion_grados"].delete(0, "end")
            self.inputs["rotacion_grados"].insert(0, ang_val)
            self._validar_campo("rotacion_grados", revalidar_pareja=False, notificar=False)

        self._verificar_combinaciones_parametros()

    def obtener_datos_formulario(self) -> Dict:
        """read and cast form values to numerical and boolean types"""
        datos = {}
        for key, entry in self.inputs.items():
            val_txt = entry.get().strip()
            try:
                if "." in val_txt:
                    datos[key] = float(val_txt)
                else:
                    datos[key] = int(val_txt)
            except ValueError:
                datos[key] = val_txt

        #strict types and safe ranges
        if "num_pasadas" in datos:
            try:
                datos["num_pasadas"] = max(1, min(40, int(datos["num_pasadas"])))
            except (ValueError, TypeError):
                datos["num_pasadas"] = 1
        else:
            datos["num_pasadas"] = 1

        if "cooling_delay_s" in datos:
            try:
                datos["cooling_delay_s"] = max(0.0, min(45.0, float(datos["cooling_delay_s"])))
            except (ValueError, TypeError):
                datos["cooling_delay_s"] = 0.0
        else:
            datos["cooling_delay_s"] = 0.0

        if "tolerancia_rdp" in datos:
            try:
                datos["tolerancia_rdp"] = max(0.0, float(datos["tolerancia_rdp"]))
            except (ValueError, TypeError):
                datos["tolerancia_rdp"] = 0.0

        #canonical process mode in english for backend and db
        modo_raw = str(self.opt_modo_proceso.get())
        if modo_raw in ("Welding", "Svařování"):
            datos["modo_proceso"] = "Welding"
        elif modo_raw in ("Marking", "Značení"):
            datos["modo_proceso"] = "Marking"
        else:
            datos["modo_proceso"] = "Cutting"

        #hardware checkboxes
        datos["invert_x"] = bool(self.var_invert_x.get())
        datos["invert_y"] = bool(self.var_invert_y.get())
        datos["swap_xy"] = bool(self.var_swap_xy.get())

        #rotation in degrees
        if "rotacion_grados" in datos:
            try:
                datos["rotacion_grados"] = float(datos["rotacion_grados"])
            except (ValueError, TypeError):
                datos["rotacion_grados"] = 0.0
        else:
            datos["rotacion_grados"] = 0.0

        #backend compatibility rotar_90_grados flag
        datos["rotar_90_grados"] = 1 if datos["rotacion_grados"] == 90.0 else 0
        return datos

    def obtener_diagnostico_formulario(self):
        """inspect all inputs and return (tiene_errores, lista_errores, lista_advertencias)"""
        errores = []
        advertencias = []
        for key, cfg in _LIMITES_PARAMETROS.items():
            if key not in self.inputs:
                continue
            val_txt = self.inputs[key].get().strip()
            param_nombre = tr(f"param_{key}")
            try:
                val = float(val_txt)
                if val < cfg["min"] or val > cfg["hard_max"]:
                    self.inputs[key].configure(border_color=COLOR_RED, border_width=2)
                    errores.append(
                        f"Field to modify: [{param_nombre}]\n"
                        f"   Current value: {val} {cfg['unit']}\n"
                        f"   Allowed physical range: {cfg['min']} to {cfg['hard_max']} {cfg['unit']}"
                    )
                elif val > cfg["rec_max"]:
                    self.inputs[key].configure(border_color=COLOR_YELLOW, border_width=2)
                    warn_msg = tr(cfg["warn_key"]) if cfg.get("warn_key") else ""
                    advertencias.append({
                        "param": key,
                        "label": f"[{param_nombre}]",
                        "val": val,
                        "unit": cfg["unit"],
                        "rec_max": cfg["rec_max"],
                        "hard_max": cfg["hard_max"],
                        "warn_msg": warn_msg
                    })
                else:
                    self.inputs[key].configure(border_color="#CBD5E1", border_width=1)
            except ValueError:
                self.inputs[key].configure(border_color=COLOR_RED, border_width=2)
                errores.append(
                    f"Field to modify: [{param_nombre}]\n"
                    f"   Invalid non-numeric input: '{val_txt}'"
                )

        #check physical parameter combinations
        errs_comb, warns_comb = self._verificar_combinaciones_parametros()
        errores.extend(errs_comb)
        advertencias.extend(warns_comb)

        return (len(errores) > 0, errores, advertencias)

    def _verificar_combinaciones_parametros(self) -> Tuple[List[str], List[Dict]]:
        """evaluates safety rules on parameter combinations using simple straightforward conditions"""
        errores = []
        advertencias = []
        datos = self.obtener_datos_formulario()

        try:
            v_mark = float(datos.get("velocidad_trazado", 0))
            v_jump = float(datos.get("velocidad_viaje", 0))
            dur_min = float(datos.get("duracion_min_segmento_ms", 0))
            jump_delay = float(datos.get("jump_delay_ms", 0))
            cooling_delay = float(datos.get("cooling_delay_s", 0))
            num_passes = int(datos.get("num_pasadas", 1))
            rdp = float(datos.get("tolerancia_rdp", 0))
        except (ValueError, TypeError):
            return errores, advertencias

        #field labels from active language (english default)
        lbl_vmark = tr("param_velocidad_trazado")          # "Mark Speed"
        lbl_vjump = tr("param_velocidad_viaje")            # "Travel Speed"
        lbl_durmark = tr("param_duracion_min_segmento_ms") # "Min Mark Dwell"
        lbl_jdelay = tr("param_jump_delay_ms")             # "Jump Settling Delay"
        lbl_passes = tr("param_num_pasadas")               # "Passes"
        lbl_cooling = tr("param_cooling_delay_s")          # "Cooling Delay"
        lbl_rdp = tr("param_tolerancia_rdp")               # "RDP Tolerance"

        #1. High Mark Speed with zero or critical dwell
        if v_mark >= 600.0 and dur_min < 5.0:
            if "velocidad_trazado" in self.inputs:
                self.inputs["velocidad_trazado"].configure(border_color=COLOR_RED, border_width=2)
            if "duracion_min_segmento_ms" in self.inputs:
                self.inputs["duracion_min_segmento_ms"].configure(border_color=COLOR_RED, border_width=2)
            msg1 = f"⚠️ [CONFLICT]: Mark Speed ({v_mark:.0f} mm/s) requires [{lbl_durmark}] >= 5.0 ms (current: {dur_min:.1f} ms).\n\n"
            for k in ("velocidad_trazado", "duracion_min_segmento_ms"):
                if k in self._tooltips:
                    self._tooltips[k].texto = msg1 + self._ayudas_base.get(k, "")
            errores.append(
                f"Fields to modify: [{lbl_vmark}] or [{lbl_durmark}]\n"
                f"   Current: {lbl_vmark} = {v_mark:.0f} mm/s, {lbl_durmark} = {dur_min:.1f} ms.\n"
                f"   Requirement: Increase [{lbl_durmark}] to >= 5.0 ms (recommended: 15-25 ms) or decrease [{lbl_vmark}] below 600 mm/s to prevent violent 10 mm mirror chatter and driver trip."
            )
        else:
            for k in ("velocidad_trazado", "duracion_min_segmento_ms"):
                if k in self._tooltips:
                    self._tooltips[k].texto = self._ayudas_base.get(k, "")
        if v_mark > 300.0 and dur_min == 0.0 and v_mark < 600.0:
            advertencias.append({
                "param": "duracion_min_segmento_ms",
                "label": f"[{lbl_durmark}] with rapid [{lbl_vmark}]",
                "val": dur_min,
                "unit": "ms",
                "rec_max": 25.0,
                "hard_max": 100.0,
                "warn_msg": f"[{lbl_vmark}] is {v_mark:.0f} mm/s with [{lbl_durmark}] at 0 ms. Micro-vectors will cause corner rounding due to 10 mm mirror inertia. Set to >= 10 ms."
            })

        #2. Extreme Travel Speed with insufficient Jump Settling Delay
        #Note: Thorlabs GVS112 mirror settling time is 0.4 ms (small step) to 1.5-2.0 ms (full scale).
        if v_jump >= 2000.0 and jump_delay < 2.0:
            if "velocidad_viaje" in self.inputs:
                self.inputs["velocidad_viaje"].configure(border_color=COLOR_RED, border_width=2)
            if "jump_delay_ms" in self.inputs:
                self.inputs["jump_delay_ms"].configure(border_color=COLOR_RED, border_width=2)
            msg2 = f"⚠️ [CONFLICT]: Travel Speed ({v_jump:.0f} mm/s) requires [{lbl_jdelay}] >= 2.0 ms (current: {jump_delay:.1f} ms).\n\n"
            for k in ("velocidad_viaje", "jump_delay_ms"):
                if k in self._tooltips:
                    self._tooltips[k].texto = msg2 + self._ayudas_base.get(k, "")
            errores.append(
                f"Fields to modify: [{lbl_vjump}] or [{lbl_jdelay}]\n"
                f"   Current: {lbl_vjump} = {v_jump:.0f} mm/s, {lbl_jdelay} = {jump_delay:.1f} ms.\n"
                f"   Requirement: Increase [{lbl_jdelay}] to >= 2.0 ms (recommended: 10-50 ms) or decrease [{lbl_vjump}] below 2000 mm/s. The 10 mm mirrors require settling time before firing the laser."
            )
        else:
            for k in ("velocidad_viaje", "jump_delay_ms"):
                if k in self._tooltips:
                    self._tooltips[k].texto = self._ayudas_base.get(k, "")
        if v_jump > 1200.0 and jump_delay < 1.0 and v_jump < 2000.0:
            advertencias.append({
                "param": "jump_delay_ms",
                "label": f"[{lbl_jdelay}] with rapid [{lbl_vjump}]",
                "val": jump_delay,
                "unit": "ms",
                "rec_max": 200.0,
                "hard_max": 500.0,
                "warn_msg": f"Rapid jump ({v_jump:.0f} mm/s) with low settling delay ({jump_delay:.1f} ms). Risk of start hooks or tailing marks."
            })

        #3. Travel Speed slower than Mark Speed (Inversion)
        if v_jump < v_mark:
            advertencias.append({
                "param": "velocidad_viaje",
                "label": f"[{lbl_vjump}] vs [{lbl_vmark}]",
                "val": v_jump,
                "unit": "mm/s",
                "rec_max": 2000.0,
                "hard_max": 3000.0,
                "warn_msg": f"[{lbl_vjump}] ({v_jump:.0f} mm/s) is slower than [{lbl_vmark}] ({v_mark:.0f} mm/s). Unpowered rapid jumps will unnecessarily slow down total cycle time."
            })

        #4. Multi-Pass Cutting with zero Cooling Delay
        if num_passes >= 10 and cooling_delay == 0.0:
            advertencias.append({
                "param": "cooling_delay_s",
                "label": f"[{lbl_cooling}] with high [{lbl_passes}]",
                "val": cooling_delay,
                "unit": "s",
                "rec_max": 15.0,
                "hard_max": 45.0,
                "warn_msg": f"Continuous cutting with {num_passes} [{lbl_passes}] and 0s [{lbl_cooling}] accumulates heat in the Heat Affected Zone (HAZ), warping polymer edges."
            })

        #5. Excessive RDP Geometric Tolerance
        if rdp > 0.05:
            advertencias.append({
                "param": "tolerancia_rdp",
                "label": f"[{lbl_rdp}]",
                "val": rdp,
                "unit": "mm",
                "rec_max": 0.02,
                "hard_max": 0.10,
                "warn_msg": f"[{lbl_rdp}] at {rdp:.3f} mm is aggressive. Curves and fine details will be noticeably flattened."
            })

        return errores, advertencias

    def actualizar_idioma(self):
        """update all labels dividers buttons and tooltips on language change"""
        self.lbl_sec.configure(text=tr("recipe_parameters"))
        self.btn_new.configure(text=tr("btn_new_recipe"))
        self.btn_save.configure(text=tr("btn_save_recipe"))

        #update dividers
        for div_key, lbl in self._div_labels.items():
            lbl.configure(text=tr(div_key).upper())

        #update entry fields and tooltips
        for key, (lbl_name, lbl_unit, unit, p_card) in self._entry_labels.items():
            lbl_name.configure(text=tr(f"param_{key}"))
            ayuda = tr(f"help_{key}")
            cfg = _LIMITES_PARAMETROS.get(key)
            if cfg:
                ayuda += (
                    f"\n{tr('label_range_recommended')}: {cfg['min']} - {cfg['rec_max']} {unit}"
                    f" ({tr('label_max_operable')}: {cfg['hard_max']} {unit})."
                )
            self._ayudas_base[key] = ayuda
            if key in self._tooltips:
                self._tooltips[key].texto = ayuda
            else:
                self._tooltips[key] = agregar_tooltip(p_card, ayuda)

        #process mode
        self.lbl_proc_title.configure(text=tr("param_modo_proceso"))
        agregar_tooltip(self.card_proc, tr("help_modo_proceso"))

        modo_actual = self.opt_modo_proceso.get()
        canon = "Cutting"
        if modo_actual in ("Welding", "Svařování"):
            canon = "Welding"
        elif modo_actual in ("Marking", "Značení"):
            canon = "Marking"

        self.opt_modo_proceso.configure(values=[tr("mode_cutting"), tr("mode_welding"), tr("mode_marking")])
        if canon == "Welding":
            self.opt_modo_proceso.set(tr("mode_welding"))
        elif canon == "Marking":
            self.opt_modo_proceso.set(tr("mode_marking"))
        else:
            self.opt_modo_proceso.set(tr("mode_cutting"))

        #checkboxes and alignment
        self.lbl_axes_title.configure(text=tr("sec_spatial_axes"))
        self.chk_invert_x.configure(text=tr("param_invert_x"))
        agregar_tooltip(self.chk_invert_x, tr("help_invert_x"))
        self.chk_invert_y.configure(text=tr("param_invert_y"))
        agregar_tooltip(self.chk_invert_y, tr("help_invert_y"))
        self.chk_swap_xy.configure(text=tr("param_swap_xy"))
        agregar_tooltip(self.chk_swap_xy, tr("help_swap_xy"))

        self.btn_frame.configure(text=f"⛶ {tr('btn_trace_box')}")
        agregar_tooltip(self.btn_frame, tr("tooltip_btn_frame"))
        self.btn_frame_pause.configure(text=f"⏸ {tr('btn_pause')}")
        agregar_tooltip(self.btn_frame_pause, tr("btn_pause_tooltip"))
        self.btn_frame_stop.configure(text=f"⏹ {tr('btn_framing_stop')}")
        agregar_tooltip(self.btn_frame_stop, tr("btn_framing_stop"))

        agregar_tooltip(self.receta_box, tr("tooltip_recipe"))
        agregar_tooltip(self.btn_del_receta, tr("tooltip_btn_del"))
        agregar_tooltip(self.btn_new, tr("tooltip_btn_new"))
        agregar_tooltip(self.btn_save, tr("tooltip_btn_save"))

    def set_recetas(self, nombres: List[str], seleccionada: Optional[str] = None):
        """update recipe dropdown"""
        self.opt_receta.configure(values=nombres)
        if seleccionada:
            self.opt_receta.set(seleccionada)
        elif nombres:
            self.opt_receta.set(nombres[0])

    def set_delete_visible(self, visible: bool):
        """show or hide delete recipe button"""
        if visible:
            self.btn_del_receta.pack(side="right")
        else:
            self.btn_del_receta.pack_forget()

