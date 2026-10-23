# -*- coding: utf-8 -*-
"""gui interaction event handlers and callbacks"""

import os
from tkinter import filedialog, messagebox
import customtkinter as ctk

from .constantes import RECETAS_PREDETERMINADAS
from interfaz.i18n import tr


class EventosInteraccionMixin:
    """mixin processing user interface events and callbacks"""

    def _on_com_seleccionado(self, val: str):
        """handle hardware detection and rescan"""
        if hasattr(self.puente, "detect_hardware"):
            self.puente.detect_hardware()
        conectado = self.puente.is_physically_connected()
        self.barra_superior.set_estado_com(conectado)
        estado_hw = "Thorlabs GVS112/M" if conectado else "Virtual Simulation"
        self.barra_superior.set_puertos_com([estado_hw], seleccionado=estado_hw)
        modo = "Physical Hardware" if conectado else "Virtual Simulation"
        self.terminal.log(tr("log_hw_mode", mode=modo))
        if hasattr(self, "_iniciar_feedback_ui"):
            self._iniciar_feedback_ui()

    def _on_click_load_file(self):
        """open file browser to select dxf drawing"""
        if self.puente.is_running or getattr(self, "_cargando_dxf", False):
            return
        ruta = filedialog.askopenfilename(
            title="Load DXF Drawing",
            filetypes=[("DXF Drawing Files (*.dxf)", "*.dxf"), ("All Files (*.*)", "*.*")]
        )
        if ruta:
            dxfs = self.puente.list_dxf_files()
            nombres = [os.path.basename(f) for f in dxfs]
            if os.path.basename(ruta) not in nombres:
                nombres.append(os.path.basename(ruta))
            self.barra_superior.set_lista_dxf(nombres, seleccionado=os.path.basename(ruta))
            self._cargar_archivo_dxf(ruta)

    def _on_dxf_seleccionado(self, val: str):
        """load selected dxf file or trigger browser"""
        if self.puente.is_running or getattr(self, "_cargando_dxf", False):
            return
        if val in ("[ Load File... ]", "[ Načíst soubor... ]", tr("dxf_load_file")):
            self._on_click_load_file()
        else:
            dxfs = self.puente.list_dxf_files()
            for f in dxfs:
                if os.path.basename(f) == val:
                    self._cargar_archivo_dxf(f)
                    break

    def _on_toggle_terminal(self):
        """toggle floating terminal window visibility"""
        self.terminal.toggle()
        self.barra_superior.set_terminal_activo(self.terminal.visible)

    def _on_receta_seleccionada(self, nombre_receta: str):
        """load selected recipe parameters into form"""
        if self.puente.is_running:
            return
        for r in self.lista_recetas:
            if r["nombre"] == nombre_receta:
                self.receta_activa = r
                self.panel_config.poblar_formulario(r)

                #protect factory recipes by toggling delete button
                es_default = nombre_receta in RECETAS_PREDETERMINADAS
                self.panel_config.set_delete_visible(not es_default)

                if self.puente.ruta_dxf_actual:
                    self.puente.recalculate_paths(self.panel_config.obtener_datos_formulario())
                    self._actualizar_vistas_canvases()
                self.terminal.log(tr("log_recipe_sel", name=nombre_receta))
                break

    def _on_rotacion_cambiada(self, angulo: float):
        """recalculate paths when rotation angle changes"""
        if self.puente.is_running:
            return
        if self.puente.ruta_dxf_actual:
            self.puente.recalculate_paths(self.panel_config.obtener_datos_formulario())
            self._actualizar_vistas_canvases()

    def _on_parametro_cambiado(self, clave: str, valor: float):
        """recalculate paths when scale rotation or tolerances change"""
        if self.puente.is_running:
            return
        if clave in (
            "escala_dibujo", "rotacion_grados", "tolerancia_rdp", "tolerancia_union",
            "longitud_min_trazo", "invert_x", "invert_y", "swap_xy"
        ):
            if self.puente.ruta_dxf_actual:
                self.puente.recalculate_paths(self.panel_config.obtener_datos_formulario())
                self._actualizar_vistas_canvases()

    def _on_guardar_receta(self):
        """persist form changes to active recipe in sqlite3"""
        if self.puente.is_running or not self.receta_activa:
            return

        nombre_receta = self.receta_activa.get("nombre", "Recipe")
        confirma = messagebox.askyesno(
            tr("dlg_save_recipe_title"),
            tr("dlg_save_recipe_msg", name=nombre_receta)
        )
        if not confirma:
            return

        datos = self.panel_config.obtener_datos_formulario()
        receta_id = self.receta_activa.get("id")
        try:
            self.puente.save_or_update_recipe(datos, receta_id)
            messagebox.showinfo(tr("dlg_save_recipe_title"), tr("dlg_save_recipe_ok", name=nombre_receta))
            self.terminal.log(tr("log_recipe_saved", id=receta_id, name=nombre_receta))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save recipe: {e}")

    def _on_crear_receta(self):
        """prompt for name and create new recipe in database"""
        if self.puente.is_running:
            return
        dialog = ctk.CTkInputDialog(text=tr("dlg_new_recipe_prompt"), title=tr("dlg_new_recipe_title"))
        nombre = dialog.get_input()
        if not nombre or not nombre.strip():
            return

        datos = self.panel_config.obtener_datos_formulario()
        datos["nombre"] = nombre.strip()
        datos["polimero"] = "Custom Polymer"

        try:
            nuevo_id = self.puente.save_or_update_recipe(datos)
            self.lista_recetas = self.puente.get_recipes()
            nombres = [r["nombre"] for r in self.lista_recetas]
            self.panel_config.set_recetas(nombres, seleccionada=nombre.strip())
            self.receta_activa = self.puente.get_recipe_by_id(nuevo_id)
            #show delete button for custom recipes
            self.panel_config.set_delete_visible(True)
            messagebox.showinfo(tr("dlg_new_recipe_title"), tr("dlg_new_recipe_ok", name=nombre))
        except Exception as e:
            messagebox.showerror("Error", f"Error creating recipe: {e}")

    def _on_eliminar_receta(self):
        """delete active recipe from database"""
        if self.puente.is_running or not self.receta_activa:
            return

        nombre = self.receta_activa.get("nombre", "")

        #protect factory recipes
        if nombre in RECETAS_PREDETERMINADAS:
            messagebox.showwarning(
                tr("dlg_protected_recipe_title"),
                tr("dlg_protected_recipe_msg", name=nombre)
            )
            return

        receta_id = self.receta_activa.get("id")

        confirma = messagebox.askyesno(tr("dlg_del_recipe_title"), tr("dlg_del_recipe_msg", name=nombre))
        if confirma:
            exito = self.puente.delete_recipe(receta_id)
            if exito:
                self.lista_recetas = self.puente.get_recipes()
                nombres = [r["nombre"] for r in self.lista_recetas]
                self.panel_config.set_recetas(nombres)
                if self.lista_recetas:
                    self._on_receta_seleccionada(self.lista_recetas[0]["nombre"])
                self.terminal.log(tr("log_recipe_deleted", name=nombre))
                messagebox.showinfo(tr("dlg_del_recipe_title"), tr("dlg_del_recipe_ok", name=nombre))

    def _on_centro_cambiado(self, x: float, y: float):
        """update resting center and pointer position"""
        if self.puente.is_running:
            return
        self.puente.set_center_cm(x, y)
        self.pos_laser_actual = (x, y)
        self.panel_general.set_centro(x, y)
        self.panel_derecho.actualizar_coordenadas(x, y)
        if not self.puente.is_running:
            self.puente.center_galvos()
        self.terminal.log(tr("log_home_set", x=x, y=y))
        if self.puente.ruta_dxf_actual:
            self.puente.recalculate_paths(self.panel_config.obtener_datos_formulario())
        self._actualizar_vistas_canvases()

    def _on_dimensiones_cambiadas(self, ancho_cm: float, alto_cm: float):
        """update physical base dimensions and recalculate center"""
        if self.puente.is_running:
            return
        self.puente.set_base_dimensions(ancho_cm, alto_cm)
        cx = self.puente.centro_cm_x
        cy = self.puente.centro_cm_y
        self.pos_laser_actual = (cx, cy)
        self.panel_derecho.set_centro(cx, cy)
        self.panel_general.set_centro(cx, cy)
        self.panel_derecho.actualizar_coordenadas(cx, cy)

        if self.puente.ruta_dxf_actual:
            self.puente.recalculate_paths(self.panel_config.obtener_datos_formulario())
            self._actualizar_vistas_canvases()
            self.terminal.log(tr("log_base_recalc", w=ancho_cm, h=alto_cm, cx=cx, cy=cy))
        else:
            self._actualizar_vistas_canvases()
            self.terminal.log(tr("log_base_set", w=ancho_cm, h=alto_cm, cx=cx, cy=cy))

    def _aplicar_limites_hardware(self):
        """apply dynamic hardware limits to canvas"""
        self.panel_general.set_limites_hardware(
            self.puente.x_min_limit,
            self.puente.x_max_limit,
            self.puente.y_min_limit,
            self.puente.y_max_limit
        )

