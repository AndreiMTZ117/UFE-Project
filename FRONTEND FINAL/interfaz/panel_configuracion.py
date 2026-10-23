# -*- coding: utf-8 -*-
"""configuration panel and recipe manager for sqlite3"""

import customtkinter as ctk
from typing import Callable, Dict, List, Optional, Any

from .constantes import (
    COLOR_CARD, COLOR_BORDER, COLOR_TEXT,
    COLOR_YELLOW, COLOR_RED, COLOR_BLUE, COLOR_PAUSE,
    FONT_TEACHERS, BRUTAL_CORNER, BRUTAL_BORDER,
    BrutalOptionMenu, agregar_tooltip
)
from .i18n import tr, registrar_observador


#parameter help tooltips
_AYUDAS = {
    "velocidad_trazado": (
        "Beam speed while laser is ON (marking).\n"
        "Lower speed = higher energy per mm (deeper mark) and slower trajectory."),
    "velocidad_viaje": (
        "Rapid travel speed between paths with laser OFF.\n"
        "Higher value reduces cycle time but increases mirror stress."),
    "duracion_min_segmento_ms": (
        "Minimum duration for each marking segment.\n"
        "Very short segments are extended to this duration to avoid excessive mirror acceleration."),
    "duracion_min_viaje_ms": (
        "Minimum duration for rapid travels with laser OFF.\n"
        "Prevents abrupt galvanometer jumps between nearby paths."),
    "laser_on_delay_ms": (
        "Turn-on delay: elapsed time between mirror motion onset and optical emission.\n"
        "Compensates for galvanometer inertia."),
    "laser_off_delay_ms": (
        "Turn-off delay: duration laser remains active after completing a path,\n"
        "preventing unetched line ends."),
    "mark_delay_ms": (
        "Braking dwell time at the end of each marked path\n"
        "to allow mirrors to settle before moving."),
    "jump_delay_ms": (
        "Settling dwell after a rapid jump (laser off)\n"
        "before marking the next path."),
    "modo_proceso": (
        "Process operation mode: Cutting, Welding, or Marking.\n"
        "Stored as a first-class attribute within each recipe preset."),
    "num_pasadas": (
        "Number of repeated execution passes over the vector paths.\n"
        "Use multiple passes for cutting through thicker sheets."),
    "cooling_delay_s": (
        "Inter-pass thermal cooling dwell in seconds with LASER OFF.\n"
        "Allows heat dissipation between consecutive cutting passes."),
    "tolerancia_rdp": (
        "Ramer-Douglas-Peucker geometric simplification tolerance in mm.\n"
        "Set to 0.0 to disable simplification and preserve fine contours without deformation.\n"
        "Higher values reduce node count for smoother mirror motion."),
    "tolerancia_union": (
        "Maximum distance between path endpoints to merge them\n"
        "into a single continuous contour. Eliminates unnecessary jumps."),
    "escala_dibujo": (
        "Fraction of available area occupied by drawing (1.0 = 100%).\n"
        "Reduce to leave clearance around workpiece."),
    "rotacion_grados": (
        "Drawing rotation in degrees (0° to 360°).\n"
        "Rotates all trajectories around the geometric center."),
    "invert_x": (
        "Invert X: reflects horizontal coordinates across the center of workspace."),
    "invert_y": (
        "Invert Y: reflects vertical coordinates across the center of workspace."),
    "swap_xy": (
        "Swap XY: interchanges X and Y coordinates ((x, y) -> (y, x))."),
}

#physical validation ranges for parameters
_RANGOS_VALIDOS = {
    "velocidad_trazado":         (0.01, 50000.0),
    "velocidad_viaje":           (0.01, 50000.0),
    "duracion_min_segmento_ms":  (0, 10000),
    "duracion_min_viaje_ms":     (0, 10000),
    "laser_on_delay_ms":         (0, 10000),
    "laser_off_delay_ms":        (0, 10000),
    "mark_delay_ms":             (0, 10000),
    "jump_delay_ms":             (0, 10000),
    "num_pasadas":               (1, 50),
    "cooling_delay_s":           (0.0, 30.0),
    "tolerancia_rdp":            (0.0, 10.0),
    "tolerancia_union":          (0.0, 10.0),
    "escala_dibujo":             (0.01, 1.0),
    "rotacion_grados":           (0.0, 360.0),
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
        on_rotacion_cambiada: Optional[Callable[[float], None]] = None,
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
        self.on_rotacion_cambiada = on_rotacion_cambiada
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
        agregar_tooltip(self.btn_frame_pause, tr("btn_pause"))

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
        rango = _RANGOS_VALIDOS.get(key)
        if rango:
            ayuda += f"\nRange: {rango[0]} to {rango[1]} {unit}."
        agregar_tooltip(p_card, ayuda)

        #interactive visual validation
        entry.bind("<FocusOut>", lambda e, k=key: self._validar_campo(k))
        entry.bind("<Return>", lambda e, k=key: self._validar_campo(k))
        return p_card

    #parameter visual validation
    def _validar_campo(self, key: str):
        """validate field value against range and update border color"""
        if getattr(self, "bloqueado_ejecucion", False):
            return
        if key not in self.inputs:
            return
        entry = self.inputs[key]
        val_txt = entry.get().strip()
        rango = _RANGOS_VALIDOS.get(key)

        if rango:
            try:
                val = float(val_txt)
                if rango[0] <= val <= rango[1]:
                    entry.configure(border_color="#CBD5E1")
                    if self.on_parametro_cambiado:
                        self.on_parametro_cambiado(key, val)
                    if key == "rotacion_grados" and self.on_rotacion_cambiada:
                        self.on_rotacion_cambiada(val)
                else:
                    entry.configure(border_color=COLOR_RED)
            except ValueError:
                entry.configure(border_color=COLOR_RED)
        else:
            try:
                val = float(val_txt)
                entry.configure(border_color="#CBD5E1")
                if self.on_parametro_cambiado:
                    self.on_parametro_cambiado(key, val)
                if key == "rotacion_grados" and self.on_rotacion_cambiada:
                    self.on_rotacion_cambiada(val)
            except ValueError:
                entry.configure(border_color=COLOR_RED)

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
        if hasattr(self, "opt_modo_proceso") and self.opt_modo_proceso.get() != val:
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
        if hasattr(self, "btn_frame_pause"):
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
        if hasattr(self, "btn_del_receta"):
            self.btn_del_receta.configure(state=estado)
        self.btn_new.configure(state=estado)
        self.btn_save.configure(state=estado)

        if hasattr(self, "opt_modo_proceso"):
            self.opt_modo_proceso.configure(state=estado)
        if hasattr(self, "chk_invert_x"):
            self.chk_invert_x.configure(state=estado)
        if hasattr(self, "chk_invert_y"):
            self.chk_invert_y.configure(state=estado)
        if hasattr(self, "chk_swap_xy"):
            self.chk_swap_xy.configure(state=estado)
        if hasattr(self, "btn_frame"):
            self.btn_frame.configure(state=estado)

        for entry in self.inputs.values():
            entry.configure(state=estado)

    def poblar_formulario(self, receta: Dict):
        """populate form inputs and controls with recipe values"""
        for key, entry in self.inputs.items():
            if key in receta:
                entry.delete(0, "end")
                entry.insert(0, str(receta[key]))
                entry.configure(border_color="#CBD5E1")

        #process mode
        if hasattr(self, "opt_modo_proceso"):
            modo = receta.get("modo_proceso", "Cutting")
            modo_display = tr("mode_cutting")
            if modo in ("Welding", "Svařování"):
                modo_display = tr("mode_welding")
            elif modo in ("Marking", "Značení"):
                modo_display = tr("mode_marking")
            self.opt_modo_proceso.set(modo_display)

        #hardware check boxes
        if hasattr(self, "var_invert_x"):
            self.var_invert_x.set(bool(receta.get("invert_x", 0)))
        if hasattr(self, "var_invert_y"):
            self.var_invert_y.set(bool(receta.get("invert_y", 0)))
        if hasattr(self, "var_swap_xy"):
            self.var_swap_xy.set(bool(receta.get("swap_xy", 0)))

        #rotation angle fallback
        if "rotacion_grados" in self.inputs and "rotacion_grados" not in receta:
            if "rotar_90_grados" in receta and bool(receta["rotar_90_grados"]):
                ang_val = "90"
            else:
                ang_val = "0"
            self.inputs["rotacion_grados"].delete(0, "end")
            self.inputs["rotacion_grados"].insert(0, ang_val)
            self.inputs["rotacion_grados"].configure(border_color="#CBD5E1")

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
                datos["num_pasadas"] = max(1, min(50, int(datos["num_pasadas"])))
            except (ValueError, TypeError):
                datos["num_pasadas"] = 1
        else:
            datos["num_pasadas"] = 1

        if "cooling_delay_s" in datos:
            try:
                datos["cooling_delay_s"] = max(0.0, min(30.0, float(datos["cooling_delay_s"])))
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
        if hasattr(self, "opt_modo_proceso"):
            modo_raw = str(self.opt_modo_proceso.get())
            if modo_raw in ("Welding", "Svařování"):
                datos["modo_proceso"] = "Welding"
            elif modo_raw in ("Marking", "Značení"):
                datos["modo_proceso"] = "Marking"
            else:
                datos["modo_proceso"] = "Cutting"
        else:
            datos["modo_proceso"] = "Cutting"

        #hardware checkboxes
        datos["invert_x"] = bool(self.var_invert_x.get()) if hasattr(self, "var_invert_x") else False
        datos["invert_y"] = bool(self.var_invert_y.get()) if hasattr(self, "var_invert_y") else False
        datos["swap_xy"] = bool(self.var_swap_xy.get()) if hasattr(self, "var_swap_xy") else False

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

    def actualizar_idioma(self):
        """update all labels dividers buttons and tooltips on language change"""
        if hasattr(self, "lbl_sec"):
            self.lbl_sec.configure(text=tr("recipe_parameters"))
        if hasattr(self, "btn_new"):
            self.btn_new.configure(text=tr("btn_new_recipe"))
        if hasattr(self, "btn_save"):
            self.btn_save.configure(text=tr("btn_save_recipe"))

        #update dividers
        for div_key, lbl in self._div_labels.items():
            lbl.configure(text=tr(div_key).upper())

        #update entry fields and tooltips
        for key, (lbl_name, lbl_unit, unit, p_card) in self._entry_labels.items():
            lbl_name.configure(text=tr(f"param_{key}"))
            ayuda = tr(f"help_{key}")
            rango = _RANGOS_VALIDOS.get(key)
            if rango:
                ayuda += f"\nRange: {rango[0]} to {rango[1]} {unit}."
            agregar_tooltip(p_card, ayuda)

        #process mode
        if hasattr(self, "lbl_proc_title"):
            self.lbl_proc_title.configure(text=tr("param_modo_proceso"))
        if hasattr(self, "card_proc"):
            agregar_tooltip(self.card_proc, tr("help_modo_proceso"))

        if hasattr(self, "opt_modo_proceso"):
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
        if hasattr(self, "lbl_axes_title"):
            self.lbl_axes_title.configure(text=tr("sec_spatial_axes"))
        if hasattr(self, "chk_invert_x"):
            self.chk_invert_x.configure(text=tr("param_invert_x"))
            agregar_tooltip(self.chk_invert_x, tr("help_invert_x"))
        if hasattr(self, "chk_invert_y"):
            self.chk_invert_y.configure(text=tr("param_invert_y"))
            agregar_tooltip(self.chk_invert_y, tr("help_invert_y"))
        if hasattr(self, "chk_swap_xy"):
            self.chk_swap_xy.configure(text=tr("param_swap_xy"))
            agregar_tooltip(self.chk_swap_xy, tr("help_swap_xy"))

        if hasattr(self, "btn_frame"):
            self.btn_frame.configure(text=f"⛶ {tr('btn_trace_box')}")
            agregar_tooltip(self.btn_frame, tr("tooltip_btn_frame"))
        if hasattr(self, "btn_frame_pause"):
            self.btn_frame_pause.configure(text=f"⏸ {tr('btn_pause')}")
            agregar_tooltip(self.btn_frame_pause, tr("btn_pause"))
        if hasattr(self, "btn_frame_stop"):
            self.btn_frame_stop.configure(text=f"⏹ {tr('btn_framing_stop')}")
            agregar_tooltip(self.btn_frame_stop, tr("btn_framing_stop"))

        if hasattr(self, "receta_box"):
            agregar_tooltip(self.receta_box, tr("tooltip_recipe"))
        if hasattr(self, "btn_del_receta"):
            agregar_tooltip(self.btn_del_receta, tr("tooltip_btn_del"))
        if hasattr(self, "btn_new"):
            agregar_tooltip(self.btn_new, tr("tooltip_btn_new"))
        if hasattr(self, "btn_save"):
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

