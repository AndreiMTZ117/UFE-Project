# -*- coding: utf-8 -*-
"""
interfaz/gestion_datos.py — CARGA INICIAL Y GESTIÓN DE DATOS

Módulo encargado de la sincronización inicial con SQLite3,
detección y conexión de puertos serie COM, y carga de ficheros DXF.
"""

import os
from tkinter import messagebox
from typing import List, Dict


class GestionDatosMixin:
    """Mixin que gestiona la carga inicial y el enlace de datos."""

    def _cargar_datos_iniciales(self):
        """Carga inicial de recetas de SQLite3, puertos seriales y archivos DXF."""
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

        # 2. Puertos COM
        puertos = self.puente.listar_puertos_com()
        if puertos:
            self.barra_superior.set_puertos_com(puertos, seleccionado=puertos[0])
            self._conectar_com(puertos[0])
        else:
            self.barra_superior.set_puertos_com([], seleccionado=None)

        # 3. Archivos DXF
        dxfs = self.puente.listar_archivos_dxf()
        nombres_dxf = [os.path.basename(f) for f in dxfs]

        # Cargar el primer archivo DXF disponible
        archivo_sel = dxfs[0] if dxfs else None

        if archivo_sel:
            self.barra_superior.set_lista_dxf(nombres_dxf, seleccionado=os.path.basename(archivo_sel))
            self._cargar_archivo_dxf(archivo_sel)

    def _conectar_com(self, puerto: str):
        """Conecta o selecciona el puerto serial COM."""
        exito = self.puente.conectar_puerto(puerto)
        self.barra_superior.set_estado_com(exito)
        if exito:
            self.terminal.log(f"[COM] Conectado físicamente a {self.puente.obtener_nombre_hardware()} en {puerto}")
        else:
            self.terminal.log(f"[COM] Puerto {puerto} seleccionado (Modo Simulación / Sin hardware)")

    def _cargar_archivo_dxf(self, ruta: str):
        """Lee el DXF, parametriza trayectorias y actualiza la visualización."""
        try:
            params = self.panel_config.obtener_datos_formulario()
            res = self.puente.cargar_dxf(ruta, params)
            self.terminal.log(f"[DXF] Cargado: {res['archivo']} ({res['num_trazos']} trazos, {res['num_waypoints']} waypoints)")
            self.trazos_completados.clear()
            self._aplicar_limites_hardware()
            self._actualizar_vistas_canvases()
            self.panel_derecho.dibujar_gauges(0.0, 0.0)
        except Exception as e:
            messagebox.showerror("Error DXF", f"No se pudo cargar el DXF: {e}")
