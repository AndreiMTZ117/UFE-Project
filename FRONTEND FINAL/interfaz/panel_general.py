# -*- coding: utf-8 -*-
"""
interfaz/panel_general.py — Panel Central: Canvas General con Reglas y Proporción 1:1
"""

import tkinter as tk
import customtkinter as ctk
from typing import Callable, List, Optional, Tuple

from .constantes import (
    COLOR_CARD, COLOR_BORDER, COLOR_TEXT,
    COLOR_BLUE, COLOR_VECTOR_GRAY, COLOR_YELLOW,
    FONT_TEACHERS, BRUTAL_CORNER, BRUTAL_BORDER
)


class PanelGeneral(ctk.CTkFrame):
    """Panel central con canvas isométrico 1:1, reglas graduadas y diferenciación de trazos/saltos."""

    def __init__(
        self,
        master,
        on_dimensiones_cambiadas: Optional[Callable[[float, float], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_dimensiones_cambiadas = on_dimensiones_cambiadas
        self.f_head = ctk.CTkFont(family=FONT_TEACHERS, size=13, weight="bold")
        self.f_bold = ctk.CTkFont(family=FONT_TEACHERS, size=11, weight="bold")
        self.f_regular = ctk.CTkFont(family=FONT_TEACHERS, size=11)
        self.f_legend = ctk.CTkFont(family=FONT_TEACHERS, size=10, weight="bold")

        self.trazos_actuales: List[List[Tuple[float, float]]] = []
        self.trazos_completados: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        self.saltos_actuales: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []

        # Dimensiones estándar nativas del campo Thorlabs (±50 mm -> 10.0 x 10.0 cm)
        self.ancho_base_cm = 10.0
        self.alto_base_cm = 10.0

        self._crear_widgets()

    def _crear_widgets(self):
        # 1. Cabecera con título y leyenda de diferenciación espacial
        top_header = ctk.CTkFrame(self, fg_color="transparent")
        top_header.pack(side="top", fill="x", pady=(2, 4))

        self.lbl_title = ctk.CTkLabel(
            top_header,
            text="CANVAS VECTORIAL (ISOMÉTRICO 1:1)",
            font=self.f_head,
            text_color=COLOR_TEXT,
            anchor="w"
        )
        self.lbl_title.pack(side="left")

        # Leyenda de trayectorias
        legend_frame = ctk.CTkFrame(top_header, fg_color="transparent")
        legend_frame.pack(side="right")

        ctk.CTkLabel(
            legend_frame,
            text="― Marcado (Láser ON)",
            font=self.f_legend,
            text_color="#475569"
        ).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            legend_frame,
            text="┄ Salto rápido (Láser OFF)",
            font=self.f_legend,
            text_color="#D97706"
        ).pack(side="left")

        # 2. Footer Area size (EDITABLE)
        self.footer_area = ctk.CTkFrame(self, fg_color="transparent", height=34)
        self.footer_area.pack(side="bottom", fill="x", pady=(6, 0))

        lbl_area = ctk.CTkLabel(self.footer_area, text="CAMPO DE TRABAJO:", font=self.f_bold, text_color=COLOR_TEXT)
        lbl_area.pack(side="left", padx=(2, 6))

        # Píldora editable X
        self.pill_x = ctk.CTkFrame(
            self.footer_area,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER
        )
        self.pill_x.pack(side="left", padx=3)

        ctk.CTkLabel(self.pill_x, text="X =", font=self.f_bold, text_color=COLOR_TEXT).pack(side="left", padx=(8, 2), pady=2)
        self.entry_dim_x = ctk.CTkEntry(
            self.pill_x,
            width=50,
            height=22,
            fg_color="#F8FAFC",
            border_color="#CBD5E1",
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            text_color=COLOR_TEXT
        )
        self.entry_dim_x.insert(0, "10.0")
        self.entry_dim_x.pack(side="left", padx=2, pady=2)
        self.entry_dim_x.bind("<Return>", lambda e: self._cb_dimensiones_cambiadas())
        self.entry_dim_x.bind("<FocusOut>", lambda e: self._cb_dimensiones_cambiadas())

        ctk.CTkLabel(self.pill_x, text="cm", font=self.f_regular, text_color=COLOR_TEXT).pack(side="left", padx=(2, 8), pady=2)

        # Píldora editable Y
        self.pill_y = ctk.CTkFrame(
            self.footer_area,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER
        )
        self.pill_y.pack(side="left", padx=3)

        ctk.CTkLabel(self.pill_y, text="Y =", font=self.f_bold, text_color=COLOR_TEXT).pack(side="left", padx=(8, 2), pady=2)
        self.entry_dim_y = ctk.CTkEntry(
            self.pill_y,
            width=50,
            height=22,
            fg_color="#F8FAFC",
            border_color="#CBD5E1",
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            text_color=COLOR_TEXT
        )
        self.entry_dim_y.insert(0, "10.0")
        self.entry_dim_y.pack(side="left", padx=2, pady=2)
        self.entry_dim_y.bind("<Return>", lambda e: self._cb_dimensiones_cambiadas())
        self.entry_dim_y.bind("<FocusOut>", lambda e: self._cb_dimensiones_cambiadas())

        ctk.CTkLabel(self.pill_y, text="cm", font=self.f_regular, text_color=COLOR_TEXT).pack(side="left", padx=(2, 8), pady=2)

        # 3. Tarjeta de visualización
        self.card_general = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER
        )
        self.card_general.pack(side="top", fill="both", expand=True)

        self.canvas = tk.Canvas(
            self.card_general,
            bg=COLOR_CARD,
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.canvas.bind("<Configure>", lambda e: self.redibujar())

    def _cb_dimensiones_cambiadas(self):
        try:
            ancho = float(self.entry_dim_x.get().strip())
            alto = float(self.entry_dim_y.get().strip())
            if ancho > 0 and alto > 0:
                self.ancho_base_cm = ancho
                self.alto_base_cm = alto
                self.redibujar()
                if self.on_dimensiones_cambiadas:
                    self.on_dimensiones_cambiadas(ancho, alto)
        except ValueError:
            pass

    def actualizar_dimensiones(self, ancho_cm: float, alto_cm: float):
        self.ancho_base_cm = float(ancho_cm)
        self.alto_base_cm = float(alto_cm)
        self.entry_dim_x.delete(0, "end")
        self.entry_dim_x.insert(0, f"{ancho_cm:.1f}")
        self.entry_dim_y.delete(0, "end")
        self.entry_dim_y.insert(0, f"{alto_cm:.1f}")
        self.redibujar()

    def set_limites_hardware(self, x_min: float, x_max: float, y_min: float, y_max: float):
        self._maq_x_min = x_min
        self._maq_x_max = x_max
        self._maq_y_min = y_min
        self._maq_y_max = y_max

    def redibujar(
        self,
        trazos: Optional[List[List[Tuple[float, float]]]] = None,
        trazos_completados: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None,
        saltos_rapidos: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None
    ):
        """Renderizado isométrico 1:1 con diferenciación de trazos de corte y saltos rápidos."""
        if trazos is not None:
            self.trazos_actuales = trazos
        if trazos_completados is not None:
            self.trazos_completados = trazos_completados
        if saltos_rapidos is not None:
            self.saltos_actuales = saltos_rapidos

        c = self.canvas
        c.delete("all")

        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 50 or h <= 50:
            return

        mx = 45  # margen para regla Y
        my = 35  # margen para regla X

        draw_w = w - mx - 20
        draw_h = h - my - 20

        # Dibujar reglas graduadas según dimensiones de base actuales
        self._dibujar_reglas(c, mx, draw_h, draw_w)

        # --- ESCALA BASADA EN EL CAMPO FÍSICO EN CM (1:1 ISOMÉTRICO) ---
        rango_w = max(0.1, self.ancho_base_cm)
        rango_h = max(0.1, self.alto_base_cm)

        escala_pixel = min(draw_w / rango_w, draw_h / rango_h) * 0.92

        base_w_px = rango_w * escala_pixel
        base_h_px = rango_h * escala_pixel
        base_x0 = mx + (draw_w - base_w_px) / 2
        base_y0 = 15 + (draw_h - base_h_px) / 2

        # Rectángulo del campo óptico F-Theta
        c.create_rectangle(
            base_x0, base_y0,
            base_x0 + base_w_px, base_y0 + base_h_px,
            outline="#94A3B8", width=1.5, dash=(6, 4)
        )

        # Cruz del centro óptico nativo (0, 0)
        cx_px = base_x0 + base_w_px / 2.0
        cy_px = base_y0 + base_h_px / 2.0
        c.create_line(cx_px - 8, cy_px, cx_px + 8, cy_px, fill="#CBD5E1", width=1.5)
        c.create_line(cx_px, cy_px - 8, cx_px, cy_px + 8, fill="#CBD5E1", width=1.5)

        if not self.trazos_actuales and not self.saltos_actuales:
            c.create_text(w // 2, h // 2, text="Sin archivo cargado (DXF / G-code)", font=(FONT_TEACHERS, 14), fill="#94A3B8")
            return

        def to_px(x_cm, y_cm):
            px = base_x0 + x_cm * escala_pixel
            py = (base_y0 + base_h_px) - (y_cm * escala_pixel)
            return px, py

        # 1. Dibujar saltos rápidos en vacío (G0 / láser OFF) con línea discontinua ámbar
        for salto in self.saltos_actuales:
            p1, p2 = salto
            px1, py1 = to_px(p1[0], p1[1])
            px2, py2 = to_px(p2[0], p2[1])
            c.create_line(px1, py1, px2, py2, fill="#F59E0B", width=1.2, dash=(4, 4), capstyle="round")

        # 2. Dibujar geometría de corte base completa (láser ON) en línea sólida gris oscuro
        for ruta in self.trazos_actuales:
            if len(ruta) < 2:
                continue
            coords = []
            for pt in ruta:
                px, py = to_px(pt[0], pt[1])
                coords.extend([px, py])
            c.create_line(coords, fill=COLOR_VECTOR_GRAY, width=2.5, capstyle="round", joinstyle="round")

        # 3. Dibujar segmentos completados durante ejecución activa en azul eléctrico
        for segmento in self.trazos_completados:
            p1, p2 = segmento
            px1, py1 = to_px(p1[0], p1[1])
            px2, py2 = to_px(p2[0], p2[1])
            c.create_line(px1, py1, px2, py2, fill=COLOR_BLUE, width=3.5, capstyle="round")

    def _dibujar_reglas(self, c: tk.Canvas, mx: int, draw_h: int, draw_w: int):
        c.create_line(mx, 15, mx, draw_h + 15, fill=COLOR_BORDER, width=BRUTAL_BORDER)
        c.create_line(mx, draw_h + 15, mx + draw_w, draw_h + 15, fill=COLOR_BORDER, width=BRUTAL_BORDER)

        num_ticks = 11
        for i in range(num_ticks):
            # Ticks Eje Y
            y_pos = (draw_h + 15) - (i * (draw_h / (num_ticks - 1)))
            val_y = round(i * (self.alto_base_cm / (num_ticks - 1)) - (self.alto_base_cm / 2.0), 1)
            c.create_line(mx - 6, y_pos, mx, y_pos, fill=COLOR_BORDER, width=1.5)
            c.create_text(mx - 9, y_pos, text=f"{val_y:+.1f}", font=(FONT_TEACHERS, 8), fill=COLOR_TEXT, anchor="e")

            # Ticks Eje X
            x_pos = mx + (i * (draw_w / (num_ticks - 1)))
            val_x = round(i * (self.ancho_base_cm / (num_ticks - 1)) - (self.ancho_base_cm / 2.0), 1)
            c.create_line(x_pos, draw_h + 15, x_pos, draw_h + 21, fill=COLOR_BORDER, width=1.5)
            c.create_text(x_pos, draw_h + 26, text=f"{val_x:+.1f}", font=(FONT_TEACHERS, 8), fill=COLOR_TEXT, anchor="n")
