# -*- coding: utf-8 -*-
"""
interfaz/eventos_interaccion.py — EVENTOS DE INTERACCIÓN

Módulo encargado de responder a las acciones del usuario en la interfaz:
selección y apertura de DXF / G-code, visibilidad del terminal flotante,
cambios de recetas, sliders de rotación, definición interactiva del centro (Home)
y edición del tamaño de base (Area size).
"""

import os
from tkinter import filedialog, messagebox
import customtkinter as ctk

# Nombres de las recetas predeterminadas que no pueden eliminarse
_RECETAS_PREDETERMINADAS = {
    "Acrílico — Estándar",
    "Policarbonato — Alta Precisión",
    "Nylon — Grabado Suave",
    "Thorlabs — Prueba Vectorial",
}


class EventosInteraccionMixin:
    """Mixin que procesa los eventos y callbacks de la interfaz de usuario."""

    def _on_hal_cambiado(self, val: str = "thorlabs_galvo"):
        """Maneja la selección de HAL (Thorlabs GVS112/M nativo)."""
        self.puente.cambiar_hardware("thorlabs_galvo")
        self.barra_superior.set_modo_thorlabs(
            'REAL' if self.puente.esta_conectado_fisico() else 'SIMULACION'
        )
        self._aplicar_limites_hardware()
        self.panel_derecho.set_centro(self.puente.centro_cm_x, self.puente.centro_cm_y)
        self.panel_derecho.actualizar_coordenadas(self.puente.centro_cm_x, self.puente.centro_cm_y)
        self.panel_general.actualizar_dimensiones(self.puente.ancho_base_cm, self.puente.alto_base_cm)
        if self.puente.ruta_dxf_actual:
            self.puente.recalcular_trayectorias(self.panel_config.obtener_datos_formulario())
            self._actualizar_vistas_canvases()

    def _on_com_seleccionado(self, val: str):
        """Stub de compatibilidad."""
        pass

    def _on_dxf_seleccionado(self, val: str):
        """Carga un DXF/G-code existente o abre el explorador del sistema."""
        if val == "[ Open Explorer... ]":
            ruta = filedialog.askopenfilename(
                title="Seleccionar archivo DXF o G-code",
                filetypes=[
                    ("Archivos Vectoriales y G-code", "*.dxf *.gcode *.nc *.ngc"),
                    ("Archivos DXF (*.dxf)", "*.dxf"),
                    ("Archivos G-code (*.gcode, *.nc, *.ngc)", "*.gcode *.nc *.ngc"),
                    ("Todos los archivos", "*.*")
                ]
            )
            if ruta:
                dxfs = self.puente.listar_archivos_dxf()
                nombres = [os.path.basename(f) for f in dxfs]
                if os.path.basename(ruta) not in nombres:
                    nombres.append(os.path.basename(ruta))
                self.barra_superior.set_lista_dxf(nombres, seleccionado=os.path.basename(ruta))
                self._cargar_archivo_dxf(ruta)
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
        for r in self.lista_recetas:
            if r["nombre"] == nombre_receta:
                self.receta_activa = r
                self.panel_config.poblar_formulario(r)

                es_default = nombre_receta in _RECETAS_PREDETERMINADAS
                self.panel_config.set_delete_visible(not es_default)

                if self.puente.ruta_dxf_actual:
                    self.puente.recalcular_trayectorias(self.panel_config.obtener_datos_formulario())
                    self._actualizar_vistas_canvases()
                self.terminal.log(f"[Receta] Seleccionada: {nombre_receta}")
                break

    def _on_rotacion_cambiada(self, angulo: float):
        """Recalcula las trayectorias cuando cambia el ángulo de rotación (0°-360°)."""
        if self.puente.ruta_dxf_actual:
            self.puente.recalcular_trayectorias(self.panel_config.obtener_datos_formulario())
            self._actualizar_vistas_canvases()

    def _on_guardar_receta(self):
        """Persiste los cambios del formulario en la receta actual (SQLite3)."""
        if not self.receta_activa:
            return
        datos = self.panel_config.obtener_datos_formulario()
        receta_id = self.receta_activa.get("id")
        try:
            self.puente.guardar_o_actualizar_receta(datos, receta_id)
            messagebox.showinfo("Receta", f"Receta '{self.receta_activa['nombre']}' actualizada con éxito.")
            self.terminal.log(f"[Recetas] Receta ID={receta_id} guardada en SQLite3.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la receta: {e}")

    def _on_crear_receta(self):
        """Solicita nombre y crea una nueva receta en la base de datos."""
        dialog = ctk.CTkInputDialog(text="Introduce el nombre de la nueva receta:", title="Nueva Receta")
        nombre = dialog.get_input()
        if not nombre or not nombre.strip():
            return

        datos = self.panel_config.obtener_datos_formulario()
        datos["nombre"] = nombre.strip()
        datos["polimero"] = "Polímero Personalizado"

        try:
            nuevo_id = self.puente.guardar_o_actualizar_receta(datos)
            self.lista_recetas = self.puente.obtener_recetas()
            nombres = [r["nombre"] for r in self.lista_recetas]
            self.panel_config.set_recetas(nombres, seleccionada=nombre.strip())
            self.receta_activa = self.puente.obtener_receta_por_id(nuevo_id)
            self.panel_config.set_delete_visible(True)
            messagebox.showinfo("Nueva Receta", f"Receta '{nombre}' creada con éxito.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al crear receta: {e}")

    def _on_eliminar_receta(self):
        """Elimina la receta activa de la base de datos SQLite3 (solo personalizadas)."""
        if not self.receta_activa:
            return

        nombre = self.receta_activa.get("nombre", "")

        if nombre in _RECETAS_PREDETERMINADAS:
            messagebox.showwarning(
                "Receta Protegida",
                f"La receta '{nombre}' es una receta de fábrica y no puede eliminarse.\n\n"
                "Solo las recetas personalizadas creadas por el usuario pueden ser eliminadas."
            )
            return

        receta_id = self.receta_activa.get("id")

        confirma = messagebox.askyesno("Confirmar eliminación", f"¿Eliminar la receta '{nombre}' de la base de datos?")
        if confirma:
            exito = self.puente.eliminar_receta(receta_id)
            if exito:
                self.lista_recetas = self.puente.obtener_recetas()
                nombres = [r["nombre"] for r in self.lista_recetas]
                self.panel_config.set_recetas(nombres)
                if self.lista_recetas:
                    self._on_receta_seleccionada(self.lista_recetas[0]["nombre"])
                messagebox.showinfo("Eliminada", f"Receta '{nombre}' eliminada.")

    def _on_centro_cambiado(self, x: float, y: float):
        """Actualiza el centro de reposo de la máquina y posiciona los espejos."""
        self.puente.set_centro_cm(x, y)
        self.pos_laser_actual = (x, y)
        self.panel_derecho.actualizar_coordenadas(x, y)
        if not self.puente.en_ejecucion:
            self.puente.centrar_espejos()
        self.terminal.log(f"[HOME] Centro manual definido a: ({x:.2f}, {y:.2f}) cm")
        if self.puente.ruta_dxf_actual:
            self.puente.recalcular_trayectorias(self.panel_config.obtener_datos_formulario())
        self._actualizar_vistas_canvases()

    def _on_dimensiones_cambiadas(self, ancho_cm: float, alto_cm: float):
        """Actualiza las dimensiones del campo óptico de trabajo, recalcula centro y trazos."""
        self.puente.set_dimensiones_base(ancho_cm, alto_cm)
        cx = self.puente.centro_cm_x
        cy = self.puente.centro_cm_y
        self.pos_laser_actual = (cx, cy)
        self.panel_derecho.set_centro(cx, cy)
        self.panel_derecho.actualizar_coordenadas(cx, cy)

        if self.puente.ruta_dxf_actual:
            self.puente.recalcular_trayectorias(self.panel_config.obtener_datos_formulario())
            self._actualizar_vistas_canvases()
            self.terminal.log(f"[Campo] Dimensiones: {ancho_cm:.1f} x {alto_cm:.1f} cm | Centro: ({cx:.2f}, {cy:.2f}) cm. Trazos actualizados.")
        else:
            self._actualizar_vistas_canvases()
            self.terminal.log(f"[Campo] Dimensiones: {ancho_cm:.1f} x {alto_cm:.1f} cm | Centro: ({cx:.2f}, {cy:.2f}) cm.")

    def _aplicar_limites_hardware(self):
        """Aplica los límites dinámicos de la máquina al panel general para renderizado correcto."""
        self.panel_general.set_limites_hardware(
            self.puente.x_min_limit,
            self.puente.x_max_limit,
            self.puente.y_min_limit,
            self.puente.y_max_limit
        )
