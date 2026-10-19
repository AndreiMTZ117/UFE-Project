# -*- coding: utf-8 -*-
"""
interfaz/eventos_interaccion.py — EVENTOS DE INTERACCIÓN

Módulo encargado de responder a las acciones del usuario en la interfaz:
cambios de HAL, selección de puerto COM, selección y apertura de DXF,
visibilidad del terminal flotante, cambios de recetas, sliders de rotación,
definición interactiva del centro (Home) y edición del tamaño de base (Area size).
"""

import os
from tkinter import filedialog, messagebox
import customtkinter as ctk

from .constantes import RECETAS_PREDETERMINADAS
from interfaz.i18n import tr


class EventosInteraccionMixin:
    """Mixin que procesa los eventos y callbacks de la interfaz de usuario."""

    def _on_com_seleccionado(self, val: str):
        """Maneja la detección/re-escaneo del sistema Thorlabs GVS112/M."""
        if hasattr(self.puente, "detectar_hardware"):
            self.puente.detectar_hardware()
        conectado = self.puente.esta_conectado_fisico()
        self.barra_superior.set_estado_com(conectado)
        estado_hw = "Thorlabs GVS112/M" if conectado else "Virtual Simulation"
        self.barra_superior.set_puertos_com([estado_hw], seleccionado=estado_hw)
        modo = "Physical Hardware" if conectado else "Virtual Simulation"
        self.terminal.log(tr("log_hw_mode", mode=modo))

    def _on_click_load_file(self):
        """Opens file browser to select a DXF drawing for CAD/CAM G-code conversion and tracing."""
        if self.puente.en_ejecucion or getattr(self, "_cargando_dxf", False):
            return
        ruta = filedialog.askopenfilename(
            title="Load DXF Drawing",
            filetypes=[("DXF Drawing Files (*.dxf)", "*.dxf"), ("All Files (*.*)", "*.*")]
        )
        if ruta:
            dxfs = self.puente.listar_archivos_dxf()
            nombres = [os.path.basename(f) for f in dxfs]
            if os.path.basename(ruta) not in nombres:
                nombres.append(os.path.basename(ruta))
            self.barra_superior.set_lista_dxf(nombres, seleccionado=os.path.basename(ruta))
            self._cargar_archivo_dxf(ruta)

    def _on_dxf_seleccionado(self, val: str):
        """Loads a selected DXF or triggers file browser."""
        if self.puente.en_ejecucion or getattr(self, "_cargando_dxf", False):
            return
        if val in ("[ Load File... ]", "[ Načíst soubor... ]", tr("dxf_load_file")):
            self._on_click_load_file()
        else:
            dxfs = self.puente.listar_archivos_dxf()
            for f in dxfs:
                if os.path.basename(f) == val:
                    self._cargar_archivo_dxf(f)
                    break

    def _on_toggle_terminal(self):
        """Muestra u oculta la ventana flotante del terminal."""
        self.terminal.toggle()
        self.barra_superior.set_terminal_activo(self.terminal.visible)

    def _on_receta_seleccionada(self, nombre_receta: str):
        """Carga los parámetros de una receta seleccionada en el formulario."""
        if self.puente.en_ejecucion:
            return
        for r in self.lista_recetas:
            if r["nombre"] == nombre_receta:
                self.receta_activa = r
                self.panel_config.poblar_formulario(r)

                # Protección de recetas predeterminadas: ocultar/mostrar botón eliminar
                es_default = nombre_receta in RECETAS_PREDETERMINADAS
                self.panel_config.set_delete_visible(not es_default)

                if self.puente.ruta_dxf_actual:
                    self.puente.recalcular_trayectorias(self.panel_config.obtener_datos_formulario())
                    self._actualizar_vistas_canvases()
                self.terminal.log(tr("log_recipe_sel", name=nombre_receta))
                break

    def _on_rotacion_cambiada(self, angulo: float):
        """Recalcula las trayectorias cuando cambia el ángulo de rotación (0°-360°)."""
        if self.puente.en_ejecucion:
            return
        if self.puente.ruta_dxf_actual:
            self.puente.recalcular_trayectorias(self.panel_config.obtener_datos_formulario())
            self._actualizar_vistas_canvases()

    def _on_parametro_cambiado(self, clave: str, valor: float):
        """Recalcula las trayectorias inmediatamente cuando cambia la escala, rotación o tolerancias en el formulario."""
        if self.puente.en_ejecucion:
            return
        if clave in (
            "escala_dibujo", "rotacion_grados", "tolerancia_rdp", "tolerancia_union",
            "longitud_min_trazo", "invert_x", "invert_y", "swap_xy"
        ):
            if self.puente.ruta_dxf_actual:
                self.puente.recalcular_trayectorias(self.panel_config.obtener_datos_formulario())
                self._actualizar_vistas_canvases()

    def _on_guardar_receta(self):
        """Persiste los cambios del formulario en la receta actual (SQLite3)."""
        if self.puente.en_ejecucion or not self.receta_activa:
            return

        nombre_receta = self.receta_activa.get("nombre", "Recipe")
        confirma = messagebox.askyesno(
            "Save Parameters",
            f"Do you want to save the updated cutting parameters for '{nombre_receta}'?"
        )
        if not confirma:
            return

        datos = self.panel_config.obtener_datos_formulario()
        receta_id = self.receta_activa.get("id")
        try:
            self.puente.guardar_o_actualizar_receta(datos, receta_id)
            messagebox.showinfo("Recipe", f"Recipe '{nombre_receta}' successfully updated.")
            self.terminal.log(tr("log_recipe_saved", id=receta_id, name=nombre_receta))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save recipe: {e}")

    def _on_crear_receta(self):
        """Solicita nombre y crea una nueva receta en la base de datos."""
        if self.puente.en_ejecucion:
            return
        dialog = ctk.CTkInputDialog(text="Enter new recipe name:", title="New Recipe")
        nombre = dialog.get_input()
        if not nombre or not nombre.strip():
            return

        datos = self.panel_config.obtener_datos_formulario()
        datos["nombre"] = nombre.strip()
        datos["polimero"] = "Custom Polymer"

        try:
            nuevo_id = self.puente.guardar_o_actualizar_receta(datos)
            self.lista_recetas = self.puente.obtener_recetas()
            nombres = [r["nombre"] for r in self.lista_recetas]
            self.panel_config.set_recetas(nombres, seleccionada=nombre.strip())
            self.receta_activa = self.puente.obtener_receta_por_id(nuevo_id)
            # Mostrar botón de eliminar para recetas personalizadas
            self.panel_config.set_delete_visible(True)
            messagebox.showinfo("New Recipe", f"Recipe '{nombre}' successfully created.")
        except Exception as e:
            messagebox.showerror("Error", f"Error creating recipe: {e}")

    def _on_eliminar_receta(self):
        """Elimina la receta activa de la base de datos SQLite3 (solo personalizadas)."""
        if self.puente.en_ejecucion or not self.receta_activa:
            return

        nombre = self.receta_activa.get("nombre", "")

        # Proteger recetas predeterminadas
        if nombre in RECETAS_PREDETERMINADAS:
            messagebox.showwarning(
                "Protected Recipe",
                f"Recipe '{nombre}' is a factory preset and cannot be deleted.\n\n"
                "Only custom recipes created by the user can be deleted."
            )
            return

        receta_id = self.receta_activa.get("id")

        confirma = messagebox.askyesno("Confirm Deletion", f"Delete recipe '{nombre}' from the database?")
        if confirma:
            exito = self.puente.eliminar_receta(receta_id)
            if exito:
                self.lista_recetas = self.puente.obtener_recetas()
                nombres = [r["nombre"] for r in self.lista_recetas]
                self.panel_config.set_recetas(nombres)
                if self.lista_recetas:
                    self._on_receta_seleccionada(self.lista_recetas[0]["nombre"])
                self.terminal.log(tr("log_recipe_deleted", name=nombre))
                messagebox.showinfo("Deleted", f"Recipe '{nombre}' deleted.")

    def _on_centro_cambiado(self, x: float, y: float):
        """Actualiza el centro de reposo de la máquina y posiciona el puntero (alteración manual)."""
        if self.puente.en_ejecucion:
            return
        self.puente.set_centro_cm(x, y)
        self.pos_laser_actual = (x, y)
        self.panel_general.set_centro(x, y)
        self.panel_derecho.actualizar_coordenadas(x, y)
        if not self.puente.en_ejecucion:
            self.puente.centrar_galvos()
        self.terminal.log(tr("log_home_set", x=x, y=y))
        if self.puente.ruta_dxf_actual:
            self.puente.recalcular_trayectorias(self.panel_config.obtener_datos_formulario())
        self._actualizar_vistas_canvases()

    def _on_dimensiones_cambiadas(self, ancho_cm: float, alto_cm: float):
        """Actualiza las dimensiones de la base física de trabajo, recalcula el centro automáticamente y trazos."""
        if self.puente.en_ejecucion:
            return
        self.puente.set_dimensiones_base(ancho_cm, alto_cm)
        cx = self.puente.centro_cm_x
        cy = self.puente.centro_cm_y
        self.pos_laser_actual = (cx, cy)
        self.panel_derecho.set_centro(cx, cy)
        self.panel_general.set_centro(cx, cy)
        self.panel_derecho.actualizar_coordenadas(cx, cy)

        if self.puente.ruta_dxf_actual:
            self.puente.recalcular_trayectorias(self.panel_config.obtener_datos_formulario())
            self._actualizar_vistas_canvases()
            self.terminal.log(tr("log_base_recalc", w=ancho_cm, h=alto_cm, cx=cx, cy=cy))
        else:
            self._actualizar_vistas_canvases()
            self.terminal.log(tr("log_base_set", w=ancho_cm, h=alto_cm, cx=cx, cy=cy))

    def _aplicar_limites_hardware(self):
        """Aplica los límites dinámicos de la máquina al panel general para renderizado correcto."""
        self.panel_general.set_limites_hardware(
            self.puente.x_min_limit,
            self.puente.x_max_limit,
            self.puente.y_min_limit,
            self.puente.y_max_limit
        )

