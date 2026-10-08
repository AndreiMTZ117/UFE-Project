# -*- coding: utf-8 -*-
"""
interfaz/panel_configuracion.py — Panel Izquierdo: Configuración y Recetas (SQLite3)
"""

import customtkinter as ctk
from typing import Callable, Dict, List, Optional

from .constantes import (
    COLOR_CARD, COLOR_BORDER, COLOR_TEXT,
    COLOR_YELLOW, COLOR_RED, COLOR_BLUE,
    FONT_TEACHERS, BRUTAL_CORNER, BRUTAL_BORDER,
    BrutalOptionMenu
)

# Rangos de validación física para cada parámetro
_RANGOS_VALIDOS = {
    "velocidad_trazado":         (0.01, 100.0),
    "velocidad_viaje":           (0.01, 100.0),
    "duracion_min_segmento_ms":  (10, 5000),
    "duracion_min_viaje_ms":     (50, 10000),
    "laser_on_delay_ms":         (0, 10000),
    "laser_off_delay_ms":        (0, 10000),
    "mark_delay_ms":             (0, 10000),
    "jump_delay_ms":             (0, 10000),
    "tolerancia_rdp":            (0.0, 10.0),
    "tolerancia_union":          (0.0, 10.0),
    "escala_dibujo":             (0.01, 1.0),
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
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_receta_seleccionada = on_receta_seleccionada
        self.on_crear_receta = on_crear_receta
        self.on_guardar_receta = on_guardar_receta
        self.on_eliminar_receta = on_eliminar_receta
        self.on_rotacion_cambiada = on_rotacion_cambiada

        self.f_head = ctk.CTkFont(family=FONT_TEACHERS, size=13, weight="bold")
        self.f_bold = ctk.CTkFont(family=FONT_TEACHERS, size=11, weight="bold")
        self.f_regular = ctk.CTkFont(family=FONT_TEACHERS, size=11)
        self.f_unit = ctk.CTkFont(family=FONT_TEACHERS, size=9, weight="bold")

        self.inputs: Dict[str, ctk.CTkEntry] = {}

        self._crear_widgets()

    def _crear_widgets(self):
        # 1. Cabecera superior: Título + Selector de Receta + Botón Eliminar
        header_container = ctk.CTkFrame(self, fg_color="transparent")
        header_container.pack(side="top", fill="x", padx=6, pady=(2, 4))

        lbl_sec = ctk.CTkLabel(header_container, text="RECETA & PARÁMETROS", font=self.f_head, text_color=COLOR_TEXT, anchor="w")
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
            values=["Acrílico — Estándar"],
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
            hover_color="#FFA000",
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            height=30
        )
        self.btn_new.pack(side="left", fill="both", expand=True, padx=(3, 1), pady=3)

        self.btn_save = ctk.CTkButton(
            btn_box,
            text="💾 Save",
            command=self._cb_guardar_receta,
            fg_color="#F1F5F9",
            text_color=COLOR_TEXT,
            hover_color="#E2E8F0",
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            height=30
        )
        self.btn_save.pack(side="right", fill="both", expand=True, padx=(1, 3), pady=3)

        # 3. Formulario scrollable de parámetros
        self.scroll_params = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_params.pack(side="top", fill="both", expand=True, padx=2, pady=2)

        campos = [
            ("Velocidad trazado", "velocidad_trazado", "mm/s", "2.0"),
            ("Velocidad viaje", "velocidad_viaje", "mm/s", "3.5"),
            ("Duración mín. seg", "duracion_min_segmento_ms", "ms", "50"),
            ("Duración mín. viaje", "duracion_min_viaje_ms", "ms", "300"),
            ("Laser ON delay", "laser_on_delay_ms", "ms", "50"),
            ("Laser OFF delay", "laser_off_delay_ms", "ms", "30"),
            ("Mark delay", "mark_delay_ms", "ms", "20"),
            ("Jump delay", "jump_delay_ms", "ms", "100"),
            ("Tolerancia RDP", "tolerancia_rdp", "mm", "0.005"),
            ("Tolerancia unión", "tolerancia_union", "mm", "0.08"),
            ("Escala dibujo", "escala_dibujo", "ratio", "0.78"),
        ]

        for label_text, key, unit, val_def in campos:
            p_card = ctk.CTkFrame(
                self.scroll_params,
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

            # Validación visual al perder el foco o Enter
            entry.bind("<FocusOut>", lambda e, k=key: self._validar_campo(k))
            entry.bind("<Return>", lambda e, k=key: self._validar_campo(k))

        # Slider de Rotación — Continuo de 0° a 360° con Entry editable
        card_rot = ctk.CTkFrame(
            self.scroll_params,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=BRUTAL_CORNER
        )
        card_rot.pack(fill="x", padx=4, pady=(2, 6))

        top_rot = ctk.CTkFrame(card_rot, fg_color="transparent")
        top_rot.pack(fill="x", padx=6, pady=(3, 1))
        ctk.CTkLabel(top_rot, text="Rotación", font=self.f_regular, text_color=COLOR_TEXT).pack(side="left")

        # Entry editable para ángulo exacto
        self.entry_rot = ctk.CTkEntry(
            top_rot,
            width=50,
            height=22,
            fg_color="#F8FAFC",
            border_color="#CBD5E1",
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            text_color=COLOR_BLUE
        )
        self.entry_rot.insert(0, "0")
        self.entry_rot.pack(side="right", padx=(4, 0))
        self.entry_rot.bind("<Return>", self._cb_entry_rotacion)
        self.entry_rot.bind("<FocusOut>", self._cb_entry_rotacion)

        ctk.CTkLabel(top_rot, text="°", font=self.f_unit, text_color=COLOR_BLUE).pack(side="right")

        self.slider_rot = ctk.CTkSlider(
            card_rot,
            from_=0,
            to=360,
            number_of_steps=360,
            command=self._cb_slider_rotacion,
            progress_color=COLOR_BLUE,
            button_color=COLOR_BORDER,
            button_hover_color=COLOR_BLUE,
            height=14
        )
        self.slider_rot.set(0)
        self.slider_rot.pack(fill="x", padx=6, pady=(2, 6))

    # Validación visual de parámetros
    def _validar_campo(self, key: str):
        """Valida el valor del campo contra su rango válido y pinta borde rojo si falla."""
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
                else:
                    entry.configure(border_color=COLOR_RED)
            except ValueError:
                entry.configure(border_color=COLOR_RED)
        else:
            # Sin rango definido, solo verificar que sea numérico
            try:
                float(val_txt)
                entry.configure(border_color="#CBD5E1")
            except ValueError:
                entry.configure(border_color=COLOR_RED)

    # Callbacks internos
    def _cb_receta_seleccionada(self, val: str):
        if self.on_receta_seleccionada:
            self.on_receta_seleccionada(val)

    def _cb_crear_receta(self):
        if self.on_crear_receta:
            self.on_crear_receta()

    def _cb_guardar_receta(self):
        if self.on_guardar_receta:
            self.on_guardar_receta()

    def _cb_eliminar_receta(self):
        if self.on_eliminar_receta:
            self.on_eliminar_receta()

    def _cb_slider_rotacion(self, val: float):
        """Cuando se mueve el slider, actualizar el entry y notificar."""
        angulo = int(round(val))
        self.entry_rot.delete(0, "end")
        self.entry_rot.insert(0, str(angulo))
        if self.on_rotacion_cambiada:
            self.on_rotacion_cambiada(float(angulo))

    def _cb_entry_rotacion(self, event=None):
        """Cuando se edita el entry de rotación, actualizar el slider y notificar."""
        try:
            angulo = float(self.entry_rot.get().strip())
            angulo = max(0, min(360, angulo))
            self.slider_rot.set(angulo)
            if self.on_rotacion_cambiada:
                self.on_rotacion_cambiada(angulo)
        except ValueError:
            pass

    # Métodos públicos para consulta y modificación
    def poblar_formulario(self, receta: Dict):
        """Rellena los inputs con los valores de la receta."""
        for key, entry in self.inputs.items():
            if key in receta:
                entry.delete(0, "end")
                entry.insert(0, str(receta[key]))
                entry.configure(border_color="#CBD5E1")  # resetear validación visual
        # Rotación: cargar ángulo libre si existe, sino compatibilidad con rotar_90_grados
        if "rotacion_grados" in receta:
            ang = float(receta["rotacion_grados"])
        elif "rotar_90_grados" in receta and bool(receta["rotar_90_grados"]):
            ang = 90.0
        else:
            ang = 0.0
        self.slider_rot.set(ang)
        self.entry_rot.delete(0, "end")
        self.entry_rot.insert(0, str(int(ang)))

    def obtener_datos_formulario(self) -> Dict:
        """Lee y convierte los valores del formulario a tipos numéricos."""
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

        # Rotación libre en grados
        try:
            ang = float(self.entry_rot.get().strip())
            ang = max(0, min(360, ang))
        except ValueError:
            ang = 0.0
        datos["rotacion_grados"] = ang
        # Compatibilidad con backend: rotar_90_grados se mantiene como flag
        datos["rotar_90_grados"] = 0
        return datos

    def set_recetas(self, nombres: List[str], seleccionada: Optional[str] = None):
        """Actualiza el dropdown de recetas."""
        self.opt_receta.configure(values=nombres)
        if seleccionada:
            self.opt_receta.set(seleccionada)
        elif nombres:
            self.opt_receta.set(nombres[0])

    def set_delete_visible(self, visible: bool):
        """Muestra u oculta el botón de eliminar receta (protección de recetas predeterminadas)."""
        if visible:
            self.btn_del_receta.pack(side="right")
        else:
            self.btn_del_receta.pack_forget()
