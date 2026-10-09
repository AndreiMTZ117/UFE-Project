# -*- coding: utf-8 -*-
"""
interfaz/gestion_datos.py — CARGA INICIAL Y GESTIÓN DE DATOS

Módulo encargado de la sincronización inicial con SQLite3,
inicialización del hardware Thorlabs GVS112/M y carga de ficheros DXF / G-code.
"""

import os
from tkinter import messagebox
from typing import List, Dict


class GestionDatosMixin:
    """Mixin que gestiona la carga inicial y el enlace de datos."""

    def _cargar_datos_iniciales(self):
        """Carga inicial de recetas de SQLite3, hardware Thorlabs y archivos vectoriales."""
        # 1. Recetas SQLite3
        self.lista_recetas = self.puente.obtener_recetas()
        nombres_recetas = [r["nombre"] for r in self.lista_recetas] if self.lista_recetas else ["Acrílico — Estándar"]
        self.panel_config.set_recetas(nombres_recetas)

        receta_def = self.puente.obtener_receta_default()
        if receta_def:
            self.receta_activa = receta_def
            self.panel_config.set_recetas(nombres_recetas, seleccionada=receta_def["nombre"])
            self.panel_config.poblar_formulario(receta_def)
            from .eventos_interaccion import _RECETAS_PREDETERMINADAS
            es_default = receta_def.get("nombre") in _RECETAS_PREDETERMINADAS
            self.panel_config.set_delete_visible(not es_default)

        # 2. Inicialización de Hardware Thorlabs GVS112/M
        self.puente.conectar_thorlabs()
        modo = getattr(self.puente.controlador_hardware, 'modo', 'SIMULACION')
        self.barra_superior.set_modo_thorlabs(modo)
        if self.puente.esta_conectado_fisico():
            self.terminal.log(f"[HARDWARE] Thorlabs GVS112/M physically connected (REAL PXI-6229)")
        else:
            self.terminal.log(f"[HARDWARE] Thorlabs GVS112/M in VIRTUAL SIMULATION MODE")

        # 3. Archivos DXF / G-code
        dxfs = self.puente.listar_archivos_dxf()
        nombres_dxf = [os.path.basename(f) for f in dxfs]

        # Cargar el primer archivo vectorial disponible
        archivo_sel = dxfs[0] if dxfs else None

        if archivo_sel:
            self.barra_superior.set_lista_dxf(nombres_dxf, seleccionado=os.path.basename(archivo_sel))
            self._cargar_archivo_dxf(archivo_sel)

    def _conectar_com(self, puerto: str):
        """Método de compatibilidad legacy."""
        self.puente.conectar_thorlabs()
        self.barra_superior.set_estado_com(self.puente.esta_conectado_fisico())

    def _cargar_archivo_dxf(self, ruta: str):
        """Lee el archivo DXF o G-code, parametriza trayectorias y actualiza la visualización."""
        try:
            params = self.panel_config.obtener_datos_formulario()
            res = self.puente.cargar_dxf(ruta, params)

            t_est = res.get("tiempo_estimado_s", 0.0)
            n_pts = res.get("n_muestras_daq", 0)
            max_vx = res.get("max_vx", 0.0)
            max_vy = res.get("max_vy", 0.0)

            # Actualizar monitor analítico en el panel derecho
            self.panel_derecho.set_metricas_estimadas(t_est, n_pts, max_vx, max_vy)

            tipo_archivo = "G-CODE" if self.puente.es_gcode else "DXF"
            self.terminal.log(
                f"[{tipo_archivo}] Loaded: {res['archivo']} "
                f"({res['num_trazos']} strokes, {res['num_waypoints']} waypoints | "
                f"Est. Time: {t_est:.3f}s | |V|_max: ±{max(max_vx, max_vy):.2f}V)"
            )

            self.trazos_completados.clear()
            self._aplicar_limites_hardware()
            self._actualizar_vistas_canvases()
            self.panel_derecho.dibujar_gauges(0.0, 0.0, forzar=True)
        except Exception as e:
            messagebox.showerror("File Error", f"Could not load file: {e}")
