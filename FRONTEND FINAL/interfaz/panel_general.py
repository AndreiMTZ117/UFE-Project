# -*- coding: utf-8 -*-
"""
interfaz/panel_general.py — Panel Central: Canvas General con Reglas y Proporción 1:1
"""

import math
import tkinter as tk
import customtkinter as ctk
from typing import Callable, List, Optional, Tuple

from .constantes import (
    COLOR_CARD, COLOR_BORDER, COLOR_TEXT,
    COLOR_BLUE, COLOR_VECTOR_GRAY, COLOR_GRID, COLOR_ORANGE,
    FONT_TEACHERS, BRUTAL_CORNER, BRUTAL_BORDER,
    agregar_tooltip
)


class PanelGeneral(ctk.CTkFrame):
    """Panel central con canvas isométrico 1:1, reglas graduadas y base editable."""

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

        self.trazos_actuales: List[List[Tuple[float, float]]] = []
        self.trazos_completados: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        self.ancho_base_cm = 28.0
        self.alto_base_cm = 25.0
        self.centro_home = (14.0, 12.5)
        self.pos_puntero: Tuple[float, float] = (14.0, 12.5)
        self.frame_box_cm: Optional[Tuple[float, float, float, float]] = None

        # Parametros de escala para renderizado incremental
        self._escala_pixel = None
        self._base_x0 = 0.0
        self._base_y0 = 0.0
        self._base_h_px = 0.0

        self._crear_widgets()

    def _crear_widgets(self):
        # 1. Título "General" y Leyenda de Trazos (top)
        top_header = ctk.CTkFrame(self, fg_color="transparent")
        top_header.pack(side="top", fill="x", pady=(2, 4))

        self.lbl_title = ctk.CTkLabel(
            top_header,
            text="VECTOR CANVAS (1:1 ISOMETRIC)",
            font=self.f_head,
            text_color=COLOR_TEXT,
            anchor="w"
        )
        self.lbl_title.pack(side="left")

        # Leyenda de trazos horizontal arriba del recuadro
        self.legend_frame = ctk.CTkFrame(
            top_header,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=28
        )
        self.legend_frame.pack(side="right")

        f_leg = ctk.CTkFont(family=FONT_TEACHERS, size=9, weight="bold")

        # 1. Guía CAD (Gris)
        box_guide = ctk.CTkFrame(self.legend_frame, fg_color="transparent")
        box_guide.pack(side="left", padx=(8, 4), pady=2)
        c_guide = tk.Canvas(box_guide, width=20, height=14, bg=COLOR_CARD, highlightthickness=0)
        c_guide.pack(side="left")
        c_guide.create_line(2, 7, 18, 7, fill=COLOR_VECTOR_GRAY, width=2.5, capstyle="round")
        ctk.CTkLabel(box_guide, text="Target Vector (Guide)", font=f_leg, text_color=COLOR_TEXT).pack(side="left", padx=(3, 2))

        # Separador vertical
        ctk.CTkFrame(self.legend_frame, width=1, height=14, fg_color="#CBD5E1").pack(side="left", padx=3, pady=4)

        # 2. Salto en vacío (Naranja punteado)
        box_jump = ctk.CTkFrame(self.legend_frame, fg_color="transparent")
        box_jump.pack(side="left", padx=(4, 4), pady=2)
        c_jump = tk.Canvas(box_jump, width=28, height=16, bg=COLOR_CARD, highlightthickness=0)
        c_jump.pack(side="left")
        # Bolitas naranjas notorias de 6px de diámetro
        r_bolita = 3.0
        cy = 8.0
        for bx in (5.0, 13.0, 21.0):
            c_jump.create_oval(bx - r_bolita, cy - r_bolita, bx + r_bolita, cy + r_bolita, fill=COLOR_ORANGE, outline="")
        lbl_jump = ctk.CTkLabel(box_jump, text="Rapid Jump (G0, Laser OFF)", font=f_leg, text_color=COLOR_TEXT)
        lbl_jump.pack(side="left", padx=(4, 6))

        # Separador vertical
        ctk.CTkFrame(self.legend_frame, width=1, height=14, fg_color="#CBD5E1").pack(side="left", padx=3, pady=4)

        # 3. Trazo ejecutado activo (Azul eléctrico)
        box_trail = ctk.CTkFrame(self.legend_frame, fg_color="transparent")
        box_trail.pack(side="left", padx=(4, 4), pady=2)
        c_trail = tk.Canvas(box_trail, width=20, height=14, bg=COLOR_CARD, highlightthickness=0)
        c_trail.pack(side="left")
        c_trail.create_line(2, 7, 18, 7, fill=COLOR_BLUE, width=3.5, capstyle="round")
        ctk.CTkLabel(box_trail, text="Executed Toolpath Trail", font=f_leg, text_color=COLOR_TEXT).pack(side="left", padx=(3, 2))

        # Separador vertical
        ctk.CTkFrame(self.legend_frame, width=1, height=14, fg_color="#CBD5E1").pack(side="left", padx=3, pady=4)

        # 4. Puntero del haz (Punto verde)
        box_pointer = ctk.CTkFrame(self.legend_frame, fg_color="transparent")
        box_pointer.pack(side="left", padx=(4, 8), pady=2)
        c_pointer = tk.Canvas(box_pointer, width=16, height=14, bg=COLOR_CARD, highlightthickness=0)
        c_pointer.pack(side="left")
        c_pointer.create_oval(4, 3, 12, 11, fill="#22C55E", outline="#15803D", width=1.0)
        ctk.CTkLabel(box_pointer, text="Beam Cursor", font=f_leg, text_color=COLOR_TEXT).pack(side="left", padx=(3, 2))

        agregar_tooltip(
            self.legend_frame,
            "Toolpath line guide:\n"
            "• Gray: Target CAD geometry\n"
            "• Dashed Orange: Rapid traverse without laser\n"
            "• Blue: Laser-processed toolpath\n"
            "• Green dot: Real-time beam / cursor position"
        )

        # 2. Footer Area size (anclado abajo primero, EDITABLE)
        self.footer_area = ctk.CTkFrame(self, fg_color="transparent", height=34)
        self.footer_area.pack(side="bottom", fill="x", pady=(6, 0))

        lbl_area = ctk.CTkLabel(self.footer_area, text="BASE AREA:", font=self.f_bold, text_color=COLOR_TEXT)
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
        self.entry_dim_x.insert(0, "28.0")
        self.entry_dim_x.pack(side="left", padx=2, pady=2)
        self.entry_dim_x.bind("<Return>", lambda e: self._cb_dimensiones_cambiadas())
        self.entry_dim_x.bind("<FocusOut>", lambda e: self._cb_dimensiones_cambiadas())

        ctk.CTkLabel(self.pill_x, text="cm", font=self.f_regular, text_color=COLOR_TEXT).pack(side="left", padx=(2, 8), pady=2)
        agregar_tooltip(self.pill_x, "Width (X axis) of the physical base or workpiece, in centimeters.\n"
                                     "Defines the canvas scale and drawing placement area. "
                                     "Press Enter to apply.")

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
        self.entry_dim_y.insert(0, "25.0")
        self.entry_dim_y.pack(side="left", padx=2, pady=2)
        self.entry_dim_y.bind("<Return>", lambda e: self._cb_dimensiones_cambiadas())
        self.entry_dim_y.bind("<FocusOut>", lambda e: self._cb_dimensiones_cambiadas())

        ctk.CTkLabel(self.pill_y, text="cm", font=self.f_regular, text_color=COLOR_TEXT).pack(side="left", padx=(2, 8), pady=2)
        agregar_tooltip(self.pill_y, "Height (Y axis) of the physical base or workpiece, in centimeters.\n"
                                     "Defines the canvas scale and drawing placement area. "
                                     "Press Enter to apply.")

        # 3. Tarjeta blanca con borde negro grueso (al centro expandible, simple cuadrado)
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

    def set_bloqueo_ejecucion(self, bloqueado: bool):
        """Bloquea o habilita la edición de dimensiones de la base durante la ejecución."""
        self.bloqueado_ejecucion = bloqueado
        estado = "disabled" if bloqueado else "normal"
        self.entry_dim_x.configure(state=estado)
        self.entry_dim_y.configure(state=estado)

    def _cb_dimensiones_cambiadas(self):
        if getattr(self, "bloqueado_ejecucion", False):
            return
        try:
            ancho = float(self.entry_dim_x.get().strip())
            alto = float(self.entry_dim_y.get().strip())
            if ancho > 0 and alto > 0:
                self.ocultar_frame_dxf()
                self.ancho_base_cm = ancho
                self.alto_base_cm = alto
                self.redibujar()
                if self.on_dimensiones_cambiadas:
                    self.on_dimensiones_cambiadas(ancho, alto)
        except ValueError:
            pass

    def actualizar_dimensiones(self, ancho_cm: float, alto_cm: float):
        """Actualiza los inputs numéricos de dimensiones de la base / pieza."""
        try:
            self.ocultar_frame_dxf()
            self.ancho_base_cm = float(ancho_cm)
            self.alto_base_cm = float(alto_cm)
            prev_x = self.entry_dim_x.cget("state")
            prev_y = self.entry_dim_y.cget("state")
            self.entry_dim_x.configure(state="normal")
            self.entry_dim_y.configure(state="normal")
            self.entry_dim_x.delete(0, "end")
            self.entry_dim_x.insert(0, f"{self.ancho_base_cm:.1f}")
            self.entry_dim_y.delete(0, "end")
            self.entry_dim_y.insert(0, f"{self.alto_base_cm:.1f}")
            self.entry_dim_x.configure(state=prev_x)
            self.entry_dim_y.configure(state=prev_y)
            self.redibujar()
        except Exception:
            pass

    def set_limites_hardware(self, x_min: float, x_max: float, y_min: float, y_max: float):
        """Define los límites absolutos del hardware/máquina para mapeo fiel en canvas."""
        self._maq_x_min = x_min
        self._maq_x_max = x_max
        self._maq_y_min = y_min
        self._maq_y_max = y_max

    def set_centro(self, x: float, y: float):
        """Define el centro físico de reposo (Home) para los saltos en vacío."""
        try:
            self.centro_home = (float(x), float(y))
            self.pos_puntero = (float(x), float(y))
            self.redibujar()
        except Exception:
            pass


    def redibujar(
        self,
        trazos: Optional[List[List[Tuple[float, float]]]] = None,
        trazos_completados: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None
    ):
        """Renderizado isometrico 1:1 basado en las dimensiones de la base fisica.
        
        Cuando se llama con nuevos trazos (carga DXF / cambio receta), redibuja todo.
        Durante la ejecucion, solo se usa agregar_segmento_completado para incrementar.
        """
        if trazos is not None:
            self.trazos_actuales = trazos
            # Limpiar completados si cambio la figura base
            self.trazos_completados = []
        if trazos_completados is not None:
            self.trazos_completados = trazos_completados

        c = self.canvas
        try:
            c.delete("all")
        except Exception:
            return

        try:
            w = c.winfo_width()
            h = c.winfo_height()
        except Exception:
            return

        if w <= 50 or h <= 50:
            return

        pad_left = 38     # Espacio para ticks y números del eje Y
        pad_right = 50    # Espacio para "X [cm]"
        pad_top = 22      # Espacio para "Y [cm]"
        pad_bottom = 28   # Espacio para ticks y números del eje X

        avail_w = max(10, w - pad_left - pad_right)
        avail_h = max(10, h - pad_top - pad_bottom)

        try:
            rango_w = float(self.ancho_base_cm)
            if rango_w <= 0 or math.isnan(rango_w) or math.isinf(rango_w):
                rango_w = 28.0
        except Exception:
            rango_w = 28.0

        try:
            rango_h = float(self.alto_base_cm)
            if rango_h <= 0 or math.isnan(rango_h) or math.isinf(rango_h):
                rango_h = 25.0
        except Exception:
            rango_h = 25.0

        # Escala isométrica 1:1 estricta
        self._escala_pixel = min(avail_w / rango_w, avail_h / rango_h) * 0.96
        base_w_px = rango_w * self._escala_pixel
        base_h_px = rango_h * self._escala_pixel

        # Centrar la base dentro del área de dibujo
        self._base_x0 = pad_left + (avail_w - base_w_px) / 2.0
        self._base_y0 = pad_top + (avail_h - base_h_px) / 2.0
        self._base_h_px = base_h_px

        # Dibujar reglas graduadas alineadas exactamente con el contorno de la base
        try:
            self._dibujar_reglas(c, self._base_x0, self._base_y0, base_w_px, base_h_px)
        except Exception:
            pass

        if not self.trazos_actuales:
            try:
                c.create_text(w // 2, h // 2, text="No DXF file loaded", font=(FONT_TEACHERS, 14), fill="#94A3B8")
            except Exception:
                pass
            if getattr(self, "pos_puntero", None) is not None:
                self.actualizar_puntero(self.pos_puntero[0], self.pos_puntero[1])
            return

        # Helper: mapear coordenada fisica metrica (cm) -> pixel del canvas
        def to_px(x_cm, y_cm):
            px = self._base_x0 + float(x_cm) * self._escala_pixel
            py = (self._base_y0 + self._base_h_px) - (float(y_cm) * self._escala_pixel)
            return px, py

        # 1. Dibujar saltos en vacío (G0 rapid jumps) con línea punteada naranja ANTES de la geometría
        hx, hy = getattr(self, "centro_home", (rango_w / 2.0, rango_h / 2.0))
        pos_salto = (hx, hy)
        viajes = []
        for ruta in self.trazos_actuales:
            if ruta:
                p_inicio = ruta[0]
                if abs(pos_salto[0] - p_inicio[0]) > 1e-4 or abs(pos_salto[1] - p_inicio[1]) > 1e-4:
                    viajes.append((pos_salto, p_inicio))
                pos_salto = ruta[-1]
        if abs(pos_salto[0] - hx) > 1e-4 or abs(pos_salto[1] - hy) > 1e-4:
            viajes.append((pos_salto, (hx, hy)))

        for p1, p2 in viajes:
            if not p1 or not p2 or len(p1) < 2 or len(p2) < 2:
                continue
            try:
                px1, py1 = to_px(p1[0], p1[1])
                px2, py2 = to_px(p2[0], p2[1])
                if abs(px1 - px2) >= 0.5 or abs(py1 - py2) >= 0.5:
                    c.create_line(px1, py1, px2, py2, fill=COLOR_ORANGE, width=2.2, dash=(4, 4), capstyle="round")
            except Exception:
                pass

        # 2. Dibujar geometria base completa (guía vectorial CAD) en gris
        total_puntos = sum(len(r) for r in self.trazos_actuales if r)
        stride_render = max(1, math.ceil(total_puntos / 25000)) if total_puntos > 25000 else 1

        for ruta in self.trazos_actuales:
            if not ruta:
                continue
            if len(ruta) == 1:
                try:
                    px, py = to_px(ruta[0][0], ruta[0][1])
                    c.create_oval(px - 1.5, py - 1.5, px + 1.5, py + 1.5, fill=COLOR_VECTOR_GRAY, outline="")
                except Exception:
                    pass
                continue

            if stride_render > 1 and len(ruta) > stride_render:
                pts_render = [ruta[i] for i in range(0, len(ruta), stride_render)]
                if (len(ruta) - 1) % stride_render != 0:
                    pts_render.append(ruta[-1])
            else:
                pts_render = ruta

            coords = []
            for pt in pts_render:
                if pt and len(pt) >= 2:
                    try:
                        px, py = to_px(pt[0], pt[1])
                        coords.extend([px, py])
                    except Exception:
                        pass
            if len(coords) >= 4:
                try:
                    c.create_line(coords, fill=COLOR_VECTOR_GRAY, width=2.5, capstyle="round", joinstyle="round")
                except Exception:
                    pass
            elif len(coords) == 2:
                try:
                    c.create_oval(coords[0] - 1.5, coords[1] - 1.5, coords[0] + 1.5, coords[1] + 1.5, fill=COLOR_VECTOR_GRAY, outline="")
                except Exception:
                    pass

        # 3. Redibujar segmentos completados (solo al reiniciar/cambiar figura) en azul eléctrico
        for segmento in self.trazos_completados:
            if not segmento or len(segmento) < 2:
                continue
            p1, p2 = segmento[0], segmento[1]
            if not p1 or not p2 or len(p1) < 2 or len(p2) < 2:
                continue
            try:
                px1, py1 = to_px(p1[0], p1[1])
                px2, py2 = to_px(p2[0], p2[1])
                c.create_line(px1, py1, px2, py2, fill=COLOR_BLUE, width=3.5,
                              capstyle="round", tags="completado")
            except Exception:
                pass

        # 4. Redibujar marco perimetral naranja si está activo
        if getattr(self, "frame_box_cm", None) is not None:
            self._dibujar_frame_dxf(c)

        # 5. Dibujar puntero del haz láser (puntito verde en coordenadas del cursor)
        if getattr(self, "pos_puntero", None) is not None:
            self.actualizar_puntero(self.pos_puntero[0], self.pos_puntero[1])

    def actualizar_puntero(self, x_cm: float, y_cm: float):
        """Actualiza la posición visual del puntero/cursor láser (puntito verde) en el canvas 1:1."""
        try:
            self.pos_puntero = (float(x_cm), float(y_cm))
            c = self.canvas
            c.delete("puntero_laser")
            if not hasattr(self, '_escala_pixel') or self._escala_pixel is None:
                return
            px = self._base_x0 + float(x_cm) * self._escala_pixel
            py = (self._base_y0 + self._base_h_px) - (float(y_cm) * self._escala_pixel)
            r = 3.5  # Puntito pequeño visible y nítido (7px de diámetro)
            c.create_oval(
                px - r, py - r, px + r, py + r,
                fill="#22C55E", outline="#15803D", width=1.0,
                tags="puntero_laser"
            )
            c.tag_raise("puntero_laser")
        except Exception:
            pass

    def mostrar_frame_dxf(self, bbox_cm: Optional[Tuple[float, float, float, float]] = None):
        """
        Calcula y dibuja el marco rectangular delimitador (Bounding Box) en línea naranja punteada
        al pulsar el botón de encuadre (Framing) en el panel izquierdo.
        """
        if bbox_cm is not None:
            self.frame_box_cm = bbox_cm
        elif self.trazos_actuales:
            all_x = [pt[0] for ruta in self.trazos_actuales for pt in ruta if pt and len(pt) >= 2]
            all_y = [pt[1] for ruta in self.trazos_actuales for pt in ruta if pt and len(pt) >= 2]
            if all_x and all_y:
                self.frame_box_cm = (min(all_x), min(all_y), max(all_x), max(all_y))
            else:
                self.frame_box_cm = None
        else:
            self.frame_box_cm = None

        if self.frame_box_cm is not None:
            self._dibujar_frame_dxf(self.canvas)

    def _dibujar_frame_dxf(self, c: tk.Canvas):
        """Dibuja el marco de límites delimitadores del DXF en línea naranja punteada."""
        if getattr(self, "frame_box_cm", None) is None:
            return
        if not hasattr(self, '_escala_pixel') or self._escala_pixel is None:
            return

        try:
            c.delete("frame_dxf")
            min_x, min_y, max_x, max_y = self.frame_box_cm

            def to_px(x_cm, y_cm):
                px = self._base_x0 + float(x_cm) * self._escala_pixel
                py = (self._base_y0 + self._base_h_px) - (float(y_cm) * self._escala_pixel)
                return px, py

            px1, py1 = to_px(min_x, min_y)
            px2, py2 = to_px(max_x, max_y)

            # Rectángulo delimitador cerrado:
            # (min_x, min_y) -> (max_x, min_y) -> (max_x, max_y) -> (min_x, max_y) -> (min_x, min_y)
            coords = [px1, py1, px2, py1, px2, py2, px1, py2, px1, py1]
            c.create_line(
                coords,
                fill=COLOR_ORANGE,
                width=2.2,
                dash=(4, 4),
                capstyle="round",
                joinstyle="round",
                tags="frame_dxf"
            )
            c.tag_raise("frame_dxf")
            if getattr(self, "pos_puntero", None) is not None:
                c.tag_raise("puntero_laser")
        except Exception:
            pass

    def ocultar_frame_dxf(self):
        """Oculta y elimina el marco naranja punteado de delimitación DXF de forma no permanente."""
        self.frame_box_cm = None
        try:
            self.canvas.delete("frame_dxf")
        except Exception:
            pass

    def limpiar_completados(self):
        """Elimina todos los segmentos marcados/completados del canvas y limpia la lista interna."""
        self.trazos_completados = []
        try:
            self.canvas.delete("completado")
        except Exception:
            pass

    def agregar_segmento_completado(
        self, p1: Tuple[float, float], p2: Tuple[float, float], forzar: bool = False
    ) -> bool:
        """
        Renderizado INCREMENTAL: agrega solo el nuevo segmento completado al canvas
        sin redibujar toda la figura. Esto evita el trabamiento al acumularse trazos.

        Retorna True si el segmento se dibuja. Si el desplazamiento es insignificante
        y no se fuerza, no se dibuja y retorna False para que el llamador acumule.
        """
        c = self.canvas
        if not hasattr(self, '_escala_pixel') or self._escala_pixel is None:
            return False  # Canvas aun no inicializado
        try:
            if c.winfo_width() <= 50 or c.winfo_height() <= 50:
                return False
        except Exception:
            return False

        if not p1 or not p2 or len(p1) < 2 or len(p2) < 2:
            return False

        def to_px(x_cm, y_cm):
            px = self._base_x0 + float(x_cm) * self._escala_pixel
            py = (self._base_y0 + self._base_h_px) - (float(y_cm) * self._escala_pixel)
            return px, py

        try:
            px1, py1 = to_px(p1[0], p1[1])
            px2, py2 = to_px(p2[0], p2[1])
        except Exception:
            return False

        dx = px2 - px1
        dy = py2 - py1
        distancia_sq = dx * dx + dy * dy
        if distancia_sq <= 0.0 or (distancia_sq < 0.25 and not forzar):
            return False

        try:
            c.create_line(px1, py1, px2, py2, fill=COLOR_BLUE, width=3.5,
                          capstyle="round", tags="completado")
            return True
        except Exception:
            return False

    def _calcular_ticks(self, val_max: float, max_intervals: int = 10) -> List[float]:
        try:
            val_max = float(val_max)
            if math.isnan(val_max) or math.isinf(val_max) or val_max <= 0:
                return [0.0]
        except Exception:
            return [0.0]

        posibles_pasos = [0.5, 1.0, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0, 15.0, 20.0, 25.0, 50.0]
        paso_elegido = None
        for p in posibles_pasos:
            num_int = val_max / p
            if 3 <= num_int <= max_intervals and abs(val_max % p) < 1e-4:
                paso_elegido = p
                break
        if paso_elegido is None:
            for p in posibles_pasos:
                if (val_max / p) <= max_intervals:
                    paso_elegido = p
                    break
        if paso_elegido is None:
            paso_elegido = max(0.1, round(val_max / 10.0, 1))

        ticks = []
        val = 0.0
        while val <= val_max + 1e-4:
            ticks.append(round(val, 2))
            val += paso_elegido
            if len(ticks) > 100:  # Guarda contra bucle infinito
                break

        if not ticks:
            ticks = [0.0]

        if ticks[-1] < val_max - 1e-4:
            ticks.append(round(val_max, 2))
        return ticks

    def _dibujar_reglas(self, c: tk.Canvas, x0: float, y0: float, w_px: float, h_px: float):
        if w_px <= 5 or h_px <= 5:
            return

        x1 = x0 + w_px
        y1 = y0 + h_px

        # 1. Rectángulo de base visible (contorno punteado gris pegado exactamente a min y max)
        c.create_rectangle(
            x0, y0, x1, y1,
            outline="#94A3B8", width=1.5, dash=(6, 4)
        )

        # 2. Generar ticks métricos exactos
        ticks_y = self._calcular_ticks(self.alto_base_cm)
        ticks_x = self._calcular_ticks(self.ancho_base_cm)

        # Eje Y: Ticks, etiquetas y grilla interna
        rango_y = max(0.1, self.alto_base_cm)
        for val_y in ticks_y:
            y_pos = y1 - (val_y / rango_y) * h_px
            # Grilla métrica interna
            c.create_line(x0, y_pos, x1, y_pos, fill=COLOR_GRID, width=1)
            # Tick a la izquierda
            c.create_line(x0 - 5, y_pos, x0, y_pos, fill=COLOR_BORDER, width=1.5)
            # Etiqueta numérica
            texto_y = f"{int(val_y)}" if abs(val_y - round(val_y)) < 1e-4 else f"{val_y:.1f}"
            c.create_text(x0 - 8, y_pos, text=texto_y, font=(FONT_TEACHERS, 8), fill=COLOR_TEXT, anchor="e")

        # Eje X: Ticks, etiquetas y grilla interna
        rango_x = max(0.1, self.ancho_base_cm)
        for val_x in ticks_x:
            x_pos = x0 + (val_x / rango_x) * w_px
            # Grilla métrica interna
            c.create_line(x_pos, y0, x_pos, y1, fill=COLOR_GRID, width=1)
            # Tick abajo
            c.create_line(x_pos, y1, x_pos, y1 + 5, fill=COLOR_BORDER, width=1.5)
            # Etiqueta numérica
            texto_x = f"{int(val_x)}" if abs(val_x - round(val_x)) < 1e-4 else f"{val_x:.1f}"
            c.create_text(x_pos, y1 + 7, text=texto_x, font=(FONT_TEACHERS, 8), fill=COLOR_TEXT, anchor="n")

        # 3. Ejes principales sólidos en borde carbón (pegados a los bordes izquierdo e inferior)
        c.create_line(x0, y0, x0, y1, fill=COLOR_BORDER, width=BRUTAL_BORDER)  # Eje Y
        c.create_line(x0, y1, x1, y1, fill=COLOR_BORDER, width=BRUTAL_BORDER)  # Eje X

        # 4. Rótulos de ejes: "Y [cm]" arriba del eje Y y "X [cm]" a la derecha del eje X
        c.create_text(x0 - 4, y0 - 8, text="Y [cm]", font=(FONT_TEACHERS, 8, "bold"), fill=COLOR_TEXT, anchor="sw")
        c.create_text(x1 + 6, y1, text="X [cm]", font=(FONT_TEACHERS, 8, "bold"), fill=COLOR_TEXT, anchor="w")
