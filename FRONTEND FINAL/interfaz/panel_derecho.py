# -*- coding: utf-8 -*-
"""right panel gauges trace point and execution controls"""

import math
import tkinter as tk
import customtkinter as ctk
from typing import Callable, List, Optional, Tuple

from .constantes import (
    COLOR_CARD, COLOR_BORDER, COLOR_TEXT,
    COLOR_YELLOW, COLOR_RED, COLOR_BLUE, COLOR_BLUE_FADED, COLOR_GREEN, COLOR_ORANGE,
    COLOR_PAUSE, COLOR_TIMER_BG, COLOR_BOX_BG, COLOR_MUTED,
    COLOR_VECTOR_GRAY,
    FONT_BRUNO, FONT_TEACHERS, FONT_CONSOLAS, FONT_SEGOE,
    BRUTAL_CORNER, BRUTAL_BORDER, BRUTAL_BORDER_THICK,
    agregar_tooltip
)
from .i18n import tr, registrar_observador


class PanelDerecho(ctk.CTkFrame):
    """right lateral panel telemetry dmm gauges laser tracking and execution controls"""

    def __init__(
        self,
        master,
        on_click_start: Optional[Callable[[], None]] = None,
        on_click_pause_resume: Optional[Callable[[], None]] = None,
        on_click_stop: Optional[Callable[[], None]] = None,
        on_centro_cambiado: Optional[Callable[[float, float], None]] = None,
        on_viewport_cambiado: Optional[Callable[[Optional[Tuple[float, float, float, float]]], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_click_start = on_click_start
        self.on_click_pause_resume = on_click_pause_resume
        self.on_click_stop = on_click_stop
        self.on_centro_cambiado = on_centro_cambiado
        self.on_viewport_cambiado = on_viewport_cambiado

        self.f_head = ctk.CTkFont(family=FONT_TEACHERS, size=12, weight="bold")
        self.f_bold = ctk.CTkFont(family=FONT_TEACHERS, size=11, weight="bold")
        self.f_regular = ctk.CTkFont(family=FONT_TEACHERS, size=11)
        self.f_bruno_btn = ctk.CTkFont(family=FONT_BRUNO, size=13, weight="bold")
        self.f_bruno_timer = ctk.CTkFont(family=FONT_BRUNO, size=16, weight="bold")
        self.f_dmm_lbl = ctk.CTkFont(family=FONT_SEGOE, size=9, weight="bold")
        self.f_dmm_val = ctk.CTkFont(family=FONT_CONSOLAS, size=15, weight="bold")
        self.f_pill = ctk.CTkFont(family=FONT_CONSOLAS, size=11, weight="bold")

        self.trazos_actuales: List[List[Tuple[float, float]]] = []
        self.trazos_completados: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        self.trazos_pasadas_previas: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        self._trazos_bboxes: Optional[List[Tuple[float, float, float, float]]] = None
        self.centro_home = (19.35, 19.75)
        self.pos_laser_actual = (19.35, 19.75)
        self._ultimo_estado = "READY"

        #free navigation and tracking camera mode
        self.modo_auto_centrado = True
        self.centro_camara_cm = (19.35, 19.75)
        self._pan_iniciado = False
        self._pan_arrastrando = False
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._pan_cam_start = (19.35, 19.75)

        self.pct_trace = 0.0
        self.pct_total = 0.0

        #laser tracking relative zoom factor
        self.zoom_niveles = [4, 6, 8, 10, 12, 16, 20, 30]
        self.zoom_relativo = 8
        self.escala_referencia_px_cm = 20.0
        self.ancla_vivo: Optional[Tuple[float, float]] = None

        self._crear_widgets()
        registrar_observador(self.actualizar_idioma)


    def _crear_widgets(self):
        #execution control panel
        self.frame_controles = ctk.CTkFrame(self, fg_color="transparent", height=46)
        self.frame_controles.pack(side="bottom", fill="x", pady=(4, 0))
        self.frame_controles.pack_propagate(False)

        #home button
        self.btn_home = ctk.CTkButton(
            self.frame_controles,
            text="✛",
            command=self.toggle_home_card,
            fg_color=COLOR_CARD,
            text_color=COLOR_TEXT,
            hover_color=COLOR_YELLOW,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            font=ctk.CTkFont(size=20, weight="bold"),
            width=44,
            height=42
        )
        self.btn_home.pack(side="left", padx=(0, 6))
        agregar_tooltip(self.btn_home, tr("btn_home_tooltip"))

        #dynamic action container
        self.action_box = ctk.CTkFrame(self.frame_controles, fg_color="transparent")
        self.action_box.pack(side="left", fill="both", expand=True)

        #start button
        self.btn_start = ctk.CTkButton(
            self.action_box,
            text=tr("btn_start"),
            command=self._cb_start,
            fg_color=COLOR_YELLOW,
            text_color=COLOR_TEXT,
            hover_color="#E09612",
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bruno_btn,
            height=42
        )
        self.btn_start.pack(fill="both", expand=True)
        agregar_tooltip(self.btn_start, "Start vector laser scanning with current recipe parameters.")

        #running mode widgets
        self.running_box = ctk.CTkFrame(self.action_box, fg_color="transparent")

        self.btn_pause_resume = ctk.CTkButton(
            self.running_box,
            text=tr("btn_pause"),
            command=self._cb_pause_resume,
            fg_color=COLOR_PAUSE,
            text_color=COLOR_TEXT,
            hover_color="#CBD5E1",
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            font=ctk.CTkFont(family=FONT_BRUNO, size=11, weight="bold"),
            width=82,
            height=42
        )
        self.btn_pause_resume.pack(side="left", padx=(0, 6))
        self.tooltip_pause = agregar_tooltip(self.btn_pause_resume, tr("btn_pause_tooltip"))

        #emergency stop button
        self.btn_stop = ctk.CTkButton(
            self.running_box,
            text=tr("btn_stop"),
            command=self._cb_stop,
            fg_color=COLOR_RED,
            text_color="#FFFFFF",
            hover_color="#B91C1C",
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER_THICK,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bruno_btn,
            width=86,
            height=42
        )
        self.btn_stop.pack(side="left", padx=(0, 6))
        agregar_tooltip(self.btn_stop, "EMERGENCY STOP: aborts scanning immediately and shuts off laser.")

        self.timer_box = ctk.CTkFrame(
            self.running_box,
            fg_color=COLOR_TIMER_BG,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=42
        )
        self.timer_box.pack(side="left", fill="both", expand=True)

        self.lbl_timer = ctk.CTkLabel(
            self.timer_box,
            text="0:00:00",
            font=self.f_bruno_timer,
            text_color=COLOR_TEXT
        )
        self.lbl_timer.place(relx=0.5, rely=0.5, anchor="center")

        #realtime telemetry card
        self.card_telemetria = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER
        )
        self.card_telemetria.pack(side="top", fill="x", pady=(0, 5))

        header_telem = ctk.CTkFrame(self.card_telemetria, fg_color="transparent")
        header_telem.pack(fill="x", padx=8, pady=(6, 2))

        ctk.CTkLabel(
            header_telem,
            text="GALVANOMETER TELEMETRY",
            font=self.f_head,
            text_color=COLOR_TEXT,
            anchor="w"
        ).pack(side="left")

        #system status badge
        self.badge_status = ctk.CTkLabel(
            header_telem,
            text=f"● {tr('status_ready')}",
            font=ctk.CTkFont(family=FONT_SEGOE, size=10, weight="bold"),
            text_color=COLOR_GREEN,
            fg_color="#DCFCE7",
            corner_radius=BRUTAL_CORNER,
            padx=7,
            pady=1
        )
        self.badge_status.pack(side="right")
        agregar_tooltip(self.badge_status, "Current operational state of the scanning workstation.")

        #dmm voltage boxes
        row_dmm = ctk.CTkFrame(self.card_telemetria, fg_color="transparent")
        row_dmm.pack(fill="x", padx=8, pady=(2, 4))

        #dmm x box
        self.box_vx = ctk.CTkFrame(
            row_dmm,
            fg_color=COLOR_BOX_BG,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=46
        )
        self.box_vx.pack(side="left", fill="both", expand=True, padx=(0, 4))
        self.box_vx.pack_propagate(False)

        self.lbl_chan_x = ctk.CTkLabel(
            self.box_vx,
            text=tr("dmm_x"),
            font=self.f_dmm_lbl,
            text_color=COLOR_MUTED
        )
        self.lbl_chan_x.pack(anchor="w", padx=6, pady=(2, 0))

        self.lbl_vx = ctk.CTkLabel(
            self.box_vx,
            text="+0.000 V",
            font=self.f_dmm_val,
            text_color=COLOR_TEXT
        )
        self.lbl_vx.pack(anchor="e", padx=6, pady=(0, 2))
        agregar_tooltip(self.box_vx, "Galvanometer Channel X instantaneous mirror drive voltage: ±0.000 V (-10.0V to +10.0V).\nProportional to optical deflection angle.")

        #dmm y box
        self.box_vy = ctk.CTkFrame(
            row_dmm,
            fg_color=COLOR_BOX_BG,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=46
        )
        self.box_vy.pack(side="right", fill="both", expand=True, padx=(4, 0))
        self.box_vy.pack_propagate(False)

        self.lbl_chan_y = ctk.CTkLabel(
            self.box_vy,
            text=tr("dmm_y"),
            font=self.f_dmm_lbl,
            text_color=COLOR_MUTED
        )
        self.lbl_chan_y.pack(anchor="w", padx=6, pady=(2, 0))

        self.lbl_vy = ctk.CTkLabel(
            self.box_vy,
            text="+0.000 V",
            font=self.f_dmm_val,
            text_color=COLOR_TEXT
        )
        self.lbl_vy.pack(anchor="e", padx=6, pady=(0, 2))
        agregar_tooltip(self.box_vy, "Galvanometer Channel Y instantaneous mirror drive voltage: ±0.000 V (-10.0V to +10.0V).\nProportional to optical deflection angle.")

        #laser emission state pill
        self.pill_laser = ctk.CTkFrame(
            self.card_telemetria,
            fg_color="#E2E8F0",
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=26
        )
        self.pill_laser.pack(fill="x", padx=8, pady=(2, 6))
        self.pill_laser.pack_propagate(False)

        self.lbl_laser_state = ctk.CTkLabel(
            self.pill_laser,
            text="[LASER OFF]",
            font=self.f_pill,
            text_color=COLOR_MUTED
        )
        self.lbl_laser_state.place(relx=0.5, rely=0.5, anchor="center")
        agregar_tooltip(self.pill_laser, "Real-time optical laser emission state:\n[LASER OFF] (rapid jumps) or ⚡ [LASER ACTIVE] (marking).")

        #circular progress gauges
        self.card_gauges = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=116
        )
        self.card_gauges.pack(side="top", fill="x", pady=(0, 5))
        self.card_gauges.pack_propagate(False)

        self.canvas_gauges = tk.Canvas(self.card_gauges, bg=COLOR_CARD, highlightthickness=0, height=112)
        self.canvas_gauges.pack(fill="both", expand=True)
        self.canvas_gauges.bind("<Configure>", lambda e: self.dibujar_gauges())

        #trace point panel with zoom
        self.box_trace = ctk.CTkFrame(self, fg_color="transparent")
        self.box_trace.pack(side="top", fill="both", expand=True, pady=(0, 2))

        header_trace = ctk.CTkFrame(self.box_trace, fg_color="transparent")
        header_trace.pack(side="top", fill="x", pady=(0, 4))

        self.lbl_trace = ctk.CTkLabel(header_trace, text="", font=self.f_head, text_color=COLOR_TEXT, anchor="w")
        self.lbl_trace.pack(side="left")

        self.btn_zoom_mas = ctk.CTkButton(
            header_trace, text="+", width=28, height=22, command=lambda: self._cambiar_zoom(+1),
            fg_color=COLOR_CARD, text_color=COLOR_TEXT, hover_color=COLOR_YELLOW,
            border_color=COLOR_BORDER, border_width=BRUTAL_BORDER, corner_radius=BRUTAL_CORNER,
            font=self.f_bold
        )
        self.btn_zoom_mas.pack(side="right")
        self.btn_zoom_menos = ctk.CTkButton(
            header_trace, text="−", width=28, height=22, command=lambda: self._cambiar_zoom(-1),
            fg_color=COLOR_CARD, text_color=COLOR_TEXT, hover_color=COLOR_YELLOW,
            border_color=COLOR_BORDER, border_width=BRUTAL_BORDER, corner_radius=BRUTAL_CORNER,
            font=self.f_bold
        )
        self.btn_zoom_menos.pack(side="right", padx=(0, 4))
        self.btn_auto_center = ctk.CTkButton(
            header_trace, text="⦾", width=28, height=22, command=self.centrar_en_laser,
            fg_color=COLOR_YELLOW, text_color=COLOR_TEXT, hover_color=COLOR_YELLOW,
            border_color=COLOR_BORDER, border_width=BRUTAL_BORDER, corner_radius=BRUTAL_CORNER,
            font=self.f_bold
        )
        self.btn_auto_center.pack(side="right", padx=(0, 6))
        agregar_tooltip(self.btn_zoom_mas, "Increase laser tracking zoom (higher beam detail).")
        agregar_tooltip(self.btn_zoom_menos, "Decrease laser tracking zoom (wider surrounding area).")
        agregar_tooltip(self.btn_auto_center, tr("btn_auto_center_tooltip"))
        self._actualizar_titulo_zoom()

        self.card_trace = ctk.CTkFrame(
            self.box_trace,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER
        )
        self.card_trace.pack(side="top", fill="both", expand=True)

        self.canvas_trace = tk.Canvas(self.card_trace, bg=COLOR_CARD, highlightthickness=0)
        self.canvas_trace.pack(fill="both", expand=True, padx=4, pady=4)
        self.canvas_trace.bind("<Configure>", lambda e: (self.redibujar_trace(), self._notificar_viewport()))
        self.canvas_trace.bind("<ButtonPress-1>", self._on_pan_start)
        self.canvas_trace.bind("<B1-Motion>", self._on_pan_drag)
        self.canvas_trace.bind("<ButtonRelease-1>", self._on_pan_end)

        #floating coordinate badge
        self.coord_badge = ctk.CTkFrame(
            self.card_trace,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER
        )
        self.coord_badge.place(relx=0.96, rely=0.94, anchor="se")

        self.lbl_coord_live = ctk.CTkLabel(
            self.coord_badge,
            text="x = 19.35 cm  |  y = 19.75 cm",
            font=self.f_bold,
            text_color=COLOR_TEXT,
            padx=10,
            pady=3
        )
        self.lbl_coord_live.pack()

        #home center configuration popup
        self.card_home_popup = ctk.CTkFrame(
            self.winfo_toplevel(),
            fg_color=COLOR_YELLOW,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            width=200,
            height=130
        )

        self.lbl_center_title = ctk.CTkLabel(self.card_home_popup, text=tr("home_title"), font=self.f_bold, text_color=COLOR_TEXT)
        self.lbl_center_title.pack(pady=(6, 4))

        frame_xy = ctk.CTkFrame(self.card_home_popup, fg_color="transparent")
        frame_xy.pack(padx=10, pady=2, fill="x")

        #x row
        row_x = ctk.CTkFrame(frame_xy, fg_color="transparent")
        row_x.pack(fill="x", pady=2)
        ctk.CTkLabel(row_x, text="X:", font=self.f_bold, text_color=COLOR_TEXT, width=20).pack(side="left")
        self.entry_home_x = ctk.CTkEntry(
            row_x,
            width=80,
            height=24,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            text_color=COLOR_TEXT
        )
        self.entry_home_x.insert(0, "19.35")
        self.entry_home_x.pack(side="left", padx=4)
        ctk.CTkLabel(row_x, text="cm", font=self.f_regular, text_color=COLOR_TEXT).pack(side="left")

        #y row
        row_y = ctk.CTkFrame(frame_xy, fg_color="transparent")
        row_y.pack(fill="x", pady=2)
        ctk.CTkLabel(row_y, text="Y:", font=self.f_bold, text_color=COLOR_TEXT, width=20).pack(side="left")
        self.entry_home_y = ctk.CTkEntry(
            row_y,
            width=80,
            height=24,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            text_color=COLOR_TEXT
        )
        self.entry_home_y.insert(0, "19.75")
        self.entry_home_y.pack(side="left", padx=4)
        ctk.CTkLabel(row_y, text="cm", font=self.f_regular, text_color=COLOR_TEXT).pack(side="left")

        #apply button
        self.btn_set_home = ctk.CTkButton(
            self.card_home_popup,
            text=tr("btn_apply"),
            command=self._cb_aplicar_centro,
            fg_color=COLOR_CARD,
            text_color=COLOR_TEXT,
            hover_color="#F1F5F9",
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            height=26
        )
        self.btn_set_home.pack(fill="x", padx=12, pady=(4, 8))

        agregar_tooltip(self.entry_home_x, "X coordinate of resting center (Home), in cm, within base area.")
        agregar_tooltip(self.entry_home_y, "Y coordinate of resting center (Home), in cm, within base area.")
        agregar_tooltip(self.btn_set_home, "Apply center (X, Y): moves resting point and recalculates drawing position.")

    #laser tracking zoom
    def _actualizar_titulo_zoom(self):
        self.lbl_trace.configure(text=f"{tr('view_trace')} (ZOOM {self.zoom_relativo}X)")


    def _cambiar_zoom(self, direccion: int):
        """change relative zoom level and redraw trace"""
        niveles = self.zoom_niveles
        idx = niveles.index(self.zoom_relativo) if self.zoom_relativo in niveles else 0
        idx = max(0, min(len(niveles) - 1, idx + direccion))
        self.zoom_relativo = niveles[idx]
        self._actualizar_titulo_zoom()
        self.redibujar_trace()
        self._notificar_viewport()

    #free navigation pan and drag
    def centrar_en_laser(self):
        """recenter zoom camera on current laser position"""
        self.modo_auto_centrado = True
        self.centro_camara_cm = self.pos_laser_actual
        self._actualizar_estilo_boton_centrado()
        self.redibujar_trace()
        self._notificar_viewport()

    def _actualizar_estilo_boton_centrado(self):
        if hasattr(self, "btn_auto_center"):
            if self.modo_auto_centrado:
                self.btn_auto_center.configure(fg_color=COLOR_YELLOW, hover_color=COLOR_YELLOW)
            else:
                self.btn_auto_center.configure(fg_color=COLOR_CARD, hover_color=COLOR_YELLOW)

    def _on_pan_start(self, event):
        self._pan_iniciado = True
        self._pan_arrastrando = False
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        if self.modo_auto_centrado:
            self._pan_cam_start = self.pos_laser_actual
        else:
            self._pan_cam_start = self.centro_camara_cm
        try:
            self.canvas_trace.configure(cursor="fleur")
        except Exception:
            pass

    def _on_pan_drag(self, event):
        if not getattr(self, "_pan_iniciado", False):
            return
        dx_px = event.x - self._pan_start_x
        dy_px = event.y - self._pan_start_y

        if not self._pan_arrastrando and (abs(dx_px) > 2 or abs(dy_px) > 2):
            self._pan_arrastrando = True
            if self.modo_auto_centrado:
                self.modo_auto_centrado = False
                self._actualizar_estilo_boton_centrado()

        if self._pan_arrastrando:
            zoom_factor = max(1.0, self.escala_referencia_px_cm) * self.zoom_relativo
            #pan drag calculations
            dx_cm = dx_px / zoom_factor
            dy_cm = dy_px / zoom_factor

            c_ini_x, c_ini_y = self._pan_cam_start
            nueva_cam_x = c_ini_x - dx_cm
            nueva_cam_y = c_ini_y + dy_cm
            self.centro_camara_cm = (nueva_cam_x, nueva_cam_y)

            self.redibujar_trace()
            self._notificar_viewport()

    def _on_pan_end(self, event):
        self._pan_iniciado = False
        self._pan_arrastrando = False
        try:
            self.canvas_trace.configure(cursor="")
        except Exception:
            pass

    def _obtener_bbox_camara_cm(self) -> Optional[Tuple[float, float, float, float]]:
        """calculate visible bounding box in physical cm"""
        try:
            w = self.canvas_trace.winfo_width()
            h = self.canvas_trace.winfo_height()
            if w <= 20 or h <= 20:
                return None
            zoom_factor = max(1.0, self.escala_referencia_px_cm) * self.zoom_relativo
            cam_x, cam_y = self.pos_laser_actual if self.modo_auto_centrado else self.centro_camara_cm
            half_w_cm = (w / 2.0) / zoom_factor
            half_h_cm = (h / 2.0) / zoom_factor
            return (cam_x - half_w_cm, cam_x + half_w_cm, cam_y - half_h_cm, cam_y + half_h_cm)
        except Exception:
            return None

    def _notificar_viewport(self):
        """notify external observer of camera viewport"""
        if not self.on_viewport_cambiado:
            return
        if self.modo_auto_centrado:
            self.on_viewport_cambiado(None)
        else:
            self.on_viewport_cambiado(self._obtener_bbox_camara_cm())

    #internal callbacks
    def _cb_start(self):
        if getattr(self, "bloqueado_ejecucion", False):
            return
        if self.on_click_start:
            self.on_click_start()

    def _cb_pause_resume(self):
        if self.on_click_pause_resume:
            self.on_click_pause_resume()

    def _cb_stop(self):
        if self.on_click_stop:
            self.on_click_stop()

    def _cb_aplicar_centro(self):
        if str(self.btn_home.cget("state")) == "disabled":
            return
        try:
            x = float(self.entry_home_x.get().strip())
            y = float(self.entry_home_y.get().strip())
            self.centro_home = (x, y)
            self.pos_laser_actual = (x, y)
            self.actualizar_coordenadas(x, y)
            if self.on_centro_cambiado:
                self.on_centro_cambiado(x, y)
            self.toggle_home_card()
            self.redibujar_trace()
        except ValueError:
            pass

    def set_centro(self, x: float, y: float):
        """update center inputs in popup"""
        try:
            x_val = float(x)
            y_val = float(y)
            self.centro_home = (x_val, y_val)
            self.entry_home_x.delete(0, "end")
            self.entry_home_x.insert(0, f"{x_val:.2f}")
            self.entry_home_y.delete(0, "end")
            self.entry_home_y.insert(0, f"{y_val:.2f}")
            self.actualizar_coordenadas(x_val, y_val)
            if self.modo_auto_centrado:
                self.centro_camara_cm = (x_val, y_val)
            self.redibujar_trace()
            self._notificar_viewport()
        except Exception:
            pass

    def toggle_home_card(self):
        if str(self.btn_home.cget("state")) == "disabled":
            return
        if self.card_home_popup.winfo_ismapped():
            self.card_home_popup.place_forget()
            self.btn_home.configure(fg_color=COLOR_CARD)
        else:
            self.card_home_popup.place(relx=0.76, rely=0.88, anchor="se")
            try:
                self.card_home_popup.lift()
            except Exception:
                pass
            self.btn_home.configure(fg_color=COLOR_YELLOW)

    def set_bloqueo_ejecucion(self, bloqueado: bool):
        """lock or unlock right panel controls during execution"""
        self.bloqueado_ejecucion = bloqueado
        estado = "disabled" if bloqueado else "normal"
        if hasattr(self, "btn_start"):
            self.btn_start.configure(state=estado)
        if hasattr(self, "btn_home"):
            self.btn_home.configure(state=estado)

    #control modes and telemetry states
    def set_modo_running(self):
        self.btn_start.pack_forget()
        self.running_box.pack(fill="both", expand=True)
        self.btn_pause_resume.configure(text=tr("btn_pause"), fg_color=COLOR_PAUSE)
        self.set_estado_sistema("SCANNING")
        #disable home button during execution
        self.btn_home.configure(state="disabled")
        if self.card_home_popup.winfo_ismapped():
            self.card_home_popup.place_forget()
            self.btn_home.configure(fg_color=COLOR_CARD)

    def set_modo_idle(self):
        self.ancla_vivo = None
        self.running_box.pack_forget()
        self.btn_start.pack(fill="both", expand=True)
        self.btn_start.configure(text=tr("btn_start"))
        self.set_estado_sistema("READY")
        self.actualizar_voltajes(0.0, 0.0, False)
        self._esta_pausado = False
        #reactivate home button on idle
        self.btn_home.configure(state="normal")

    def set_estado_pausa(self, pausado: bool):
        self._esta_pausado = pausado
        if pausado:
            self.btn_pause_resume.configure(text=tr("btn_resume"), fg_color=COLOR_YELLOW)
            if hasattr(self, "tooltip_pause") and self.tooltip_pause:
                self.tooltip_pause.texto = tr("btn_resume_tooltip")
            self.set_estado_sistema("PAUSED")
            self.set_laser_activo(False)
        else:
            self.btn_pause_resume.configure(text=tr("btn_pause"), fg_color=COLOR_PAUSE)
            if hasattr(self, "tooltip_pause") and self.tooltip_pause:
                self.tooltip_pause.texto = tr("btn_pause_tooltip")
            self.set_estado_sistema("SCANNING")

    def set_estado_sistema(self, estado: str):
        try:
            self._ultimo_estado = str(estado)
            estado_up = str(estado).upper()
            if estado_up in ("IDLE", "READY"):
                self.badge_status.configure(text=f"● {tr('status_ready')}", text_color=COLOR_GREEN, fg_color="#DCFCE7")
            elif estado_up in ("RUNNING", "SCANNING"):
                self.badge_status.configure(text=f"● {tr('status_executing')}", text_color="#B45309", fg_color="#FEF3C7")
            elif estado_up in ("PAUSED",):
                self.badge_status.configure(text=f"● {tr('status_paused')}", text_color="#D97706", fg_color="#FEF08A")
            elif estado_up in ("STOPPED", "ABORTED"):
                self.badge_status.configure(text=f"● {tr('status_stopped')}", text_color=COLOR_RED, fg_color="#FEE2E2")
            elif estado_up in ("COMPLETED",):
                self.badge_status.configure(text=f"● {tr('status_completed')}", text_color=COLOR_GREEN, fg_color="#DCFCE7")
            else:
                self.badge_status.configure(text=f"● {estado_up}", text_color=COLOR_MUTED, fg_color="#F1F5F9")
        except Exception:
            pass

    def actualizar_voltajes(self, vx: float, vy: float, laser_on: bool = False):
        try:
            vx_val = float(vx) if vx is not None and not (math.isnan(vx) or math.isinf(vx)) else 0.0
            vy_val = float(vy) if vy is not None and not (math.isnan(vy) or math.isinf(vy)) else 0.0
            self.lbl_vx.configure(text=f"{vx_val:+.3f} V")
            self.lbl_vy.configure(text=f"{vy_val:+.3f} V")
            self.set_laser_activo(bool(laser_on))
        except Exception:
            pass

    def set_laser_activo(self, activo: bool):
        try:
            if activo:
                self.pill_laser.configure(fg_color="#FEF3C7", border_color=COLOR_YELLOW)
                self.lbl_laser_state.configure(text="⚡ [LASER ACTIVE]", text_color="#B45309")
            else:
                self.pill_laser.configure(fg_color="#E2E8F0", border_color=COLOR_BORDER)
                self.lbl_laser_state.configure(text="[LASER OFF]", text_color=COLOR_MUTED)
        except Exception:
            pass

    def actualizar_timer(self, texto: str):
        try:
            self.lbl_timer.configure(text=str(texto or "0:00:00"))
        except Exception:
            pass

    def actualizar_coordenadas(self, x: float, y: float):
        try:
            x_val = float(x) if x is not None and not (math.isnan(x) or math.isinf(x)) else 0.0
            y_val = float(y) if y is not None and not (math.isnan(y) or math.isinf(y)) else 0.0
            self.pos_laser_actual = (x_val, y_val)
            self.lbl_coord_live.configure(text=f"x = {x_val:.2f} cm  |  y = {y_val:.2f} cm")
        except Exception:
            pass

    #gauge rendering
    def dibujar_gauges(self, pct_trace: Optional[float] = None, pct_total: Optional[float] = None):
        if pct_trace is not None:
            try:
                self.pct_trace = float(pct_trace) if not (math.isnan(pct_trace) or math.isinf(pct_trace)) else 0.0
            except Exception:
                self.pct_trace = 0.0
        if pct_total is not None:
            try:
                self.pct_total = float(pct_total) if not (math.isnan(pct_total) or math.isinf(pct_total)) else 0.0
            except Exception:
                self.pct_total = 0.0

        c = self.canvas_gauges
        try:
            c.delete("all")

            w = c.winfo_width()
            h = c.winfo_height()
            if w <= 50 or h <= 50:
                return

            r = 34
            grosor = 9

            c1_x = w * 0.28
            c1_y = h * 0.54
            self._dibujar_un_gauge(c, c1_x, c1_y, r, grosor, self.pct_trace, tr("gauge_trace"))

            c2_x = w * 0.72
            c2_y = h * 0.54
            self._dibujar_un_gauge(c, c2_x, c2_y, r, grosor, self.pct_total, tr("gauge_total"))
        except Exception:
            pass

    def _dibujar_un_gauge(self, c: tk.Canvas, cx: float, cy: float, r: float, grosor: float, pct: float, titulo: str):
        pct_clean = max(0.0, min(100.0, float(pct)))
        c.create_text(cx, cy - r - 9, text=titulo, font=(FONT_TEACHERS, 10, "bold"), fill=COLOR_TEXT)
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=COLOR_BORDER, width=BRUTAL_BORDER)

        grados_arco = -(pct_clean / 100.0) * 360.0
        if pct_clean > 0:
            c.create_arc(
                cx - r + grosor / 2, cy - r + grosor / 2,
                cx + r - grosor / 2, cy + r - grosor / 2,
                start=90,
                extent=grados_arco,
                style="arc",
                outline=COLOR_BLUE,
                width=grosor
            )

        c.create_text(cx, cy, text=f"{int(round(pct_clean))} %", font=(FONT_TEACHERS, 11, "bold"), fill=COLOR_TEXT)

    def archivar_pasada_completada(self):
        """archive finished pass traces into translucent layer"""
        if self.trazos_completados:
            self.trazos_pasadas_previas.extend(self.trazos_completados)
            self.trazos_completados = []

    def limpiar_progreso(self):
        """reset completed segments anchors and progress gauges"""
        self.trazos_completados = []
        self.trazos_pasadas_previas = []
        self.ancla_vivo = None
        self.pct_trace = 0.0
        self.pct_total = 0.0
        self.actualizar_voltajes(0.0, 0.0, False)
        self.dibujar_gauges(0.0, 0.0)
        self.centrar_en_laser()

    #trace point canvas rendering
    def redibujar_trace(
        self,
        trazos: Optional[List[List[Tuple[float, float]]]] = None,
        trazos_completados: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None,
        pos_laser: Optional[Tuple[float, float]] = None,
        trazos_pasadas_previas: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None
    ):
        try:
            if trazos is not None:
                if self.trazos_actuales is not trazos:
                    self.trazos_actuales = trazos
                    self._trazos_bboxes = None

            if trazos_completados is not None:
                self.trazos_completados = list(trazos_completados)
            if trazos_pasadas_previas is not None:
                self.trazos_pasadas_previas = list(trazos_pasadas_previas)
            if pos_laser is not None:
                self.pos_laser_actual = pos_laser

            c = self.canvas_trace
            c.delete("all")

            w = c.winfo_width()
            h = c.winfo_height()
            if w <= 20 or h <= 20:
                return

            cx = w / 2.0
            cy = h / 2.0

            if self.modo_auto_centrado:
                cam_x, cam_y = self.pos_laser_actual
                self.centro_camara_cm = (cam_x, cam_y)
            else:
                cam_x, cam_y = self.centro_camara_cm

            zoom_factor = max(1.0, self.escala_referencia_px_cm) * self.zoom_relativo

            margin_cm = (max(w, h) / 2.0) / zoom_factor + 0.8
            min_x = cam_x - margin_cm
            max_x = cam_x + margin_cm
            min_y = cam_y - margin_cm
            max_y = cam_y + margin_cm

            if self.trazos_actuales:
                if self._trazos_bboxes is None or len(self._trazos_bboxes) != len(self.trazos_actuales):
                    bboxes = []
                    for r in self.trazos_actuales:
                        if r and len(r) >= 2:
                            try:
                                xs = [p[0] for p in r if len(p) >= 2]
                                ys = [p[1] for p in r if len(p) >= 2]
                                if xs and ys:
                                    bboxes.append((min(xs), max(xs), min(ys), max(ys)))
                                else:
                                    bboxes.append((0.0, 0.0, 0.0, 0.0))
                            except Exception:
                                bboxes.append((0.0, 0.0, 0.0, 0.0))
                        elif r and len(r) == 1:
                            p = r[0]
                            bboxes.append((p[0], p[0], p[1], p[1]))
                        else:
                            bboxes.append((0.0, 0.0, 0.0, 0.0))
                    self._trazos_bboxes = bboxes

                #rapid jump g0 lines
                hx, hy = getattr(self, "centro_home", (19.35, 19.75))
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

                for p_fin, p_ini in viajes:
                    if not p_fin or not p_ini or len(p_fin) < 2 or len(p_ini) < 2:
                        continue
                    if (p_fin[0] < min_x and p_ini[0] < min_x) or (p_fin[0] > max_x and p_ini[0] > max_x) or \
                       (p_fin[1] < min_y and p_ini[1] < min_y) or (p_fin[1] > max_y and p_ini[1] > max_y):
                        continue
                    px1 = cx + (p_fin[0] - cam_x) * zoom_factor
                    py1 = cy - (p_fin[1] - cam_y) * zoom_factor
                    px2 = cx + (p_ini[0] - cam_x) * zoom_factor
                    py2 = cy - (p_ini[1] - cam_y) * zoom_factor
                    c.create_line(px1, py1, px2, py2, fill=COLOR_ORANGE, width=2.0, dash=(4, 3), capstyle="round")

                #cad vector paths
                for ruta, (rx_min, rx_max, ry_min, ry_max) in zip(self.trazos_actuales, self._trazos_bboxes):
                    if not ruta:
                        continue
                    if rx_max < min_x or rx_min > max_x or ry_max < min_y or ry_min > max_y:
                        continue

                    if len(ruta) == 1:
                        px = cx + (ruta[0][0] - cam_x) * zoom_factor
                        py = cy - (ruta[0][1] - cam_y) * zoom_factor
                        c.create_oval(px - 2, py - 2, px + 2, py + 2, fill=COLOR_VECTOR_GRAY, outline="")
                        continue

                    #dynamic visual decimation for large vector paths
                    if len(ruta) > 10000:
                        stride = max(1, len(ruta) // 10000)
                        pts_sub = ruta[::stride]
                        if pts_sub[-1] != ruta[-1]:
                            pts_sub.append(ruta[-1])
                    else:
                        pts_sub = ruta

                    coords = []
                    for pt in pts_sub:
                        px = cx + (pt[0] - cam_x) * zoom_factor
                        py = cy - (pt[1] - cam_y) * zoom_factor
                        coords.extend([px, py])
                    if len(coords) >= 4:
                        c.create_line(coords, fill=COLOR_VECTOR_GRAY, width=3.0, capstyle="round")

                #spatial culling for previous passes
                for segmento in getattr(self, "trazos_pasadas_previas", []):
                    if not segmento or len(segmento) < 2:
                        continue
                    p1, p2 = segmento[0], segmento[1]
                    if not p1 or not p2 or len(p1) < 2 or len(p2) < 2:
                        continue
                    if (p1[0] < min_x and p2[0] < min_x) or (p1[0] > max_x and p2[0] > max_x) or \
                       (p1[1] < min_y and p2[1] < min_y) or (p1[1] > max_y and p2[1] > max_y):
                        continue
                    px1 = cx + (p1[0] - cam_x) * zoom_factor
                    py1 = cy - (p1[1] - cam_y) * zoom_factor
                    px2 = cx + (p2[0] - cam_x) * zoom_factor
                    py2 = cy - (p2[1] - cam_y) * zoom_factor
                    c.create_line(px1, py1, px2, py2, fill=COLOR_BLUE_FADED, width=3.5, capstyle="round")

                #spatial culling for completed segments of active pass
                for segmento in self.trazos_completados:
                    if not segmento or len(segmento) < 2:
                        continue
                    p1, p2 = segmento[0], segmento[1]
                    if not p1 or not p2 or len(p1) < 2 or len(p2) < 2:
                        continue
                    if (p1[0] < min_x and p2[0] < min_x) or (p1[0] > max_x and p2[0] > max_x) or \
                       (p1[1] < min_y and p2[1] < min_y) or (p1[1] > max_y and p2[1] > max_y):
                        continue
                    px1 = cx + (p1[0] - cam_x) * zoom_factor
                    py1 = cy - (p1[1] - cam_y) * zoom_factor
                    px2 = cx + (p2[0] - cam_x) * zoom_factor
                    py2 = cy - (p2[1] - cam_y) * zoom_factor
                    c.create_line(px1, py1, px2, py2, fill=COLOR_BLUE, width=4.5, capstyle="round")

                #live segment from last drawn anchor to laser pointer
                if self.ancla_vivo is not None and len(self.ancla_vivo) >= 2:
                    ax, ay = self.ancla_vivo
                    lx, ly = self.pos_laser_actual
                    c.create_line(cx + (ax - cam_x) * zoom_factor, cy - (ay - cam_y) * zoom_factor,
                                  cx + (lx - cam_x) * zoom_factor, cy - (ly - cam_y) * zoom_factor,
                                  fill=COLOR_BLUE, width=4.5, capstyle="round")

            #laser spot pointer
            lx, ly = self.pos_laser_actual
            pt_px = cx + (lx - cam_x) * zoom_factor
            pt_py = cy - (ly - cam_y) * zoom_factor
            if -25 <= pt_px <= w + 25 and -25 <= pt_py <= h + 25:
                r_pt = 5
                c.create_oval(pt_px - r_pt, pt_py - r_pt, pt_px + r_pt, pt_py + r_pt, fill="#FFFFFF", outline=COLOR_BORDER, width=BRUTAL_BORDER)
        except Exception:
            pass

    def actualizar_idioma(self):
        """update labels buttons tooltips and gauges on language change"""
        if hasattr(self, "btn_start"):
            self.btn_start.configure(text=tr("btn_start"))
        if hasattr(self, "btn_stop"):
            self.btn_stop.configure(text=tr("btn_stop"))
        if hasattr(self, "btn_pause_resume"):
            if getattr(self, "_esta_pausado", False):
                self.btn_pause_resume.configure(text=tr("btn_resume"))
            else:
                self.btn_pause_resume.configure(text=tr("btn_pause"))
            if hasattr(self, "tooltip_pause") and self.tooltip_pause:
                self.tooltip_pause.texto = tr("btn_resume_tooltip") if getattr(self, "_esta_pausado", False) else tr("btn_pause_tooltip")
        if hasattr(self, "btn_home"):
            agregar_tooltip(self.btn_home, tr("btn_home_tooltip"))
        if hasattr(self, "btn_auto_center"):
            agregar_tooltip(self.btn_auto_center, tr("btn_auto_center_tooltip"))
        if hasattr(self, "btn_set_home"):
            self.btn_set_home.configure(text=tr("btn_apply"))
        if hasattr(self, "lbl_center_title"):
            self.lbl_center_title.configure(text=tr("home_title"))
        if hasattr(self, "lbl_chan_x"):
            self.lbl_chan_x.configure(text=tr("dmm_x"))
        if hasattr(self, "lbl_chan_y"):
            self.lbl_chan_y.configure(text=tr("dmm_y"))

        self._actualizar_titulo_zoom()
        self.dibujar_gauges()
        self.set_estado_sistema(getattr(self, "_ultimo_estado", "READY"))

