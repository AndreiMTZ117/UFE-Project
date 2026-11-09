# -*- coding: utf-8 -*-
"""dual canvas rendering coordinator between main canvas and trace point canvas"""


class RenderizadoDualMixin:
    """mixin coordinating dual canvas rendering"""

    def _actualizar_vistas_canvases(self):
        """redraw main and trace point canvases synchronously"""
        #hide temporary framing rect when updating parameters
        if hasattr(self, "panel_general") and hasattr(self.panel_general, "ocultar_frame_dxf"):
            self.panel_general.ocultar_frame_dxf()

        trazos = getattr(self.puente, "trazos_fisicos_cm", self.puente.trazos_calibrados)
        trazos_prev = getattr(self, "trazos_pasadas_previas", [])
        self.panel_general.redibujar(trazos, self.trazos_completados, trazos_prev)
        if hasattr(self.panel_general, '_escala_pixel') and self.panel_general._escala_pixel:
            self.panel_derecho.escala_referencia_px_cm = self.panel_general._escala_pixel
        self.panel_derecho.redibujar_trace(trazos, self.trazos_completados, self.pos_laser_actual, trazos_prev)
