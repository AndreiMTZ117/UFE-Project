# -*- coding: utf-8 -*-
"""
interfaz/gestion_datos.py - CARGA INICIAL Y GESTION DE DATOS

Modulo encargado de la sincronizacion inicial con SQLite3,
estado del hardware Thorlabs GVS112/M y carga de ficheros DXF.
"""

import os
import threading
from tkinter import messagebox
from interfaz.i18n import tr


class GestionDatosMixin:
    """Mixin que gestiona la carga inicial y el enlace de datos."""

    def _cargar_datos_iniciales(self):
        """Carga inicial de recetas de SQLite3, estado del hardware y archivos DXF."""
        # 1. Recetas SQLite3
        self.lista_recetas = self.puente.obtener_recetas()
        nombres_recetas = [r["nombre"] for r in self.lista_recetas] if self.lista_recetas else ["Acrylic — Standard"]
        self.panel_config.set_recetas(nombres_recetas)

        receta_def = self.puente.obtener_receta_default()
        if receta_def:
            self.receta_activa = receta_def
            self.panel_config.set_recetas(nombres_recetas, seleccionada=receta_def["nombre"])
            self.panel_config.poblar_formulario(receta_def)
            from .constantes import RECETAS_PREDETERMINADAS
            es_default = receta_def.get("nombre") in RECETAS_PREDETERMINADAS
            self.panel_config.set_delete_visible(not es_default)

        # 2. Estado del hardware Thorlabs GVS112/M
        conectado_fisico = self.puente.esta_conectado_fisico()
        self.barra_superior.set_estado_com(conectado_fisico)
        if conectado_fisico:
            self.terminal.log(tr("log_hw_connected"))
        else:
            self.terminal.log(tr("log_hw_sim"))

        # Mostrar estado en el selector de puertos COM
        estado_hw = "Thorlabs GVS112/M" if conectado_fisico else "Virtual Simulation"
        self.barra_superior.set_puertos_com([estado_hw], seleccionado=estado_hw)

        # 3. Archivos DXF
        dxfs = self.puente.listar_archivos_dxf()
        nombres_dxf = [os.path.basename(f) for f in dxfs]

        archivo_sel = dxfs[0] if dxfs else None

        if archivo_sel:
            self.barra_superior.set_lista_dxf(nombres_dxf, seleccionado=os.path.basename(archivo_sel))
            self._cargar_archivo_dxf(archivo_sel, asincrono=False)

    def _cargar_archivo_dxf(self, ruta: str, asincrono: bool = True):
        """Carga de DXF: ejecuta CADConverter, GCodeParser y PathOptimizer.
        
        Si asincrono=True se ejecuta en segundo plano para evitar congelar la GUI interactiva.
        Si asincrono=False se ejecuta en el hilo actual (ideal para inicializacion de arranque).
        """
        if getattr(self, "_cargando_dxf", False):
            return

        self._cargando_dxf = True
        if hasattr(self, "barra_superior") and hasattr(self.barra_superior, "set_bloqueo_carga"):
            self.barra_superior.set_bloqueo_carga(True)

        if hasattr(self, "terminal"):
            self.terminal.log(tr("log_dxf_loading"))

        params = self.panel_config.obtener_datos_formulario()

        def _aplicar_exito(res):
            self._cargando_dxf = False
            if hasattr(self, "barra_superior") and hasattr(self.barra_superior, "set_bloqueo_carga"):
                self.barra_superior.set_bloqueo_carga(False)
            if hasattr(self, "terminal"):
                archivo = res.get('archivo', os.path.basename(ruta))
                paths = res.get('num_trazos', 0)
                points = res.get('num_waypoints', 0)
                self.terminal.log(tr("log_dxf_loaded", file=archivo, paths=paths, points=points))
            self.trazos_completados.clear()
            self.panel_general.limpiar_completados()
            self.panel_derecho.limpiar_progreso()
            self._aplicar_limites_hardware()
            self._actualizar_vistas_canvases()
            self.panel_derecho.dibujar_gauges(0.0, 0.0)

        def _aplicar_error(e):
            self._cargando_dxf = False
            if hasattr(self, "barra_superior") and hasattr(self.barra_superior, "set_bloqueo_carga"):
                self.barra_superior.set_bloqueo_carga(False)
            if hasattr(self, "terminal"):
                self.terminal.log(tr("log_dxf_err", file=os.path.basename(ruta), err=e))
            messagebox.showerror("DXF Error", f"Failed to load DXF file: {e}")

        if not asincrono:
            try:
                res = self.puente.cargar_dxf(ruta, params)
                _aplicar_exito(res)
            except Exception as e:
                _aplicar_error(e)
            return

        def worker():
            try:
                res = self.puente.cargar_dxf(ruta, params)
                try:
                    self.after(0, _aplicar_exito, res)
                except Exception:
                    _aplicar_exito(res)
            except Exception as e:
                try:
                    self.after(0, _aplicar_error, e)
                except Exception:
                    _aplicar_error(e)

        threading.Thread(target=worker, daemon=True).start()
