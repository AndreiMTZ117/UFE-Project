# -*- coding: utf-8 -*-
"""central canvas panel with graduated rulers and 1 to 1 isometric scale"""


import math
import tkinter as tk
import customtkinter as ctk
from typing import Callable, List, Optional, Tuple

from .constantes import (
    COLOR_CARD, COLOR_BORDER, COLOR_TEXT,
    COLOR_BLUE, COLOR_BLUE_FADED, COLOR_VECTOR_GRAY, COLOR_GRID, COLOR_ORANGE,
    COLOR_YELLOW, COLOR_MUTED,
    FONT_TEACHERS, FONT_SEGOE, BRUTAL_CORNER, BRUTAL_BORDER,
    agregar_tooltip
)
from .i18n import tr, registrar_observador, obtener_idioma


class PanelGeneral(ctk.CTkFrame):
    """central canvas panel with 1 to 1 isometric scale graduated rulers and editable base"""

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
        self.f_leg = ctk.CTkFont(family=FONT_TEACHERS, size=11, weight="bold")
        self.f_sub_leg = ctk.CTkFont(family=FONT_TEACHERS, size=10)

        self.trazos_actuales: List[List[Tuple[float, float]]] = []
        self.trazos_completados: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        self.trazos_pasadas_previas: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        self.ancho_base_cm = 28.0
        self.alto_base_cm = 25.0
        self.centro_home = (14.0, 12.5)
        self.pos_puntero: Tuple[float, float] = (14.0, 12.5)
        self.frame_box_cm: Optional[Tuple[float, float, float, float]] = None
        self._frustum_zoom_cm: Optional[Tuple[float, float, float, float]] = None

        #hardware feedback tracking measured trajectory in cm
        self._fb_pts_cm: List[Tuple[float, float]] = []
        self._fb_visible = False

        #responsive legend state
        self._modo_compacto_leyenda = False
        self._popup_abierto = False

        #scale parameters for incremental rendering
        self._escala_pixel = None
        self._base_x0 = 0.0
        self._base_y0 = 0.0
        self._base_h_px = 0.0

        self._crear_widgets()
        registrar_observador(self.actualizar_idioma)


    def _crear_widgets(self):
        #general title and toolpath legend
        self.top_header = ctk.CTkFrame(self, fg_color="transparent")
        self.top_header.pack(side="top", fill="x", pady=(2, 4))
        self.top_header.bind("<Configure>", self._on_header_configure)

        self.lbl_title = ctk.CTkLabel(
            self.top_header,
            text=tr("canvas_title"),
            font=self.f_head,
            text_color=COLOR_TEXT,
            anchor="w"
        )
        self.lbl_title.pack(side="left")

        #horizontal toolpath legend
        self.legend_frame = ctk.CTkFrame(
            self.top_header,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=28
        )
        self.legend_frame.pack(side="right")

        f_leg = self.f_leg

        #cad guide
        box_guide = ctk.CTkFrame(self.legend_frame, fg_color="transparent")
        box_guide.pack(side="left", padx=(8, 4), pady=2)
        c_guide = tk.Canvas(box_guide, width=20, height=14, bg=COLOR_CARD, highlightthickness=0)
        c_guide.pack(side="left")
        c_guide.create_line(2, 7, 18, 7, fill=COLOR_VECTOR_GRAY, width=2.5, capstyle="round")
        self.lbl_legend_guide = ctk.CTkLabel(box_guide, text=tr("legend_guide"), font=f_leg, text_color=COLOR_TEXT)
        self.lbl_legend_guide.pack(side="left", padx=(3, 2))

        #vertical separator
        ctk.CTkFrame(self.legend_frame, width=1, height=14, fg_color="#CBD5E1").pack(side="left", padx=3, pady=4)

        #rapid traverse jump
        box_jump = ctk.CTkFrame(self.legend_frame, fg_color="transparent")
        box_jump.pack(side="left", padx=(4, 4), pady=2)
        c_jump = tk.Canvas(box_jump, width=28, height=16, bg=COLOR_CARD, highlightthickness=0)
        c_jump.pack(side="left")
        #marker dots
        r_bolita = 3.0
        cy = 8.0
        for bx in (5.0, 13.0, 21.0):
            c_jump.create_oval(bx - r_bolita, cy - r_bolita, bx + r_bolita, cy + r_bolita, fill=COLOR_ORANGE, outline="")
        self.lbl_legend_jump = ctk.CTkLabel(box_jump, text=tr("legend_jump"), font=f_leg, text_color=COLOR_TEXT)
        self.lbl_legend_jump.pack(side="left", padx=(4, 6))

        #vertical separator
        ctk.CTkFrame(self.legend_frame, width=1, height=14, fg_color="#CBD5E1").pack(side="left", padx=3, pady=4)

        #active executed toolpath
        box_trail = ctk.CTkFrame(self.legend_frame, fg_color="transparent")
        box_trail.pack(side="left", padx=(4, 4), pady=2)
        c_trail = tk.Canvas(box_trail, width=20, height=14, bg=COLOR_CARD, highlightthickness=0)
        c_trail.pack(side="left")
        c_trail.create_line(2, 7, 18, 7, fill=COLOR_BLUE, width=3.5, capstyle="round")
        self.lbl_legend_trail = ctk.CTkLabel(box_trail, text=tr("legend_trace"), font=f_leg, text_color=COLOR_TEXT)
        self.lbl_legend_trail.pack(side="left", padx=(3, 2))

        #vertical separator
        ctk.CTkFrame(self.legend_frame, width=1, height=14, fg_color="#CBD5E1").pack(side="left", padx=3, pady=4)

        #beam pointer
        box_pointer = ctk.CTkFrame(self.legend_frame, fg_color="transparent")
        box_pointer.pack(side="left", padx=(4, 8), pady=2)
        c_pointer = tk.Canvas(box_pointer, width=16, height=14, bg=COLOR_CARD, highlightthickness=0)
        c_pointer.pack(side="left")
        c_pointer.create_oval(4, 3, 12, 11, fill="#22C55E", outline="#15803D", width=1.0)
        self.lbl_legend_pointer = ctk.CTkLabel(box_pointer, text=tr("legend_pointer"), font=f_leg, text_color=COLOR_TEXT)
        self.lbl_legend_pointer.pack(side="left", padx=(3, 2))

        #feedback measured trajectory
        self.sep_legend_fb = ctk.CTkFrame(self.legend_frame, width=1, height=14, fg_color="#CBD5E1")
        self.box_legend_fb = ctk.CTkFrame(self.legend_frame, fg_color="transparent")
        c_fb = tk.Canvas(self.box_legend_fb, width=20, height=14, bg=COLOR_CARD, highlightthickness=0)
        c_fb.pack(side="left")
        c_fb.create_line(2, 7, 18, 7, fill="#D946EF", width=3.0, capstyle="round")
        self.lbl_legend_fb = ctk.CTkLabel(self.box_legend_fb, text=tr("legend_measured"), font=f_leg, text_color=COLOR_TEXT)
        self.lbl_legend_fb.pack(side="left", padx=(3, 8))

        agregar_tooltip(
            self.legend_frame,
            "Toolpath line guide:\n"
            "• Gray: Target CAD geometry\n"
            "• Dashed Orange: Rapid traverse without laser\n"
            "• Blue: Laser-processed toolpath\n"
            "• Green dot: Real-time beam / cursor position"
        )

        #compact dropdown button
        self.btn_legend_toggle = ctk.CTkButton(
            self.top_header,
            text=f"{tr('legend_btn_guide')}",
            command=self._toggle_popup_leyenda,
            font=self.f_leg,
            height=26,
            width=88,
            fg_color=COLOR_CARD,
            text_color=COLOR_TEXT,
            hover_color=COLOR_YELLOW,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER
        )
        agregar_tooltip(self.btn_legend_toggle, tr("legend_btn_tooltip"))

        #floating popover card
        self._crear_popup_leyenda()

        #initial size check
        self.after(50, lambda: self._ajustar_modo_leyenda(self.top_header.winfo_width()))

        #footer area size
        self.footer_area = ctk.CTkFrame(self, fg_color="transparent", height=34)
        self.footer_area.pack(side="bottom", fill="x", pady=(6, 0))

        self.lbl_area = ctk.CTkLabel(self.footer_area, text=f"{tr('base_dim_title')}:", font=self.f_bold, text_color=COLOR_TEXT)
        self.lbl_area.pack(side="left", padx=(2, 6))

        #editable x dimension
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

        #editable y dimension
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

        #canvas card container
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
        self.canvas.bind("<ButtonPress-1>", lambda e: self._cerrar_popup_leyenda(), add="+")

    def set_bloqueo_ejecucion(self, bloqueado: bool):
        """lock or unlock base dimensions editing during execution"""
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
        """update base dimension numeric entry fields"""
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
        """set absolute hardware limits for canvas mapping"""
        self._maq_x_min = x_min
        self._maq_x_max = x_max
        self._maq_y_min = y_min
        self._maq_y_max = y_max

    def set_centro(self, x: float, y: float):
        """set physical home center coordinates"""
        try:
            self.centro_home = (float(x), float(y))
            self.pos_puntero = (float(x), float(y))
            self.redibujar()
        except Exception:
            pass


    def redibujar(
        self,
        trazos: Optional[List[List[Tuple[float, float]]]] = None,
        trazos_completados: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None,
        trazos_pasadas_previas: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None
    ):
        """full 1 to 1 isometric redraw on base canvas"""
        if trazos is not None:
            self.trazos_actuales = trazos
            #clear completed segments on base geometry change
            self.trazos_completados = []
            self.trazos_pasadas_previas = []
        if trazos_completados is not None:
            self.trazos_completados = list(trazos_completados)
        if trazos_pasadas_previas is not None:
            self.trazos_pasadas_previas = list(trazos_pasadas_previas)

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

        pad_left = 38     #space for y axis ticks and labels
        pad_right = 50    #space for x axis label
        pad_top = 22      #space for y axis label
        pad_bottom = 28   #space for x axis ticks and labels

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

        #strict 1 to 1 isometric scale
        self._escala_pixel = min(avail_w / rango_w, avail_h / rango_h) * 0.96
        base_w_px = rango_w * self._escala_pixel
        base_h_px = rango_h * self._escala_pixel

        #center base in drawing area
        self._base_x0 = pad_left + (avail_w - base_w_px) / 2.0
        self._base_y0 = pad_top + (avail_h - base_h_px) / 2.0
        self._base_h_px = base_h_px

        #draw graduated rulers aligned with base outline
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
            if getattr(self, "_frustum_zoom_cm", None) is not None:
                self._dibujar_frustum_zoom(c)
            return

        #map physical coordinates in cm to canvas pixels
        def to_px(x_cm, y_cm):
            px = self._base_x0 + float(x_cm) * self._escala_pixel
            py = (self._base_y0 + self._base_h_px) - (float(y_cm) * self._escala_pixel)
            return px, py

        #draw rapid jumps before geometry
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

        #draw complete base geometry in gray
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

        #redraw previous passes in faded blue
        for segmento in getattr(self, "trazos_pasadas_previas", []):
            if not segmento or len(segmento) < 2:
                continue
            p1, p2 = segmento[0], segmento[1]
            if not p1 or not p2 or len(p1) < 2 or len(p2) < 2:
                continue
            try:
                px1, py1 = to_px(p1[0], p1[1])
                px2, py2 = to_px(p2[0], p2[1])
                c.create_line(px1, py1, px2, py2, fill=COLOR_BLUE_FADED, width=2.5,
                              capstyle="round", tags="pasada_previa")
            except Exception:
                pass

        #redraw active pass completed segments in electric blue
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

        #redraw orange perimeter framing box
        if getattr(self, "frame_box_cm", None) is not None:
            self._dibujar_frame_dxf(c)

        #draw laser beam pointer
        if getattr(self, "pos_puntero", None) is not None:
            self.actualizar_puntero(self.pos_puntero[0], self.pos_puntero[1])

        #redraw zoom camera frustum box
        if getattr(self, "_frustum_zoom_cm", None) is not None:
            self._dibujar_frustum_zoom(c)

        #redraw feedback measured trajectory
        if self._fb_pts_cm:
            self._redibujar_feedback_completo(c)

    def actualizar_puntero(self, x_cm: float, y_cm: float):
        """update laser beam pointer visual position on 1 to 1 canvas"""
        try:
            self.pos_puntero = (float(x_cm), float(y_cm))
            c = self.canvas
            c.delete("puntero_laser")
            if not hasattr(self, '_escala_pixel') or self._escala_pixel is None:
                return
            px = self._base_x0 + float(x_cm) * self._escala_pixel
            py = (self._base_y0 + self._base_h_px) - (float(y_cm) * self._escala_pixel)
            r = 3.5  #sharp small dot
            c.create_oval(
                px - r, py - r, px + r, py + r,
                fill="#22C55E", outline="#15803D", width=1.0,
                tags="puntero_laser"
            )
            c.tag_raise("puntero_laser")
        except Exception:
            pass

    def mostrar_frame_dxf(self, bbox_cm: Optional[Tuple[float, float, float, float]] = None):
        """compute and display dxf bounding box framing overlay"""
        if bbox_cm is not None:
            self.frame_box_cm = bbox_cm
            self._dibujar_frame_dxf(self.canvas)
            return

    def _dibujar_frame_dxf(self, c: tk.Canvas):
        """draw dxf bounding box framing in dashed orange"""
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

            #closed bounding box coordinates
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
        """hide dxf framing box"""
        self.frame_box_cm = None
        try:
            self.canvas.delete("frame_dxf")
        except Exception:
            pass

    def actualizar_frustum_zoom(self, bbox_cm: Optional[Tuple[float, float, float, float]]):
        """update zoom camera frustum box overlay"""
        self._frustum_zoom_cm = bbox_cm
        self._dibujar_frustum_zoom(self.canvas)

    def ocultar_frustum_zoom(self):
        """hide zoom camera frustum box"""
        self._frustum_zoom_cm = None
        try:
            self.canvas.delete("frustum_zoom_cam")
        except Exception:
            pass

    def _dibujar_frustum_zoom(self, c: tk.Canvas):
        """render zoom camera green dashed rectangle on canvas"""
        if getattr(self, "_frustum_zoom_cm", None) is None:
            try:
                c.delete("frustum_zoom_cam")
            except Exception:
                pass
            return
        if not hasattr(self, '_escala_pixel') or self._escala_pixel is None:
            return

        try:
            c.delete("frustum_zoom_cam")
            min_x, max_x, min_y, max_y = self._frustum_zoom_cm

            def to_px(x_cm, y_cm):
                px = self._base_x0 + float(x_cm) * self._escala_pixel
                py = (self._base_y0 + self._base_h_px) - (float(y_cm) * self._escala_pixel)
                return px, py

            px1, py1 = to_px(min_x, min_y)
            px2, py2 = to_px(max_x, max_y)

            coords = [px1, py1, px2, py1, px2, py2, px1, py2, px1, py1]
            c.create_line(
                coords,
                fill="#22C55E",
                width=2.5,
                dash=(5, 4),
                capstyle="round",
                joinstyle="round",
                tags="frustum_zoom_cam"
            )
            c.tag_raise("frustum_zoom_cam")
            if getattr(self, "pos_puntero", None) is not None:
                c.tag_raise("puntero_laser")
        except Exception:
            pass

    def archivar_pasada_completada(self):
        """convert completed pass segments to translucent previous layer"""
        c = getattr(self, "canvas", None)
        if c:
            try:
                c.itemconfig("completado", fill=COLOR_BLUE_FADED, width=2.5, tags="pasada_previa")
                c.tag_lower("pasada_previa", "completado")
                if getattr(self, "pos_puntero", None) is not None:
                    c.tag_raise("puntero_laser")
            except Exception:
                pass
        if self.trazos_completados:
            self.trazos_pasadas_previas.extend(self.trazos_completados)
            self.trazos_completados = []

    def limpiar_completados(self):
        """clear all completed segments from canvas and memory"""
        self.trazos_completados = []
        self.trazos_pasadas_previas = []
        self.limpiar_feedback()
        try:
            self.canvas.delete("completado")
            self.canvas.delete("pasada_previa")
        except Exception:
            pass

    #hardware feedback tracking layer
    def set_feedback_visible(self, visible: bool):
        """toggle visibility of measured feedback layer in legend"""
        self._fb_visible = bool(visible)
        try:
            if visible:
                if not self.sep_legend_fb.winfo_ismapped():
                    self.sep_legend_fb.pack(side="left", padx=3, pady=4)
                    self.box_legend_fb.pack(side="left", padx=(4, 4), pady=2)
                if hasattr(self, "row_pop_fb") and not self.row_pop_fb.winfo_ismapped():
                    self.row_pop_fb.pack(fill="x", padx=8, pady=(3, 6))
            else:
                self.sep_legend_fb.pack_forget()
                self.box_legend_fb.pack_forget()
                if hasattr(self, "row_pop_fb"):
                    self.row_pop_fb.pack_forget()
                self.limpiar_feedback()
        except Exception:
            pass

    def limpiar_feedback(self):
        """clear measured feedback trajectory from canvas and memory"""
        self._fb_pts_cm = []
        try:
            self.canvas.delete("fb_trace")
        except Exception:
            pass

    def agregar_puntos_feedback(self, puntos_cm: List[Tuple[float, float]]):
        """append measured feedback points and draw incremental segments"""
        c = self.canvas
        if not hasattr(self, '_escala_pixel') or self._escala_pixel is None:
            return

        def to_px(x_cm, y_cm):
            return (self._base_x0 + float(x_cm) * self._escala_pixel,
                    (self._base_y0 + self._base_h_px) - (float(y_cm) * self._escala_pixel))

        try:
            for p in puntos_cm:
                if not self._fb_pts_cm:
                    self._fb_pts_cm.append(p)
                    continue
                px1, py1 = to_px(*self._fb_pts_cm[-1])
                px2, py2 = to_px(*p)
                if (px2 - px1) ** 2 + (py2 - py1) ** 2 < 1.0:
                    continue  #decimate to at least 1px
                c.create_line(px1, py1, px2, py2, fill="#D946EF", width=2.0,
                              capstyle="round", tags="fb_trace")
                self._fb_pts_cm.append(p)
            if len(self._fb_pts_cm) > 200000:
                del self._fb_pts_cm[: len(self._fb_pts_cm) - 200000]
            c.tag_raise("fb_trace")
            if getattr(self, "pos_puntero", None) is not None:
                c.tag_raise("puntero_laser")
        except Exception:
            pass

    def _redibujar_feedback_completo(self, c: tk.Canvas):
        """redraw full measured feedback layer after canvas resize"""
        if not hasattr(self, '_escala_pixel') or self._escala_pixel is None:
            return
        try:
            c.delete("fb_trace")
            coords = []
            for x_cm, y_cm in self._fb_pts_cm:
                coords.extend([
                    self._base_x0 + float(x_cm) * self._escala_pixel,
                    (self._base_y0 + self._base_h_px) - (float(y_cm) * self._escala_pixel),
                ])
            if len(coords) >= 4:
                c.create_line(coords, fill="#D946EF", width=2.0, capstyle="round",
                              joinstyle="round", tags="fb_trace")
                c.tag_raise("fb_trace")
                if getattr(self, "pos_puntero", None) is not None:
                    c.tag_raise("puntero_laser")
        except Exception:
            pass

    def agregar_segmento_completado(
        self, p1: Tuple[float, float], p2: Tuple[float, float], forzar: bool = False
    ) -> bool:
        """draw single incremental completed segment without full canvas redraw"""
        c = self.canvas
        if not hasattr(self, '_escala_pixel') or self._escala_pixel is None:
            return False  #canvas not initialized
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
            self.trazos_completados.append((p1, p2))
            if getattr(self, "pos_puntero", None) is not None:
                c.tag_raise("puntero_laser")
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
            if len(ticks) > 100:  #guard against infinite loop
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

        #visible base rectangle
        c.create_rectangle(
            x0, y0, x1, y1,
            outline="#94A3B8", width=1.5, dash=(6, 4)
        )

        #generate metric ticks
        ticks_y = self._calcular_ticks(self.alto_base_cm)
        ticks_x = self._calcular_ticks(self.ancho_base_cm)

        #y axis ticks labels and internal grid
        rango_y = max(0.1, self.alto_base_cm)
        for val_y in ticks_y:
            y_pos = y1 - (val_y / rango_y) * h_px
            #internal metric grid
            c.create_line(x0, y_pos, x1, y_pos, fill=COLOR_GRID, width=1)
            #left tick
            c.create_line(x0 - 5, y_pos, x0, y_pos, fill=COLOR_BORDER, width=1.5)
            #numeric label
            texto_y = f"{int(val_y)}" if abs(val_y - round(val_y)) < 1e-4 else f"{val_y:.1f}"
            c.create_text(x0 - 8, y_pos, text=texto_y, font=(FONT_TEACHERS, 9), fill=COLOR_TEXT, anchor="e")

        #x axis ticks labels and internal grid
        rango_x = max(0.1, self.ancho_base_cm)
        for val_x in ticks_x:
            x_pos = x0 + (val_x / rango_x) * w_px
            #internal metric grid
            c.create_line(x_pos, y0, x_pos, y1, fill=COLOR_GRID, width=1)
            #bottom tick
            c.create_line(x_pos, y1, x_pos, y1 + 5, fill=COLOR_BORDER, width=1.5)
            #numeric label
            texto_x = f"{int(val_x)}" if abs(val_x - round(val_x)) < 1e-4 else f"{val_x:.1f}"
            c.create_text(x_pos, y1 + 7, text=texto_x, font=(FONT_TEACHERS, 9), fill=COLOR_TEXT, anchor="n")

        #main solid axes
        c.create_line(x0, y0, x0, y1, fill=COLOR_BORDER, width=BRUTAL_BORDER)  #y axis
        c.create_line(x0, y1, x1, y1, fill=COLOR_BORDER, width=BRUTAL_BORDER)  #x axis

        #axis labels
        c.create_text(x0 - 4, y0 - 8, text="Y [cm]", font=(FONT_TEACHERS, 9, "bold"), fill=COLOR_TEXT, anchor="sw")
        c.create_text(x1 + 6, y1, text="X [cm]", font=(FONT_TEACHERS, 9, "bold"), fill=COLOR_TEXT, anchor="w")

    #responsive legend and popover
    def _crear_popup_leyenda(self):
        """create popover card with detailed toolpath guide"""
        self.legend_popup = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            width=280
        )

        #popover card header
        header_pop = ctk.CTkFrame(self.legend_popup, fg_color="#F1F5F9", corner_radius=BRUTAL_CORNER, height=28)
        header_pop.pack(fill="x", padx=4, pady=(4, 4))

        self.lbl_popup_title = ctk.CTkLabel(
            header_pop,
            text=f"ℹ {tr('legend_popup_title')}",
            font=ctk.CTkFont(family=FONT_TEACHERS, size=11, weight="bold"),
            text_color=COLOR_TEXT
        )
        self.lbl_popup_title.pack(side="left", padx=6)

        btn_close_pop = ctk.CTkButton(
            header_pop,
            text="✕",
            width=20,
            height=20,
            command=self._cerrar_popup_leyenda,
            fg_color="transparent",
            text_color=COLOR_MUTED,
            hover_color="#E2E8F0",
            font=ctk.CTkFont(family=FONT_SEGOE, size=11, weight="bold")
        )
        btn_close_pop.pack(side="right", padx=2)

        #cad guide
        row1 = ctk.CTkFrame(self.legend_popup, fg_color="transparent")
        row1.pack(fill="x", padx=8, pady=3)
        c1 = tk.Canvas(row1, width=22, height=18, bg=COLOR_CARD, highlightthickness=0)
        c1.pack(side="left", padx=(0, 6))
        c1.create_line(2, 9, 20, 9, fill=COLOR_VECTOR_GRAY, width=2.5, capstyle="round")
        t1 = ctk.CTkFrame(row1, fg_color="transparent")
        t1.pack(side="left", fill="x", expand=True)
        self.lbl_pop_guide = ctk.CTkLabel(t1, text=tr("legend_guide"), font=self.f_leg, text_color=COLOR_TEXT, anchor="w")
        self.lbl_pop_guide.pack(anchor="w")
        self.lbl_pop_guide_desc = ctk.CTkLabel(t1, text=tr("legend_guide_desc"), font=self.f_sub_leg, text_color=COLOR_MUTED, anchor="w")
        self.lbl_pop_guide_desc.pack(anchor="w")

        #rapid traverse jump
        row2 = ctk.CTkFrame(self.legend_popup, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=3)
        c2 = tk.Canvas(row2, width=22, height=18, bg=COLOR_CARD, highlightthickness=0)
        c2.pack(side="left", padx=(0, 6))
        for bx in (4.0, 11.0, 18.0):
            c2.create_oval(bx - 2.5, 9.0 - 2.5, bx + 2.5, 9.0 + 2.5, fill=COLOR_ORANGE, outline="")
        t2 = ctk.CTkFrame(row2, fg_color="transparent")
        t2.pack(side="left", fill="x", expand=True)
        self.lbl_pop_jump = ctk.CTkLabel(t2, text=tr("legend_jump"), font=self.f_leg, text_color=COLOR_TEXT, anchor="w")
        self.lbl_pop_jump.pack(anchor="w")
        self.lbl_pop_jump_desc = ctk.CTkLabel(t2, text=tr("legend_jump_desc"), font=self.f_sub_leg, text_color=COLOR_MUTED, anchor="w")
        self.lbl_pop_jump_desc.pack(anchor="w")

        #active executed toolpath
        row3 = ctk.CTkFrame(self.legend_popup, fg_color="transparent")
        row3.pack(fill="x", padx=8, pady=3)
        c3 = tk.Canvas(row3, width=22, height=18, bg=COLOR_CARD, highlightthickness=0)
        c3.pack(side="left", padx=(0, 6))
        c3.create_line(2, 9, 20, 9, fill=COLOR_BLUE, width=3.5, capstyle="round")
        t3 = ctk.CTkFrame(row3, fg_color="transparent")
        t3.pack(side="left", fill="x", expand=True)
        self.lbl_pop_trail = ctk.CTkLabel(t3, text=tr("legend_trace"), font=self.f_leg, text_color=COLOR_TEXT, anchor="w")
        self.lbl_pop_trail.pack(anchor="w")
        self.lbl_pop_trail_desc = ctk.CTkLabel(t3, text=tr("legend_trace_desc"), font=self.f_sub_leg, text_color=COLOR_MUTED, anchor="w")
        self.lbl_pop_trail_desc.pack(anchor="w")

        #laser pointer
        row4 = ctk.CTkFrame(self.legend_popup, fg_color="transparent")
        row4.pack(fill="x", padx=8, pady=(3, 6))
        c4 = tk.Canvas(row4, width=22, height=18, bg=COLOR_CARD, highlightthickness=0)
        c4.pack(side="left", padx=(0, 6))
        c4.create_oval(7, 5, 15, 13, fill="#22C55E", outline="#15803D", width=1.0)
        t4 = ctk.CTkFrame(row4, fg_color="transparent")
        t4.pack(side="left", fill="x", expand=True)
        self.lbl_pop_pointer = ctk.CTkLabel(t4, text=tr("legend_pointer"), font=self.f_leg, text_color=COLOR_TEXT, anchor="w")
        self.lbl_pop_pointer.pack(anchor="w")
        self.lbl_pop_pointer_desc = ctk.CTkLabel(t4, text=tr("legend_pointer_desc"), font=self.f_sub_leg, text_color=COLOR_MUTED, anchor="w")
        self.lbl_pop_pointer_desc.pack(anchor="w")

        #measured feedback trajectory
        self.row_pop_fb = ctk.CTkFrame(self.legend_popup, fg_color="transparent")
        c5 = tk.Canvas(self.row_pop_fb, width=22, height=18, bg=COLOR_CARD, highlightthickness=0)
        c5.pack(side="left", padx=(0, 6))
        c5.create_line(2, 9, 20, 9, fill="#D946EF", width=3.0, capstyle="round")
        t5 = ctk.CTkFrame(self.row_pop_fb, fg_color="transparent")
        t5.pack(side="left", fill="x", expand=True)
        self.lbl_pop_fb = ctk.CTkLabel(t5, text=tr("legend_measured"), font=self.f_leg, text_color=COLOR_TEXT, anchor="w")
        self.lbl_pop_fb.pack(anchor="w")
        self.lbl_pop_fb_desc = ctk.CTkLabel(t5, text=tr("legend_measured_desc"), font=self.f_sub_leg, text_color=COLOR_MUTED, anchor="w")
        self.lbl_pop_fb_desc.pack(anchor="w")

    def _toggle_popup_leyenda(self):
        """toggle floating toolpath guide popup"""
        if getattr(self, "_popup_abierto", False):
            self._cerrar_popup_leyenda()
        else:
            self._abrir_popup_leyenda()

    def _abrir_popup_leyenda(self):
        self._popup_abierto = True
        self.legend_popup.place(relx=1.0, x=-2, y=34, anchor="ne")
        try:
            self.legend_popup.lift()
        except Exception:
            pass
        if hasattr(self, "btn_legend_toggle"):
            self.btn_legend_toggle.configure(
                fg_color=COLOR_YELLOW,
                text=f"{tr('legend_btn_guide')}"
            )

    def _cerrar_popup_leyenda(self):
        self._popup_abierto = False
        if hasattr(self, "legend_popup"):
            self.legend_popup.place_forget()
        if hasattr(self, "btn_legend_toggle"):
            self.btn_legend_toggle.configure(
                fg_color=COLOR_CARD,
                text=f"{tr('legend_btn_guide')}"
            )

    def _on_header_configure(self, event):
        ancho = event.width
        if ancho <= 50:
            return
        self._ajustar_modo_leyenda(ancho)

    def _ajustar_modo_leyenda(self, ancho: int):
        #threshold where title and horizontal legend collide
        limite = 780
        if ancho < limite:
            if not getattr(self, "_modo_compacto_leyenda", False):
                self._modo_compacto_leyenda = True
                self.legend_frame.pack_forget()
                self.btn_legend_toggle.pack(side="right")
        else:
            if getattr(self, "_modo_compacto_leyenda", False):
                self._modo_compacto_leyenda = False
                self._cerrar_popup_leyenda()
                self.btn_legend_toggle.pack_forget()
                self.legend_frame.pack(side="right")

    def actualizar_idioma(self):
        """update central panel titles legends and tooltips on language change"""
        if hasattr(self, "lbl_title"):
            self.lbl_title.configure(text=tr("canvas_title"))
        if hasattr(self, "lbl_legend_guide"):
            self.lbl_legend_guide.configure(text=tr("legend_guide"))
        if hasattr(self, "lbl_legend_jump"):
            self.lbl_legend_jump.configure(text=tr("legend_jump"))
        if hasattr(self, "lbl_legend_trail"):
            self.lbl_legend_trail.configure(text=tr("legend_trace"))
        if hasattr(self, "lbl_legend_pointer"):
            self.lbl_legend_pointer.configure(text=tr("legend_pointer"))

        if hasattr(self, "btn_legend_toggle"):
            self.btn_legend_toggle.configure(text=f"{tr('legend_btn_guide')}")
            agregar_tooltip(self.btn_legend_toggle, tr("legend_btn_tooltip"))

        if hasattr(self, "lbl_popup_title"):
            self.lbl_popup_title.configure(text=f"ℹ {tr('legend_popup_title')}")
        if hasattr(self, "lbl_pop_guide"):
            self.lbl_pop_guide.configure(text=tr("legend_guide"))
        if hasattr(self, "lbl_pop_guide_desc"):
            self.lbl_pop_guide_desc.configure(text=tr("legend_guide_desc"))
        if hasattr(self, "lbl_pop_jump"):
            self.lbl_pop_jump.configure(text=tr("legend_jump"))
        if hasattr(self, "lbl_pop_jump_desc"):
            self.lbl_pop_jump_desc.configure(text=tr("legend_jump_desc"))
        if hasattr(self, "lbl_pop_trail"):
            self.lbl_pop_trail.configure(text=tr("legend_trace"))
        if hasattr(self, "lbl_pop_trail_desc"):
            self.lbl_pop_trail_desc.configure(text=tr("legend_trace_desc"))
        if hasattr(self, "lbl_pop_pointer"):
            self.lbl_pop_pointer.configure(text=tr("legend_pointer"))
        if hasattr(self, "lbl_pop_pointer_desc"):
            self.lbl_pop_pointer_desc.configure(text=tr("legend_pointer_desc"))
        if hasattr(self, "lbl_legend_fb"):
            self.lbl_legend_fb.configure(text=tr("legend_measured"))
        if hasattr(self, "lbl_pop_fb"):
            self.lbl_pop_fb.configure(text=tr("legend_measured"))
        if hasattr(self, "lbl_pop_fb_desc"):
            self.lbl_pop_fb_desc.configure(text=tr("legend_measured_desc"))

        if hasattr(self, "lbl_area"):
            self.lbl_area.configure(text=f"{tr('base_dim_title')}:")

        if hasattr(self, "legend_frame"):
            agregar_tooltip(
                self.legend_frame,
                "Toolpath line guide:\n"
                "• Gray: Target CAD geometry\n"
                "• Dashed Orange: Rapid traverse without laser\n"
                "• Blue: Laser-processed toolpath\n"
                "• Green dot: Real-time beam / cursor position"
                if obtener_idioma() == "EN" else
                "Vodítko drah nástroje:\n"
                "• Šedá: Cílová CAD geometrie\n"
                "• Oranžová přerušovaná: Rychlý přejezd bez laseru\n"
                "• Modrá: Vypálená dráha laseru\n"
                "• Zelený bod: Reálná poloha paprsku / kurzor"
            )
        if hasattr(self, "pill_x"):
            agregar_tooltip(
                self.pill_x,
                "Width (X axis) of the physical base or workpiece, in centimeters.\n"
                "Defines the canvas scale and drawing placement area. Press Enter to apply."
                if obtener_idioma() == "EN" else
                "Šířka (osa X) fyzické základny nebo obrobku v centimetrech.\n"
                "Definuje měřítko plátna a oblast umístění kresby. Stiskněte Enter pro použití."
            )
        if hasattr(self, "pill_y"):
            agregar_tooltip(
                self.pill_y,
                "Height (Y axis) of the physical base or workpiece, in centimeters.\n"
                "Defines the canvas scale and drawing placement area. Press Enter to apply."
                if obtener_idioma() == "EN" else
                "Výška (osa Y) fyzické základny nebo obrobku v centimetrech.\n"
                "Definuje měřítko plátna a oblast umístění kresby. Stiskněte Enter pro použití."
            )

