# -*- coding: utf-8 -*-
"""
interfaz/renderizado_dual.py — RENDERIZADO DUAL EN CANVAS (CYBER-BRUTALISM)

Módulo encargado de la sincronización gráfica simultánea entre:
1. Panel General (Canvas 1:1 con reglas graduadas en centímetros, base DXF y trazos cortados).
2. Panel Derecho (Canvas Trace Point con zoom 4x centrado en la cabeza láser y halo cian).
"""


class RenderizadoDualMixin:
    """Mixin que coordina el redibujado dual de los canvases."""

    def _actualizar_vistas_canvases(self):
        """Redibuja en sincronía el Canvas General y el Canvas Trace Point."""
        trazos = getattr(self.puente, "trazos_fisicos_cm", self.puente.trazos_calibrados)
        self.panel_general.redibujar(trazos, self.trazos_completados)
        self.panel_derecho.redibujar_trace(trazos, self.trazos_completados, self.pos_laser_actual)
