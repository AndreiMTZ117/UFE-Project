# -*- coding: utf-8 -*-
"""
interfaz/renderizado_dual.py - RENDERIZADO DUAL EN CANVAS (CYBER-BRUTALISM)

Coordina el redibujado entre:
1. Panel General (Canvas 1:1 con reglas, base DXF - INCREMENTAL durante ejecucion).
2. Panel Derecho (Canvas Trace Point con zoom 4x centrado en la cabeza laser).
"""


class RenderizadoDualMixin:
    """Mixin que coordina el redibujado dual de los canvases."""

    def _actualizar_vistas_canvases(self):
        """
        Redibuja en sincronía el Canvas General y el Canvas Trace Point.

        El Canvas General hace un redibujado COMPLETO de la figura base.
        Se usa al cargar un DXF, cambiar receta o cambiar parametros.
        Durante la ejecucion activa, el progreso se dibuja incrementalmente
        via panel_general.agregar_segmento_completado (sin redibujar todo).
        """
        # Desaparecer el marco delimitador temporal al modificar parametros, receta o cargar nuevo DXF
        if hasattr(self, "panel_general") and hasattr(self.panel_general, "ocultar_frame_dxf"):
            self.panel_general.ocultar_frame_dxf()

        trazos = getattr(self.puente, "trazos_fisicos_cm", self.puente.trazos_calibrados)
        self.panel_general.redibujar(trazos, self.trazos_completados)
        if hasattr(self.panel_general, '_escala_pixel') and self.panel_general._escala_pixel:
            self.panel_derecho.escala_referencia_px_cm = self.panel_general._escala_pixel
        self.panel_derecho.redibujar_trace(trazos, self.trazos_completados, self.pos_laser_actual)
