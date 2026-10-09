# -*- coding: utf-8 -*-
"""
interfaz/panel_derecho.py — Panel Derecho: Gauges + Trace Point + Execution Controls
"""

import tkinter as tk
import customtkinter as ctk
from typing import Callable, List, Optional, Tuple

from .constantes import (
    COLOR_BG, COLOR_CARD, COLOR_BORDER, COLOR_TEXT,
    COLOR_YELLOW, COLOR_RED, COLOR_BLUE,
    COLOR_PAUSE, COLOR_TIMER_BG,
    COLOR_VECTOR_GRAY, COLOR_CYAN_HALO,
    FONT_BRUNO, FONT_TEACHERS,
    BRUTAL_CORNER, BRUTAL_BORDER
)


class PanelDerecho(ctk.CTkFrame):
    """Panel lateral derecho con gauges circulares, canvas zoom de trace point y controles de ciclo."""

    def __init__(
        self,
        master,
        on_click_start: Optional[Callable[[], None]] = None,
        on_click_pause_resume: Optional[Callable[[], None]] = None,
        on_click_stop: Optional[Callable[[], None]] = None,
        on_centro_cambiado: Optional[Callable[[float, float], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_click_start = on_click_start
        self.on_click_pause_resume = on_click_pause_resume
        self.on_click_stop = on_click_stop
        self.on_centro_cambiado = on_centro_cambiado

        self.f_head = ctk.CTkFont(family=FONT_TEACHERS, size=13, weight="bold")
        self.f_bold = ctk.CTkFont(family=FONT_TEACHERS, size=11, weight="bold")
        self.f_regular = ctk.CTkFont(family=FONT_TEACHERS, size=11)
        self.f_bruno_btn = ctk.CTkFont(family=FONT_BRUNO, size=14, weight="bold")
        self.f_bruno_timer = ctk.CTkFont(family=FONT_BRUNO, size=18, weight="bold")

        self.trazos_actuales: List[List[Tuple[float, float]]] = []
        self.trazos_completados: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        self.pos_laser_actual = (0.0, 0.0)   # Centro óptico del campo Thorlabs

        self.pct_trace = 0.0
        self.pct_total = 0.0

        self._crear_widgets()

    def _crear_widgets(self):
        # 1. Panel de Controles de Ejecución (ANCLADO AL FONDO PRIMERO)
        self.frame_controles = ctk.CTkFrame(self, fg_color="transparent", height=48)
        self.frame_controles.pack(side="bottom", fill="x", pady=(6, 0))
        self.frame_controles.pack_propagate(False)

        # Botón HOME estilo Cyber-Brutalism (Cuadrado con borde grueso)
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
            font=ctk.CTkFont(size=22, weight="bold"),
            width=48,
            height=44
        )
        self.btn_home.pack(side="left", padx=(0, 8))

        # Contenedor dinámico (IDLE vs RUNNING)
        self.action_box = ctk.CTkFrame(self.frame_controles, fg_color="transparent")
        self.action_box.pack(side="left", fill="both", expand=True)

        # Botón START (Modo IDLE)
        self.btn_start = ctk.CTkButton(
            self.action_box,
            text="START",
            command=self._cb_start,
            fg_color=COLOR_YELLOW,
            text_color=COLOR_TEXT,
            hover_color="#FFA000",
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bruno_btn,
            height=44
        )
        self.btn_start.pack(fill="both", expand=True)

        # Widgets en Modo RUNNING (Ocultos inicialmente)
        self.running_box = ctk.CTkFrame(self.action_box, fg_color="transparent")

        self.btn_pause_resume = ctk.CTkButton(
            self.running_box,
            text="PAUSE",
            command=self._cb_pause_resume,
            fg_color=COLOR_PAUSE,
            text_color=COLOR_TEXT,
            hover_color="#818CF8",
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            font=ctk.CTkFont(family=FONT_BRUNO, size=12, weight="bold"),
            width=92,
            height=44
        )
        self.btn_pause_resume.pack(side="left", padx=(0, 6))

        self.btn_stop = ctk.CTkButton(
            self.running_box,
            text="STOP",
            command=self._cb_stop,
            fg_color=COLOR_RED,
            text_color=COLOR_TEXT,
            hover_color="#DC2626",
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bruno_btn,
            width=80,
            height=44
        )
        self.btn_stop.pack(side="left", padx=(0, 6))

        self.timer_box = ctk.CTkFrame(
            self.running_box,
            fg_color=COLOR_TIMER_BG,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=44
        )
        self.timer_box.pack(side="left", fill="both", expand=True)

        self.lbl_timer = ctk.CTkLabel(
            self.timer_box,
            text="0:00:00",
            font=self.f_bruno_timer,
            text_color=COLOR_TEXT
        )
        self.lbl_timer.place(relx=0.5, rely=0.5, anchor="center")

        # 2. Medidores circulares (Trace y Total) con tarjeta blanca y borde 2px
        top_gauges = ctk.CTkFrame(self, fg_color="transparent")
        top_gauges.pack(side="top", fill="x", pady=(2, 4))
        ctk.CTkLabel(top_gauges, text="PROGRESO DE CORTE", font=self.f_head, text_color=COLOR_TEXT, anchor="w").pack(fill="x")

        self.card_gauges = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=125
        )
        self.card_gauges.pack(side="top", fill="x", pady=(0, 6))
        self.card_gauges.pack_propagate(False)

        self.canvas_gauges = tk.Canvas(self.card_gauges, bg=COLOR_CARD, highlightthickness=0, height=120)
        self.canvas_gauges.pack(fill="both", expand=True)
        self.canvas_gauges.bind("<Configure>", lambda e: self.dibujar_gauges())

        # 2b. Monitor Analítico DAQ & Tiempo Exacto (FASE 4.2)
        self.card_monitor_daq = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            height=58
        )
        self.card_monitor_daq.pack(side="top", fill="x", pady=(0, 6))
        self.card_monitor_daq.pack_propagate(False)

        daq_row1 = ctk.CTkFrame(self.card_monitor_daq, fg_color="transparent")
        daq_row1.pack(fill="x", padx=8, pady=(4, 1))

        self.lbl_daq_tiempo = ctk.CTkLabel(
            daq_row1,
            text="⏱ T. EST.: 0.000 s",
            font=self.f_bold,
            text_color=COLOR_TEXT
        )
        self.lbl_daq_tiempo.pack(side="left")

        self.lbl_daq_muestras = ctk.CTkLabel(
            daq_row1,
            text="[ 0 pts @ 100kS/s ]",
            font=self.f_regular,
            text_color="#64748B"
        )
        self.lbl_daq_muestras.pack(side="right")

        daq_row2 = ctk.CTkFrame(self.card_monitor_daq, fg_color="transparent")
        daq_row2.pack(fill="x", padx=8, pady=(0, 3))

        self.lbl_daq_voltaje_live = ctk.CTkLabel(
            daq_row2,
            text="⚡ AO: Vx = +0.00 V | Vy = +0.00 V",
            font=self.f_regular,
            text_color=COLOR_BLUE
        )
        self.lbl_daq_voltaje_live.pack(side="left")

        self.lbl_daq_voltaje_max = ctk.CTkLabel(
            daq_row2,
            text="|V|_max: ±0.00 V",
            font=self.f_regular,
            text_color="#64748B"
        )
        self.lbl_daq_voltaje_max.pack(side="right")

        # 3. Panel "Trace point" con Zoom y Halo (al centro expandible)
        self.box_trace = ctk.CTkFrame(self, fg_color="transparent")
        self.box_trace.pack(side="top", fill="both", expand=True, pady=(2, 4))

        self.lbl_trace = ctk.CTkLabel(self.box_trace, text="SEGUIMIENTO LÁSER (ZOOM 4X)", font=self.f_head, text_color=COLOR_TEXT, anchor="w")
        self.lbl_trace.pack(side="top", fill="x", pady=(0, 4))

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
        self.canvas_trace.bind("<Configure>", lambda e: self.redibujar_trace())

        # Badge flotante de coordenadas dentro de la tarjeta
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
            text="x = 0.00 cm  |  y = 0.00 cm",
            font=self.f_bold,
            text_color=COLOR_TEXT,
            padx=10,
            pady=3
        )
        self.lbl_coord_live.pack()

        # Popup flotante HOME con X e Y EDITABLES para definir el centro
        self.card_home_popup = ctk.CTkFrame(
            self.winfo_toplevel(),
            fg_color=COLOR_YELLOW,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            width=200,
            height=130
        )

        lbl_center = ctk.CTkLabel(self.card_home_popup, text="Center (Home)", font=self.f_bold, text_color=COLOR_TEXT)
        lbl_center.pack(pady=(6, 4))

        frame_xy = ctk.CTkFrame(self.card_home_popup, fg_color="transparent")
        frame_xy.pack(padx=10, pady=2, fill="x")

        # Fila X
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
        self.entry_home_x.insert(0, "0.00")
        self.entry_home_x.pack(side="left", padx=4)
        ctk.CTkLabel(row_x, text="cm", font=self.f_regular, text_color=COLOR_TEXT).pack(side="left")

        # Fila Y
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
        self.entry_home_y.insert(0, "0.00")
        self.entry_home_y.pack(side="left", padx=4)
        ctk.CTkLabel(row_y, text="cm", font=self.f_regular, text_color=COLOR_TEXT).pack(side="left")

        # Botón para centrar y aplicar
        self.btn_set_home = ctk.CTkButton(
            self.card_home_popup,
            text="Centrar",
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

    # Callbacks internos
    def _cb_start(self):
        if self.on_click_start:
            self.on_click_start()

    def _cb_pause_resume(self):
        if self.on_click_pause_resume:
            self.on_click_pause_resume()

    def _cb_stop(self):
        if self.on_click_stop:
            self.on_click_stop()

    def _cb_aplicar_centro(self):
        try:
            x = float(self.entry_home_x.get().strip())
            y = float(self.entry_home_y.get().strip())
            self.pos_laser_actual = (x, y)
            self.actualizar_coordenadas(x, y)
            if self.on_centro_cambiado:
                self.on_centro_cambiado(x, y)
            self.toggle_home_card()
        except ValueError:
            pass

    def set_centro(self, x: float, y: float):
        """Actualiza los inputs del centro en el popup."""
        self.entry_home_x.delete(0, "end")
        self.entry_home_x.insert(0, f"{x:.2f}")
        self.entry_home_y.delete(0, "end")
        self.entry_home_y.insert(0, f"{y:.2f}")
        self.actualizar_coordenadas(x, y)

    def toggle_home_card(self):
        if self.card_home_popup.winfo_ismapped():
            self.card_home_popup.place_forget()
            self.btn_home.configure(fg_color=COLOR_CARD)
        else:
            self.card_home_popup.place(relx=0.76, rely=0.88, anchor="se")
            self.btn_home.configure(fg_color=COLOR_YELLOW)

    # Modos de estado de control
    def set_modo_running(self):
        self.btn_start.pack_forget()
        self.running_box.pack(fill="both", expand=True)
        self.btn_pause_resume.configure(text="PAUSE", fg_color=COLOR_PAUSE)

    def set_modo_idle(self):
        self.running_box.pack_forget()
        self.btn_start.pack(fill="both", expand=True)

    def set_estado_pausa(self, pausado: bool):
        if pausado:
            self.btn_pause_resume.configure(text="RESUME", fg_color=COLOR_YELLOW)
        else:
            self.btn_pause_resume.configure(text="PAUSE", fg_color=COLOR_PAUSE)

    def actualizar_timer(self, texto: str):
        self.lbl_timer.configure(text=texto)

    def actualizar_coordenadas(self, x: float, y: float):
        self.pos_laser_actual = (x, y)
        self.lbl_coord_live.configure(text=f"x = {x:.2f} cm  |  y = {y:.2f} cm")

    def set_metricas_estimadas(self, tiempo_s: float, n_muestras: int, max_vx: float, max_vy: float):
        """Actualiza las métricas analíticas del monitor DAQ (tiempo exacto y voltajes máx)."""
        self.lbl_daq_tiempo.configure(text=f"⏱ T. EST.: {tiempo_s:.3f} s")
        self.lbl_daq_muestras.configure(text=f"[ {n_muestras:,} pts @ 100kS/s ]")
        v_max = max(max_vx, max_vy)
        self.lbl_daq_voltaje_max.configure(text=f"|V|_max: ±{v_max:.2f} V")

    def actualizar_voltajes_live(self, vx: float, vy: float):
        """Actualiza la telemetría instantánea de voltaje enviada a los galvanómetros."""
        self.lbl_daq_voltaje_live.configure(text=f"⚡ AO: Vx = {vx:+.2f} V | Vy = {vy:+.2f} V")

    # Renderizado de medidores
    def dibujar_gauges(self, pct_trace: Optional[float] = None, pct_total: Optional[float] = None):
        if pct_trace is not None:
            self.pct_trace = pct_trace
        if pct_total is not None:
            self.pct_total = pct_total

        c = self.canvas_gauges
        c.delete("all")

        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 50 or h <= 50:
            return

        r = 38
        grosor = 11

        c1_x = w * 0.28
        c1_y = h * 0.56
        self._dibujar_un_gauge(c, c1_x, c1_y, r, grosor, self.pct_trace, "Trazo Actual")

        c2_x = w * 0.72
        c2_y = h * 0.56
        self._dibujar_un_gauge(c, c2_x, c2_y, r, grosor, self.pct_total, "Total Acumulado")

    def _dibujar_un_gauge(self, c: tk.Canvas, cx: float, cy: float, r: float, grosor: float, pct: float, titulo: str):
        c.create_text(cx, cy - r - 10, text=titulo, font=(FONT_TEACHERS, 10, "bold"), fill=COLOR_TEXT)
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=COLOR_BORDER, width=BRUTAL_BORDER)

        grados_arco = -(pct / 100.0) * 360.0
        if pct > 0:
            c.create_arc(
                cx - r + grosor / 2, cy - r + grosor / 2,
                cx + r - grosor / 2, cy + r - grosor / 2,
                start=90,
                extent=grados_arco,
                style="arc",
                outline=COLOR_BLUE,
                width=grosor
            )

        c.create_text(cx, cy, text=f"{int(round(pct))} %", font=(FONT_TEACHERS, 12, "bold"), fill=COLOR_TEXT)

    # Renderizado Trace Point (Zoom 4x)
    def redibujar_trace(
        self,
        trazos: Optional[List[List[Tuple[float, float]]]] = None,
        trazos_completados: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None,
        pos_laser: Optional[Tuple[float, float]] = None
    ):
        if trazos is not None:
            self.trazos_actuales = trazos
        if trazos_completados is not None:
            self.trazos_completados = trazos_completados
        if pos_laser is not None:
            self.pos_laser_actual = pos_laser

        c = self.canvas_trace
        c.delete("all")

        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 20 or h <= 20:
            return

        cx = w / 2
        cy = h / 2

        lx, ly = self.pos_laser_actual
        zoom_factor = 45.0

        if self.trazos_actuales:
            for ruta in self.trazos_actuales:
                if len(ruta) < 2:
                    continue
                coords = []
                for pt in ruta:
                    px = cx + (pt[0] - lx) * zoom_factor
                    py = cy - (pt[1] - ly) * zoom_factor
                    coords.extend([px, py])
                c.create_line(coords, fill=COLOR_VECTOR_GRAY, width=3.0, capstyle="round")

            for p1, p2 in self.trazos_completados:
                px1 = cx + (p1[0] - lx) * zoom_factor
                py1 = cy - (p1[1] - ly) * zoom_factor
                px2 = cx + (p2[0] - lx) * zoom_factor
                py2 = cy - (p2[1] - ly) * zoom_factor
                c.create_line(px1, py1, px2, py2, fill=COLOR_BLUE, width=4.5, capstyle="round")

        # Halo luminoso cyan y punto blanco central
        r_halo = 18
        c.create_oval(cx - r_halo, cy - r_halo, cx + r_halo, cy + r_halo, fill=COLOR_CYAN_HALO, outline="")

        r_pt = 5
        c.create_oval(cx - r_pt, cy - r_pt, cx + r_pt, cy + r_pt, fill="#FFFFFF", outline=COLOR_BORDER, width=BRUTAL_BORDER)
