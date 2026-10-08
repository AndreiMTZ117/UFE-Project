# -*- coding: utf-8 -*-
"""
interfaz/terminal_flotante.py — Terminal Flotante (Cyber-Brutalist)
"""

import csv
import os
import tkinter as tk
import customtkinter as ctk
from datetime import datetime
from tkinter import filedialog
from typing import Callable, List, Dict, Optional

from .constantes import (
    COLOR_CARD, COLOR_BORDER, COLOR_TEXT,
    COLOR_GREEN, COLOR_YELLOW, COLOR_TERMINAL_BG,
    FONT_TEACHERS, BRUTAL_CORNER, BRUTAL_BORDER
)


class TerminalFlotante(ctk.CTkFrame):
    """Consola emergente Cyber-Brutalist para depuración y telemetría de hardware."""

    def __init__(self, master, on_cerrar: Optional[Callable[[], None]] = None,
                 obtener_historial: Optional[Callable[[], List[Dict]]] = None,
                 **kwargs):
        super().__init__(
            master,
            fg_color=COLOR_TERMINAL_BG,
            border_color=COLOR_BORDER,
            border_width=BRUTAL_BORDER,
            corner_radius=BRUTAL_CORNER,
            width=580,
            height=360,
            **kwargs
        )

        self.on_cerrar = on_cerrar
        self.obtener_historial = obtener_historial
        self.f_bold = ctk.CTkFont(family=FONT_TEACHERS, size=12, weight="bold")
        self.f_regular = ctk.CTkFont(family=FONT_TEACHERS, size=10)
        self.visible = False
        self._modo_historial = False

        self._crear_widgets()

    def _crear_widgets(self):
        # 1. Cabecera del terminal
        t_header = ctk.CTkFrame(self, fg_color="transparent", height=34)
        t_header.pack(fill="x", padx=12, pady=(10, 4))

        # Botón History funcional
        self.btn_history = ctk.CTkButton(
            t_header,
            text="📋 History",
            command=self._toggle_historial,
            fg_color="transparent",
            text_color="#FFFFFF",
            hover_color="#374151",
            border_color="#FFFFFF",
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            width=90,
            height=28
        )
        self.btn_history.pack(side="left")

        # Botón Exportar CSV
        self.btn_export = ctk.CTkButton(
            t_header,
            text="⬇ CSV",
            command=self._exportar_csv,
            fg_color="transparent",
            text_color="#FFFFFF",
            hover_color="#374151",
            border_color="#FFFFFF",
            border_width=1,
            corner_radius=BRUTAL_CORNER,
            font=self.f_bold,
            width=70,
            height=28
        )
        self.btn_export.pack(side="left", padx=(6, 0))

        btn_close = ctk.CTkButton(
            t_header,
            text="✕",
            command=self.ocultar,
            fg_color="transparent",
            text_color="#FFFFFF",
            hover_color="#374151",
            corner_radius=BRUTAL_CORNER,
            font=ctk.CTkFont(size=14, weight="bold"),
            width=28,
            height=28
        )
        btn_close.pack(side="right")

        # 2. Consola de texto (logs)
        self.txt_terminal = tk.Text(
            self,
            bg=COLOR_TERMINAL_BG,
            fg=COLOR_GREEN,
            insertbackground="#FFFFFF",
            font=("Consolas", 10),
            highlightthickness=0,
            bd=0
        )
        self.txt_terminal.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self.txt_terminal.insert("end", "[UFE Laser Console Initialized]\nSistema listo.\n")

        # 3. Frame de historial (oculto por defecto)
        self.frame_historial = ctk.CTkFrame(self, fg_color=COLOR_TERMINAL_BG)
        # No se empaca hasta que se active

    def _toggle_historial(self):
        """Alterna entre vista de logs y vista de historial de producción."""
        if self._modo_historial:
            self.frame_historial.pack_forget()
            self.txt_terminal.pack(fill="both", expand=True, padx=12, pady=(4, 12))
            self.btn_history.configure(text="📋 History", border_color="#FFFFFF")
            self._modo_historial = False
        else:
            self._mostrar_historial()

    def _mostrar_historial(self):
        """Carga y muestra el historial de producción."""
        if not self.obtener_historial:
            return

        registros = self.obtener_historial()

        # Ocultar terminal de logs, mostrar historial
        self.txt_terminal.pack_forget()

        # Limpiar historial previo
        for widget in self.frame_historial.winfo_children():
            widget.destroy()

        self.frame_historial.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self.btn_history.configure(text="◀ Logs", border_color=COLOR_YELLOW)
        self._modo_historial = True

        if not registros:
            lbl_empty = ctk.CTkLabel(
                self.frame_historial,
                text="No hay registros de producción aún.",
                font=self.f_bold,
                text_color="#94A3B8"
            )
            lbl_empty.pack(pady=40)
            return

        # Tabla scrollable
        scroll_frame = ctk.CTkScrollableFrame(
            self.frame_historial,
            fg_color=COLOR_TERMINAL_BG,
            scrollbar_button_color="#374151"
        )
        scroll_frame.pack(fill="both", expand=True)

        # Cabecera de la tabla
        header_frame = ctk.CTkFrame(scroll_frame, fg_color="#374151", height=28, corner_radius=BRUTAL_CORNER)
        header_frame.pack(fill="x", pady=(0, 4))
        header_frame.pack_propagate(False)

        columnas = ["#", "Fecha", "DXF", "Receta", "Estado", "Duración"]
        anchos = [30, 130, 120, 120, 80, 70]
        for col, ancho in zip(columnas, anchos):
            ctk.CTkLabel(
                header_frame,
                text=col,
                font=self.f_bold,
                text_color="#FFFFFF",
                width=ancho,
                anchor="w"
            ).pack(side="left", padx=4)

        # Filas de datos
        self._datos_historial = registros
        for i, reg in enumerate(registros[:50]):
            color_bg = "#1E293B" if i % 2 == 0 else COLOR_TERMINAL_BG
            row_frame = ctk.CTkFrame(scroll_frame, fg_color=color_bg, height=26, corner_radius=0)
            row_frame.pack(fill="x")
            row_frame.pack_propagate(False)

            estado = reg.get("estado", "?")
            color_estado = COLOR_GREEN if estado == "COMPLETADO" else "#FF6B6B" if estado == "ABORTADO" else "#FFB200"

            timestamp = reg.get("timestamp", "")
            if len(timestamp) > 16:
                timestamp = timestamp[:16]

            dur = reg.get("duracion_segundos", 0)
            dur_txt = f"{dur:.1f}s" if dur else "—"

            vals = [
                str(reg.get("id", "")),
                timestamp,
                str(reg.get("archivo_dxf", ""))[:18],
                str(reg.get("receta_nombre", ""))[:18],
                estado,
                dur_txt
            ]
            colores = ["#94A3B8", "#FFFFFF", "#FFFFFF", "#FFFFFF", color_estado, "#FFFFFF"]

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
        """Exporta el historial de producción a un archivo CSV."""
        if not self.obtener_historial:
            return

        registros = self.obtener_historial()
        if not registros:
            self.log("[Export] No hay registros para exportar.")
            return

        fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_default = f"historial_produccion_{fecha_str}.csv"

        ruta = filedialog.asksaveasfilename(
            title="Exportar Historial de Producción",
            defaultextension=".csv",
            initialfile=ruta_default,
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")]
        )

        if not ruta:
            return

        try:
            campos = [
                "ID", "Fecha", "Hora", "Archivo_DXF", "Hardware",
                "Receta", "Velocidad_Trazado_mms", "Velocidad_Viaje_mms",
                "Escala", "Tolerancia_RDP_mm", "Tolerancia_Union_mm",
                "Trazos", "Waypoints", "Duracion_Segundos",
                "Estado", "Mensaje_Error"
            ]

            with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
                writer.writeheader()
                for reg in registros:
                    ts = str(reg.get("timestamp", "")).strip()
                    partes = ts.split()
                    fecha = partes[0] if len(partes) > 0 else ts
                    hora = partes[1] if len(partes) > 1 else ""

                    fila = {
                        "ID": reg.get("id", ""),
                        "Fecha": fecha,
                        "Hora": hora,
                        "Archivo_DXF": reg.get("archivo_dxf", ""),
                        "Hardware": reg.get("hardware_usado", ""),
                        "Receta": reg.get("receta_nombre", ""),
                        "Velocidad_Trazado_mms": reg.get("velocidad_trazado", ""),
                        "Velocidad_Viaje_mms": reg.get("velocidad_viaje", ""),
                        "Escala": reg.get("escala_dibujo", ""),
                        "Tolerancia_RDP_mm": reg.get("tolerancia_rdp", ""),
                        "Tolerancia_Union_mm": reg.get("tolerancia_union", ""),
                        "Trazos": reg.get("trazos_totales", ""),
                        "Waypoints": reg.get("waypoints_totales", ""),
                        "Duracion_Segundos": reg.get("duracion_segundos", ""),
                        "Estado": reg.get("estado", ""),
                        "Mensaje_Error": reg.get("mensaje_error", "")
                    }
                    writer.writerow(fila)

            self.log(f"[Export] Historial exportado exitosamente a: {os.path.basename(ruta)} ({len(registros)} registros)")
        except Exception as e:
            self.log(f"[Export] Error al exportar: {e}")

    def toggle(self):
        if self.visible:
            self.ocultar()
        else:
            self.mostrar()

    def mostrar(self):
        self.place(relx=0.98, rely=0.08, anchor="ne")
        self.visible = True
        self.lift()

    def ocultar(self):
        self.place_forget()
        self.visible = False
        # Restaurar a vista de logs si está en historial
        if self._modo_historial:
            self._toggle_historial()
        if self.on_cerrar:
            self.on_cerrar()

    def log(self, texto: str):
        """Escribe una nueva línea en la consola y auto-scrollea al final."""
        self.txt_terminal.insert("end", texto + "\n")
        self.txt_terminal.see("end")
