# -*- coding: utf-8 -*-
"""initial data loading and synchronization for sqlite3 hardware and dxf"""

import os
import threading
from tkinter import messagebox
from interfaz.i18n import tr


class GestionDatosMixin:
    """mixin for initial data loading and binding"""

    def _cargar_datos_iniciales(self):
        """initial load of sqlite3 recipes hardware state and dxf files"""
        #sqlite3 recipes
        self.lista_recetas = self.puente.get_recipes()
        nombres_recetas = [r["nombre"] for r in self.lista_recetas] if self.lista_recetas else ["Acrylic — Standard"]
        self.panel_config.set_recetas(nombres_recetas)

        receta_def = self.puente.get_default_recipe()
        if receta_def:
            self.receta_activa = receta_def
            self.panel_config.set_recetas(nombres_recetas, seleccionada=receta_def["nombre"])
            self.panel_config.poblar_formulario(receta_def)
            from .constantes import RECETAS_PREDETERMINADAS
            es_default = receta_def.get("nombre") in RECETAS_PREDETERMINADAS
            self.panel_config.set_delete_visible(not es_default)

        #hardware state
        conectado_fisico = self.puente.is_physically_connected()
        self.barra_superior.set_estado_com(conectado_fisico)
        if conectado_fisico:
            self.terminal.log(tr("log_hw_connected"))
        else:
            self.terminal.log(tr("log_hw_sim"))

        #display state in com port selector
        self._refrescar_selector_hw()

        #dxf files
        dxfs = self.puente.list_dxf_files()
        nombres_dxf = [os.path.basename(f) for f in dxfs]

        archivo_sel = dxfs[0] if dxfs else None

        if archivo_sel:
            self.barra_superior.set_lista_dxf(nombres_dxf, seleccionado=os.path.basename(archivo_sel))
            self._cargar_archivo_dxf(archivo_sel, asincrono=False)

    def _cargar_archivo_dxf(self, ruta: str, asincrono: bool = True):
        """load dxf file synchronously or asynchronously in background thread"""
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
            self.trazos_pasadas_previas.clear()
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
                res = self.puente.load_dxf(ruta, params)
                _aplicar_exito(res)
            except Exception as e:
                _aplicar_error(e)
            return

        def worker():
            try:
                res = self.puente.load_dxf(ruta, params)
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
