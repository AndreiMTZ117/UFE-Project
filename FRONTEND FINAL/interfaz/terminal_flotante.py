# -*- coding: utf-8 -*-
"""cyber brutalist floating terminal and production history"""

import csv
import os
import tkinter as tk
import customtkinter as ctk
from datetime import datetime
from tkinter import filedialog
from typing import Callable, List, Dict, Optional, Any

from .constantes import (
    COLOR_BORDER,
    COLOR_GREEN, COLOR_YELLOW, COLOR_RED, COLOR_TERMINAL_BG,
    FONT_TEACHERS, BRUTAL_CORNER, BRUTAL_BORDER
)
from .i18n import tr, registrar_observador


class TerminalFlotante(ctk.CTkFrame):
    """floating console for hardware debugging and telemetry"""

    def __init__(
        self,
        master,
        on_cerrar: Optional[Callable[[], None]] = None,
        on_abrir: Optional[Callable[[], None]] = None,
        obtener_historial: Optional[Callable[[], List[Dict]]] = None,
        **kwargs
    ):
        self._ancho_fijo = 740
        self._alto_fijo = 440
        super().__init__(
            master,
            fg_color=COLOR_TERMINAL_BG,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            width=self._ancho_fijo,
            height=self._alto_fijo,
            **kwargs
        )
        self.pack_propagate(False)

        self.on_cerrar = on_cerrar
        self.on_abrir = on_abrir
        self.obtener_historial = obtener_historial
        self.f_bold = ctk.CTkFont(family=FONT_TEACHERS, size=11, weight="bold")
        self.f_regular = ctk.CTkFont(family=FONT_TEACHERS, size=11)
        self.visible = False
        self._modo_historial = False

        self._logs: List[Dict[str, str]] = []
        self._filtro_actual: str = "ALL"
        self._filtro_botones: Dict[str, ctk.CTkButton] = {}

        self._crear_widgets()
        registrar_observador(self.actualizar_idioma)

    def _crear_widgets(self):
        #header frame
        t_header = ctk.CTkFrame(self, fg_color="transparent", height=32)
        t_header.pack(fill="x", padx=12, pady=(10, 2))

        #history button
        self.btn_history = ctk.CTkButton(
            t_header,
            text=tr("term_history"),
            command=self._toggle_historial,
            fg_color="transparent",
            text_color="#FFFFFF",
            hover_color="#374151",
            border_color="#FFFFFF",
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            width=88,
            height=26
        )
        self.btn_history.pack(side="left")

        #export csv button
        self.btn_export = ctk.CTkButton(
            t_header,
            text=tr("term_export"),
            command=self._exportar_csv,
            fg_color="transparent",
            text_color="#FFFFFF",
            hover_color="#374151",
            border_color="#FFFFFF",
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            width=68,
            height=26
        )
        self.btn_export.pack(side="left", padx=(6, 0))

        #clear console button
        self.btn_clear = ctk.CTkButton(
            t_header,
            text=tr("term_clear"),
            command=self._limpiar_consola,
            fg_color="transparent",
            text_color="#CBD5E1",
            hover_color="#374151",
            border_color="#64748B",
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            width=72,
            height=26
        )
        self.btn_clear.pack(side="left", padx=(6, 0))

        #copy all logs button
        self.btn_copy = ctk.CTkButton(
            t_header,
            text=tr("term_copy"),
            command=self._copiar_logs,
            fg_color="transparent",
            text_color="#CBD5E1",
            hover_color="#374151",
            border_color="#64748B",
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            width=70,
            height=26
        )
        self.btn_copy.pack(side="left", padx=(6, 0))

        btn_close = ctk.CTkButton(
            t_header,
            text="✕",
            command=self.ocultar,
            fg_color="transparent",
            text_color="#FFFFFF",
            hover_color="#374151",
            corner_radius=BRUTAL_CORNER,
            font=ctk.CTkFont(size=13, weight="bold"),
            width=26,
            height=26
        )
        btn_close.pack(side="right")

        #secondary toolbar: filters
        self.t_filter_bar = ctk.CTkFrame(self, fg_color="transparent", height=24)
        self.t_filter_bar.pack(fill="x", padx=12, pady=(2, 4))

        filtros_def = [
            ("ALL", tr("filter_all"), "#FFFFFF", 48),
            ("ERROR", f"🔴 {tr('filter_errors')}", "#EF4444", 76),
            ("HW", f"🔵 {tr('filter_hw')}", "#06B6D4", 94),
            ("TELEMETRY", f"🟣 {tr('filter_telemetry')}", "#A855F7", 98),
        ]

        for fid, ftxt, fcolor, fwidth in filtros_def:
            btn_f = ctk.CTkButton(
                self.t_filter_bar,
                text=ftxt,
                command=lambda f=fid: self._cambiar_filtro(f),
                fg_color="#374151" if fid == "ALL" else "transparent",
                text_color=fcolor,
                hover_color="#374151",
                border_color="#475569",
                border_width=1 if fid == "ALL" else 0,
                corner_radius=BRUTAL_CORNER,
                font=self.f_bold,
                width=fwidth,
                height=22
            )
            btn_f.pack(side="left", padx=(0, 4))
            self._filtro_botones[fid] = btn_f

        #text log console with severity tags
        self.txt_terminal = tk.Text(
            self,
            bg=COLOR_TERMINAL_BG,
            fg="#E2E8F0",
            insertbackground="#FFFFFF",
            font=("Consolas", 10),
            highlightthickness=0,
            bd=0
        )
        self.txt_terminal.tag_config("TIMESTAMP", foreground="#64748B")
        self.txt_terminal.tag_config("ERROR", foreground="#EF4444", font=("Consolas", 10, "bold"))
        self.txt_terminal.tag_config("WARN", foreground="#F59E0B")
        self.txt_terminal.tag_config("HW", foreground="#06B6D4")
        self.txt_terminal.tag_config("TELEMETRY", foreground="#A855F7")
        self.txt_terminal.tag_config("SUCCESS", foreground="#10B981")
        self.txt_terminal.tag_config("INFO", foreground="#E2E8F0")

        self.txt_terminal.pack(fill="both", expand=True, padx=12, pady=(2, 10))
        self.log(tr("log_console_init"), "INFO")

        #history frame hidden by default
        self.frame_historial = ctk.CTkFrame(self, fg_color=COLOR_TERMINAL_BG)
        self.frame_historial.pack_propagate(False)

    def _cambiar_filtro(self, nuevo_filtro: str):
        """switches active log filter and re-renders text console"""
        self._filtro_actual = nuevo_filtro
        for fid, btn in self._filtro_botones.items():
            if fid == nuevo_filtro:
                btn.configure(fg_color="#374151", border_width=1)
            else:
                btn.configure(fg_color="transparent", border_width=0)

        self.txt_terminal.delete("1.0", "end")
        for reg in self._logs:
            if self._coincide_filtro(reg["nivel"]):
                self._insertar_linea(reg)

    def _coincide_filtro(self, nivel: str) -> bool:
        if self._filtro_actual == "ALL":
            return True
        if self._filtro_actual == "ERROR":
            return nivel in ("ERROR", "WARN")
        if self._filtro_actual == "HW":
            return nivel in ("HW", "ERROR")
        if self._filtro_actual == "TELEMETRY":
            return nivel == "TELEMETRY"
        return True

    def _insertar_linea(self, reg: Dict[str, str]):
        self.txt_terminal.insert("end", f"[{reg['ts']}] ", "TIMESTAMP")
        self.txt_terminal.insert("end", f"{reg['texto']}\n", reg["nivel"])
        self.txt_terminal.see("end")

    def _limpiar_consola(self):
        """clears internal log buffer and screen"""
        self._logs.clear()
        self.txt_terminal.delete("1.0", "end")

    def _copiar_logs(self):
        """copies current visible terminal content to system clipboard"""
        try:
            full_text = self.txt_terminal.get("1.0", "end-1c")
            self.clipboard_clear()
            self.clipboard_append(full_text)
            self.btn_copy.configure(text="✓ Copied!")
            self.after(1500, lambda: self.btn_copy.configure(text=tr("term_copy")))
        except Exception:
            pass

    def _toggle_historial(self):
        """toggle between logs and production history"""
        if self._modo_historial:
            self.frame_historial.pack_forget()
            self.t_filter_bar.pack(fill="x", padx=12, pady=(2, 4))
            self.txt_terminal.pack(fill="both", expand=True, padx=12, pady=(2, 10))
            self.btn_history.configure(text=tr("term_history"), border_color="#FFFFFF")
            self._modo_historial = False
        else:
            self._mostrar_historial()

    def _mostrar_historial(self):
        """load and render production history table"""
        if not self.obtener_historial:
            return

        registros = self.obtener_historial()

        #hide log terminal and filter bar, show history
        self.t_filter_bar.pack_forget()
        self.txt_terminal.pack_forget()

        #clear previous history
        for widget in self.frame_historial.winfo_children():
            widget.destroy()

        self.frame_historial.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self.btn_history.configure(text=tr("term_logs"), border_color=COLOR_YELLOW)
        self._modo_historial = True

        if not registros:
            lbl_empty = ctk.CTkLabel(
                self.frame_historial,
                text=tr("hist_no_records"),
                font=self.f_bold,
                text_color="#94A3B8"
            )
            lbl_empty.pack(pady=40)
            return

        #scrollable table
        scroll_frame = ctk.CTkScrollableFrame(
            self.frame_historial,
            fg_color=COLOR_TERMINAL_BG,
            scrollbar_button_color="#374151"
        )
        scroll_frame.pack(fill="both", expand=True)

        #table header
        header_frame = ctk.CTkFrame(scroll_frame, fg_color="#374151", height=30, corner_radius=BRUTAL_CORNER)
        header_frame.pack(fill="x", padx=2, pady=(0, 4))
        header_frame.pack_propagate(False)

        columnas = [tr("col_num"), tr("col_date"), tr("col_dxf"), tr("col_recipe"), tr("col_mode"), tr("col_status"), tr("col_duration")]
        anchos = [32, 115, 125, 115, 75, 85, 60]
        for col, ancho in zip(columnas, anchos):
            ctk.CTkLabel(
                header_frame,
                text=col,
                font=self.f_bold,
                text_color="#FFFFFF",
                width=ancho,
                anchor="w"
            ).pack(side="left", padx=4)

        #data rows
        self._datos_historial = registros
        for i, reg in enumerate(registros[:100]):
            color_bg = "#1E293B" if i % 2 == 0 else COLOR_TERMINAL_BG
            row_frame = ctk.CTkFrame(scroll_frame, fg_color=color_bg, height=26, corner_radius=BRUTAL_CORNER)
            row_frame.pack(fill="x", padx=2, pady=1)
            row_frame.pack_propagate(False)

            estado_raw = str(reg.get("estado", "?")).strip().upper()
            if estado_raw in ("COMPLETADO", "COMPLETED", "OK"):
                color_estado = COLOR_GREEN
                estado_display = tr("status_completed")
            elif estado_raw in ("ABORTADO", "ABORTED", "STOPPED"):
                color_estado = "#FF6B6B"
                estado_display = tr("status_stopped")
            else:
                color_estado = "#F5A623"
                estado_display = "FAILED"

            timestamp = str(reg.get("timestamp", ""))
            if len(timestamp) > 16:
                timestamp = timestamp[:16]

            dur = reg.get("duracion_segundos", 0)
            dur_txt = f"{dur:.1f}s" if dur is not None else "—"

            nombre_dxf = os.path.basename(str(reg.get("archivo_dxf", "")))
            if len(nombre_dxf) > 18:
                nombre_dxf = nombre_dxf[:15] + "..."

            receta_txt = str(reg.get("receta_nombre", "Manual"))
            if len(receta_txt) > 16:
                receta_txt = receta_txt[:13] + "..."

            modo_txt = str(reg.get("modo_proceso") or reg.get("modo") or "Cutting")
            if modo_txt in ("Cutting", "Řezání"):
                modo_txt = tr("mode_cutting")
            elif modo_txt in ("Welding", "Svařování"):
                modo_txt = tr("mode_welding")
            elif modo_txt in ("Marking", "Značení"):
                modo_txt = tr("mode_marking")

            if len(modo_txt) > 10:
                modo_txt = modo_txt[:8] + ".."

            vals = [
                str(reg.get("id", "")),
                timestamp,
                nombre_dxf,
                receta_txt,
                modo_txt,
                estado_display,
                dur_txt
            ]
            colores = ["#94A3B8", "#FFFFFF", "#FFFFFF", "#FFFFFF", COLOR_YELLOW, color_estado, "#FFFFFF"]

            for val, ancho, color in zip(vals, anchos, colores):
                ctk.CTkLabel(
                    row_frame,
                    text=val,
                    font=self.f_regular,
                    text_color=color,
                    width=ancho,
                    anchor="w"
                ).pack(side="left", padx=4)

    def _exportar_csv(self):
        """export production history to csv file"""
        if not self.obtener_historial:
            return

        registros = self.obtener_historial()
        if not registros:
            self.log(tr("hist_export_empty"), "WARN")
            return

        fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_default = f"production_history_{fecha_str}.csv"

        ruta = filedialog.asksaveasfilename(
            title=tr("hist_export_title"),
            defaultextension=".csv",
            initialfile=ruta_default,
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )

        if not ruta:
            return

        try:
            campos = [
                "ID", "Date", "Time", "DXF_File", "Hardware",
                "Recipe", "Process_Mode", "Mark_Speed_mms", "Travel_Speed_mms",
                "Scale", "RDP_Tolerance_mm", "Join_Tolerance_mm",
                "Paths", "Waypoints", "Duration_Seconds",
                "Status", "Error_Message",
                "Tracking_RMS_um", "Tracking_Max_um", "Tracking_Lag_ms"
            ]

            with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
                writer.writeheader()
                for reg in registros:
                    ts = str(reg.get("timestamp", "")).strip()
                    partes = ts.split()
                    fecha = partes[0] if len(partes) > 0 else ts
                    hora = partes[1] if len(partes) > 1 else ""

                    st_raw = str(reg.get("estado", "")).upper()
                    st_eng = "COMPLETED" if st_raw in ("COMPLETADO", "COMPLETED", "OK") else "ABORTED" if st_raw in ("ABORTADO", "ABORTED", "STOPPED") else st_raw

                    modo_proc_csv = str(reg.get("modo_proceso") or reg.get("modo") or "Cutting").strip()
                    if modo_proc_csv.lower() in ("cutting", "řezání", "corte"):
                        modo_proc_csv = "Cutting"
                    elif modo_proc_csv.lower() in ("welding", "svařování", "soldadura"):
                        modo_proc_csv = "Welding"
                    elif modo_proc_csv.lower() in ("marking", "značení", "marcado"):
                        modo_proc_csv = "Marking"

                    fila = {
                        "ID": reg.get("id", ""),
                        "Date": fecha,
                        "Time": hora,
                        "DXF_File": reg.get("archivo_dxf", ""),
                        "Hardware": reg.get("hardware_usado", ""),
                        "Recipe": reg.get("receta_nombre", ""),
                        "Process_Mode": modo_proc_csv,
                        "Mark_Speed_mms": reg.get("velocidad_trazado", ""),
                        "Travel_Speed_mms": reg.get("velocidad_viaje", ""),
                        "Scale": reg.get("escala_dibujo", ""),
                        "RDP_Tolerance_mm": reg.get("tolerancia_rdp", ""),
                        "Join_Tolerance_mm": reg.get("tolerancia_union", ""),
                        "Paths": reg.get("trazos_totales", ""),
                        "Waypoints": reg.get("waypoints_totales", ""),
                        "Duration_Seconds": reg.get("duracion_segundos", ""),
                        "Status": st_eng,
                        "Error_Message": reg.get("mensaje_error", ""),
                        "Tracking_RMS_um": "" if reg.get("tracking_rms_um") is None else reg.get("tracking_rms_um"),
                        "Tracking_Max_um": "" if reg.get("tracking_max_um") is None else reg.get("tracking_max_um"),
                        "Tracking_Lag_ms": "" if reg.get("tracking_lag_ms") is None else reg.get("tracking_lag_ms")
                    }
                    writer.writerow(fila)

            self.log(tr("hist_export_ok", file=os.path.basename(ruta), count=len(registros)), "SUCCESS")
        except Exception as e:
            self.log(tr("hist_export_err", err=e), "ERROR")

    def actualizar_idioma(self):
        """update button and table texts on language change"""
        if hasattr(self, "btn_history"):
            self.btn_history.configure(text=tr("term_logs") if self._modo_historial else tr("term_history"))
        if hasattr(self, "btn_export"):
            self.btn_export.configure(text=tr("term_export"))
        if hasattr(self, "btn_clear"):
            self.btn_clear.configure(text=tr("term_clear"))
        if hasattr(self, "btn_copy"):
            self.btn_copy.configure(text=tr("term_copy"))
        if hasattr(self, "_filtro_botones"):
            if "ALL" in self._filtro_botones:
                self._filtro_botones["ALL"].configure(text=tr("filter_all"))
            if "ERROR" in self._filtro_botones:
                self._filtro_botones["ERROR"].configure(text=f"🔴 {tr('filter_errors')}")
            if "HW" in self._filtro_botones:
                self._filtro_botones["HW"].configure(text=f"🔵 {tr('filter_hw')}")
            if "TELEMETRY" in self._filtro_botones:
                self._filtro_botones["TELEMETRY"].configure(text=f"🟣 {tr('filter_telemetry')}")
        if self._modo_historial:
            self._mostrar_historial()

    def toggle(self):
        if self.visible:
            self.ocultar()
        else:
            self.mostrar()

    def mostrar(self):
        self.place(relx=0.98, rely=0.08, anchor="ne")
        self.visible = True
        self.lift()
        if self.on_abrir:
            self.on_abrir()

    def ocultar(self):
        self.place_forget()
        self.visible = False
        if self._modo_historial:
            self._toggle_historial()
        if self.on_cerrar:
            self.on_cerrar()

    def log(self, texto: str, nivel: Optional[str] = None):
        """append log line to console with severity color, timestamp and auto-open on critical errors"""
        if nivel is None:
            txt_upper = texto.upper()
            if any(k in txt_upper for k in ("[ERROR]", "[CRITICAL]", "[FATAL]", "EXCEPTION", "FAILED")):
                nivel = "ERROR"
            elif any(k in txt_upper for k in ("[WARN]", "[WARN HW]", "⚠️", "WARNING")):
                nivel = "WARN"
            elif any(k in txt_upper for k in ("[HW]", "[DAQ]", "[NIDAQCONTROLLER]", "[FEEDBACK]")):
                nivel = "HW"
            elif any(k in txt_upper for k in ("[TELEMETRY]", "[TRACKING]")):
                nivel = "TELEMETRY"
            elif any(k in txt_upper for k in ("[OK]", "COMPLETED", "COMPLETADO", "FINISHED")):
                nivel = "SUCCESS"
            else:
                nivel = "INFO"

        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        registro = {"ts": ts, "nivel": nivel, "texto": texto}
        self._logs.append(registro)
        if len(self._logs) > 2000:
            self._logs.pop(0)

        #auto-open on critical error (Option A)
        if nivel == "ERROR" and not self.visible:
            self.mostrar()

        if not self._modo_historial and self._coincide_filtro(nivel):
            self._insertar_linea(registro)
