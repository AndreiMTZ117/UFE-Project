# -*- coding: utf-8 -*-
"""
interfaz/panel_configuracion.py — Panel Izquierdo: Configuración y Recetas (SQLite3)

Reorganización con scroll continuo vertical fluido y 6 divisores visuales:
  A) KINEMATICS
  B) OPTICAL DELAYS
  C) PROCESS & PASSES (Process Mode, Passes, Cooling Delay)
  D) CAD GEOMETRY (RDP tolerance, Join tolerance)
  E) SPATIAL & AXES (Drawing scale, Rotation, Inv X, Inv Y, Swap XY)
  F) ALIGNMENT (Frame Area / Trace Box)
"""

import customtkinter as ctk
from typing import Callable, Dict, List, Optional, Any

from .constantes import (
    COLOR_CARD, COLOR_BORDER, COLOR_TEXT,
    COLOR_YELLOW, COLOR_RED, COLOR_BLUE, COLOR_PAUSE,
    FONT_TEACHERS, BRUTAL_CORNER, BRUTAL_BORDER,
    BrutalOptionMenu, agregar_tooltip
)

# Textos de ayuda (tooltips) de cada parámetro editable
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

# Rangos de validación física para cada parámetro
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
    """Panel lateral izquierdo para gestión de recetas SQLite3 y parámetros de corte."""

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
        self.f_unit = ctk.CTkFont(family=FONT_TEACHERS, size=9, weight="bold")
        self.f_div = ctk.CTkFont(family=FONT_TEACHERS, size=9, weight="bold")

        self.inputs: Dict[str, ctk.CTkEntry] = {}
        self.bloqueado_ejecucion = False

        self._crear_widgets()

    # =========================================================================
    # CONSTRUCCIÓN DE WIDGETS
    # =========================================================================
    def _crear_widgets(self):
        # 1. Cabecera superior: Título + Selector de Receta + Botón Eliminar
        header_container = ctk.CTkFrame(self, fg_color="transparent")
        header_container.pack(side="top", fill="x", padx=6, pady=(2, 4))

        lbl_sec = ctk.CTkLabel(
            header_container,
            text="RECIPE & PARAMETERS",
            font=self.f_head,
            text_color=COLOR_TEXT,
            anchor="w"
        )
        lbl_sec.pack(fill="x", pady=(0, 2))

        header_frame = ctk.CTkFrame(header_container, fg_color="transparent")
        header_frame.pack(fill="x")

        receta_box = ctk.CTkFrame(
            header_frame,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=34
        )
        receta_box.pack(side="left", fill="x", expand=True, padx=(0, 4))
        receta_box.pack_propagate(False)

        self.opt_receta = BrutalOptionMenu(
            receta_box,
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
        agregar_tooltip(
            receta_box,
            "Active recipe: saved preset of cutting parameters (speeds, delays, tolerances).\n"
            "Selecting loads its values into the form."
        )

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
        agregar_tooltip(self.btn_del_receta, "Delete selected recipe (factory preset recipes are protected).")

        # 2. Botonera New / Save (Anclada al fondo con prioridad)
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
            text="+ New",
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
        agregar_tooltip(self.btn_new, "Create a new recipe preset with current form values.")

        self.btn_save = ctk.CTkButton(
            btn_box,
            text="💾 Save",
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
        agregar_tooltip(self.btn_save, "Save current form values to the selected recipe preset.")

        # 3. Formulario scrollable de parámetros con 6 divisores continuos
        self.scroll_params = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_params.pack(side="top", fill="both", expand=True, padx=2, pady=2)

        # -------------------------------------------------------------
        # A) KINEMATICS
        # -------------------------------------------------------------
        self._crear_divisor(self.scroll_params, "KINEMATICS", es_primero=True)
        self._crear_campo_entry(self.scroll_params, "Mark speed", "velocidad_trazado", "mm/s", "2.0")
        self._crear_campo_entry(self.scroll_params, "Travel speed", "velocidad_viaje", "mm/s", "3.5")
        self._crear_campo_entry(self.scroll_params, "Min. segment dur.", "duracion_min_segmento_ms", "ms", "50")
        self._crear_campo_entry(self.scroll_params, "Min. travel dur.", "duracion_min_viaje_ms", "ms", "300")

        # -------------------------------------------------------------
        # B) OPTICAL DELAYS
        # -------------------------------------------------------------
        self._crear_divisor(self.scroll_params, "OPTICAL DELAYS")
        self._crear_campo_entry(self.scroll_params, "Laser ON delay", "laser_on_delay_ms", "ms", "50")
        self._crear_campo_entry(self.scroll_params, "Laser OFF delay", "laser_off_delay_ms", "ms", "30")
        self._crear_campo_entry(self.scroll_params, "Mark delay", "mark_delay_ms", "ms", "20")
        self._crear_campo_entry(self.scroll_params, "Jump delay", "jump_delay_ms", "ms", "100")

        # -------------------------------------------------------------
        # C) PROCESS & PASSES
        # -------------------------------------------------------------
        self._crear_divisor(self.scroll_params, "PROCESS & PASSES")

        # Selector de Modo de Proceso
        card_proc = ctk.CTkFrame(
            self.scroll_params,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=BRUTAL_CORNER
        )
        card_proc.pack(fill="x", padx=4, pady=2)

        top_proc = ctk.CTkFrame(card_proc, fg_color="transparent")
        top_proc.pack(fill="x", padx=6, pady=(3, 1))
        ctk.CTkLabel(top_proc, text="Process mode", font=self.f_regular, text_color=COLOR_TEXT).pack(side="left")
        ctk.CTkLabel(top_proc, text="[preset]", font=self.f_unit, text_color="#64748B").pack(side="right")

        self.opt_modo_proceso = BrutalOptionMenu(
            card_proc,
            values=["Cutting", "Welding", "Marking"],
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
        self.opt_modo_proceso.set("Cutting")
        self.opt_modo_proceso.pack(fill="x", padx=6, pady=(1, 4))
        agregar_tooltip(card_proc, _AYUDAS["modo_proceso"])

        self._crear_campo_entry(self.scroll_params, "Number of passes", "num_pasadas", "passes", "1")
        self._crear_campo_entry(self.scroll_params, "Cooling delay", "cooling_delay_s", "s", "0.0")

        # -------------------------------------------------------------
        # D) CAD GEOMETRY
        # -------------------------------------------------------------
        self._crear_divisor(self.scroll_params, "CAD GEOMETRY")
        self._crear_campo_entry(self.scroll_params, "RDP tolerance", "tolerancia_rdp", "mm", "0.005")
        self._crear_campo_entry(self.scroll_params, "Join tolerance", "tolerancia_union", "mm", "0.08")

        # -------------------------------------------------------------
        # E) SPATIAL & AXES
        # -------------------------------------------------------------
        self._crear_divisor(self.scroll_params, "SPATIAL & AXES")
        self._crear_campo_entry(self.scroll_params, "Drawing scale", "escala_dibujo", "ratio", "0.78")
        self._crear_campo_entry(self.scroll_params, "Rotation", "rotacion_grados", "°", "0")

        # Fila horizontal compacta de CheckBoxes (Inv X, Inv Y, Swap XY)
        card_axes = ctk.CTkFrame(
            self.scroll_params,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=BRUTAL_CORNER
        )
        card_axes.pack(fill="x", padx=4, pady=2)

        top_axes = ctk.CTkFrame(card_axes, fg_color="transparent")
        top_axes.pack(fill="x", padx=6, pady=(3, 1))
        ctk.CTkLabel(top_axes, text="Axis transforms", font=self.f_regular, text_color=COLOR_TEXT).pack(side="left")
        ctk.CTkLabel(top_axes, text="[flips]", font=self.f_unit, text_color="#64748B").pack(side="right")

        chk_row = ctk.CTkFrame(card_axes, fg_color="transparent")
        chk_row.pack(fill="x", padx=6, pady=(2, 4))

        self.var_invert_x = ctk.BooleanVar(value=False)
        self.chk_invert_x = ctk.CTkCheckBox(
            chk_row,
            text="Inv X",
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
        agregar_tooltip(self.chk_invert_x, _AYUDAS["invert_x"])

        self.var_invert_y = ctk.BooleanVar(value=False)
        self.chk_invert_y = ctk.CTkCheckBox(
            chk_row,
            text="Inv Y",
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
        agregar_tooltip(self.chk_invert_y, _AYUDAS["invert_y"])

        self.var_swap_xy = ctk.BooleanVar(value=False)
        self.chk_swap_xy = ctk.CTkCheckBox(
            chk_row,
            text="Swap XY",
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
        agregar_tooltip(self.chk_swap_xy, _AYUDAS["swap_xy"])

        # -------------------------------------------------------------
        # F) ALIGNMENT (Frame Area / Trace Box)
        # -------------------------------------------------------------
        self._crear_divisor(self.scroll_params, "ALIGNMENT")
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
            text="⛶ Frame Area (Trace Box)",
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
        agregar_tooltip(
            self.btn_frame,
            "Trace the closed 4-corner bounding box perimeter with LASER STRICTLY OFF\n"
            "to check optical workpiece positioning and clearance."
        )

        # Contenedor dinámico durante enmarcado activo: Botones PAUSE y STOP (50% / 50% de ancho idéntico)
        self.frame_running_box = ctk.CTkFrame(card_align, fg_color="transparent")
        self.frame_running_box.grid_columnconfigure(0, weight=1, uniform="frame_btn")
        self.frame_running_box.grid_columnconfigure(1, weight=1, uniform="frame_btn")
        self.frame_running_box.grid_rowconfigure(0, weight=1)

        self.btn_frame_pause = ctk.CTkButton(
            self.frame_running_box,
            text="⏸ Pause",
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
        agregar_tooltip(self.btn_frame_pause, "Pause or resume the framing trace.")

        self.btn_frame_stop = ctk.CTkButton(
            self.frame_running_box,
            text="⏹ Stop",
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
        agregar_tooltip(self.btn_frame_stop, "Stop framing immediately and return head to Home center.")

    # =========================================================================
    # HELPERS DE CREACIÓN DE WIDGETS
    # =========================================================================
    def _crear_divisor(self, parent, texto_corto: str, es_primero: bool = False):
        """
        Inserta un divisor horizontal Cyber-Brutalist elegante con etiqueta
        en mayúsculas (#64748B) y línea divisoria tenue (#CBD5E1).
        """
        top_pad = 2 if es_primero else 8
        div_frame = ctk.CTkFrame(parent, fg_color="transparent", height=16)
        div_frame.pack(fill="x", padx=6, pady=(top_pad, 2))
        div_frame.pack_propagate(False)

        lbl = ctk.CTkLabel(
            div_frame,
            text=texto_corto.upper(),
            font=self.f_div,
            text_color="#64748B"
        )
        lbl.pack(side="left", padx=(0, 6))

        line = ctk.CTkFrame(div_frame, fg_color="#CBD5E1", height=1)
        line.pack(side="left", fill="x", expand=True, pady=7)
        return div_frame

    def _crear_campo_entry(self, parent, label_text: str, key: str, unit: str, val_def: str):
        """Crea una tarjeta de entrada numérica estándar Cyber-Brutalist."""
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

        ctk.CTkLabel(top_row, text=label_text, font=self.f_regular, text_color=COLOR_TEXT).pack(side="left")
        ctk.CTkLabel(top_row, text=f"[{unit}]", font=self.f_unit, text_color="#64748B").pack(side="right")

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

        ayuda = _AYUDAS.get(key, label_text)
        rango = _RANGOS_VALIDOS.get(key)
        if rango:
            ayuda += f"\nValid range: {rango[0]} to {rango[1]} {unit}."
        agregar_tooltip(p_card, ayuda)

        # Validación visual interactiva
        entry.bind("<FocusOut>", lambda e, k=key: self._validar_campo(k))
        entry.bind("<Return>", lambda e, k=key: self._validar_campo(k))
        return p_card

    # =========================================================================
    # VALIDACIÓN VISUAL DE PARÁMETROS
    # =========================================================================
    def _validar_campo(self, key: str):
        """Valida el valor del campo contra su rango y actualiza borde visual."""
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

    # =========================================================================
    # CALLBACKS INTERNOS
    # =========================================================================
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
        """Actualiza el modo de proceso seleccionado en el formulario sin sobreescribir otros parámetros."""
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
        """Alterna entre el botón de enmarcado y los botones PAUSE/STOP durante framing."""
        if activo:
            self.btn_frame.pack_forget()
            self.frame_running_box.pack(fill="x", padx=6, pady=4)
            self.btn_frame_pause.configure(text="⏸ Pause", fg_color=COLOR_PAUSE)
        else:
            self.frame_running_box.pack_forget()
            self.btn_frame.pack(fill="x", padx=6, pady=4)

    def set_estado_pausa(self, pausado: bool):
        """Actualiza el texto del botón Pause/Resume en el panel de configuración."""
        if hasattr(self, "btn_frame_pause"):
            if pausado:
                self.btn_frame_pause.configure(text="▶ Resume", fg_color=COLOR_YELLOW)
            else:
                self.btn_frame_pause.configure(text="⏸ Pause", fg_color=COLOR_PAUSE)

    # =========================================================================
    # BLOQUEO Y CONSULTA / MODIFICACIÓN DE DATOS
    # =========================================================================
    def set_bloqueo_ejecucion(self, bloqueado: bool):
        """Bloquea o habilita todos los controles durante la ejecución activa."""
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
        """Rellena los inputs y controles con los valores de la receta."""
        for key, entry in self.inputs.items():
            if key in receta:
                entry.delete(0, "end")
                entry.insert(0, str(receta[key]))
                entry.configure(border_color="#CBD5E1")

        # Modo de proceso
        if hasattr(self, "opt_modo_proceso"):
            modo = receta.get("modo_proceso", "Cutting")
            if modo in ("Cutting", "Welding", "Marking"):
                self.opt_modo_proceso.set(modo)
            else:
                self.opt_modo_proceso.set("Cutting")

        # Casillas de verificación de hardware
        if hasattr(self, "var_invert_x"):
            self.var_invert_x.set(bool(receta.get("invert_x", 0)))
        if hasattr(self, "var_invert_y"):
            self.var_invert_y.set(bool(receta.get("invert_y", 0)))
        if hasattr(self, "var_swap_xy"):
            self.var_swap_xy.set(bool(receta.get("swap_xy", 0)))

        # Compatibilidad para rotacion_grados si solo existía rotar_90_grados
        if "rotacion_grados" in self.inputs and "rotacion_grados" not in receta:
            if "rotar_90_grados" in receta and bool(receta["rotar_90_grados"]):
                ang_val = "90"
            else:
                ang_val = "0"
            self.inputs["rotacion_grados"].delete(0, "end")
            self.inputs["rotacion_grados"].insert(0, ang_val)
            self.inputs["rotacion_grados"].configure(border_color="#CBD5E1")

    def obtener_datos_formulario(self) -> Dict:
        """Lee y convierte los valores del formulario a tipos numéricos y booleanos."""
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

        # Tipos estrictos y rangos seguros
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

        # Modo de proceso
        if hasattr(self, "opt_modo_proceso"):
            datos["modo_proceso"] = str(self.opt_modo_proceso.get())
        else:
            datos["modo_proceso"] = "Cutting"

        # Checkboxes de hardware
        datos["invert_x"] = bool(self.var_invert_x.get()) if hasattr(self, "var_invert_x") else False
        datos["invert_y"] = bool(self.var_invert_y.get()) if hasattr(self, "var_invert_y") else False
        datos["swap_xy"] = bool(self.var_swap_xy.get()) if hasattr(self, "var_swap_xy") else False

        # Rotación libre en grados
        if "rotacion_grados" in datos:
            try:
                datos["rotacion_grados"] = float(datos["rotacion_grados"])
            except (ValueError, TypeError):
                datos["rotacion_grados"] = 0.0
        else:
            datos["rotacion_grados"] = 0.0

        # Compatibilidad con backend: rotar_90_grados flag
        datos["rotar_90_grados"] = 1 if datos["rotacion_grados"] == 90.0 else 0
        return datos

    def set_recetas(self, nombres: List[str], seleccionada: Optional[str] = None):
        """Actualiza el dropdown de recetas."""
        self.opt_receta.configure(values=nombres)
        if seleccionada:
            self.opt_receta.set(seleccionada)
        elif nombres:
            self.opt_receta.set(nombres[0])

    def set_delete_visible(self, visible: bool):
        """Muestra u oculta el botón de eliminar receta."""
        if visible:
            self.btn_del_receta.pack(side="right")
        else:
            self.btn_del_receta.pack_forget()
