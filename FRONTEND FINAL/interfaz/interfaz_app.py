# -*- coding: utf-8 -*-
"""main orchestrator for ufe laser workstation gui"""

import os
import sys
import customtkinter as ctk
from typing import Dict, List, Tuple, Optional

#project paths
_DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
_DIR_RAIZ = os.path.abspath(os.path.join(_DIR_ACTUAL, ".."))
if _DIR_RAIZ not in sys.path:
    sys.path.insert(0, _DIR_RAIZ)

#design constants
from interfaz.constantes import (
    COLOR_BG,
    cargar_fuentes_windows,
    configurar_dpi_awareness
)

#initialize system config and truetype fonts
configurar_dpi_awareness()
cargar_fuentes_windows()

#backend bridge
from interfaz.conexion_interfaz import PuenteLaser
from interfaz.i18n import tr

#visual components
from interfaz.barra_superior import BarraSuperior
from interfaz.panel_configuracion import PanelConfiguracion
from interfaz.panel_general import PanelGeneral
from interfaz.panel_derecho import PanelDerecho
from interfaz.terminal_flotante import TerminalFlotante

#logic and event mixins
from interfaz.gestion_datos import GestionDatosMixin
from interfaz.eventos_interaccion import EventosInteraccionMixin
from interfaz.renderizado_dual import RenderizadoDualMixin
from interfaz.logica_ejecucion import LogicaEjecucionMixin


class AppLaserCTk(
    ctk.CTk,
    GestionDatosMixin,
    EventosInteraccionMixin,
    RenderizadoDualMixin,
    LogicaEjecucionMixin
):
    """main application window for ufe laser workstation"""

    def __init__(self):
        super().__init__()

        #window configuration
        self.title("Thorlabs GVS112/M — Industrial Galvanometer Laser Workstation")
        self.geometry("1280x760")
        self.minsize(1150, 700)
        ctk.set_appearance_mode("light")
        self.configure(fg_color=COLOR_BG)

        #backend bridge
        self.puente = PuenteLaser()
        self.puente.on_alerta_hw_cb = self._cb_alerta_hw
        self.receta_activa: Dict = {}
        self.lista_recetas: List[Dict] = []

        #telemetry and execution state
        self.tiempo_inicio_ejecucion = 0.0
        self.tiempo_pausa_acumulado = 0.0
        self.tiempo_ultima_pausa = 0.0
        self.pos_laser_actual = (self.puente.ancho_base_cm / 2.0, self.puente.alto_base_cm / 2.0)
        self.trazos_completados: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        self.trazos_pasadas_previas: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []

        #build layout
        self._construir_layout()

        #initial data loading
        self._cargar_datos_iniciales()

        #set initial limits center and dimensions
        self._aplicar_limites_hardware()
        self._iniciar_feedback_ui()
        self.panel_derecho.set_centro(self.puente.centro_cm_x, self.puente.centro_cm_y)
        self.panel_general.set_centro(self.puente.centro_cm_x, self.puente.centro_cm_y)
        self.panel_derecho.actualizar_coordenadas(self.puente.centro_cm_x, self.puente.centro_cm_y)
        self.panel_general.actualizar_dimensiones(self.puente.ancho_base_cm, self.puente.alto_base_cm)

        #timer loop
        self._actualizar_timer_loop()

        #safe window close handler
        self.protocol("WM_DELETE_WINDOW", self._on_cerrar_aplicacion)

    def _on_cerrar_aplicacion(self):
        """safely release hardware resources and close application"""
        if getattr(self, '_cerrando', False):
            return
        self._cerrando = True

        #disable close protocol to avoid reentrancy
        try:
            self.protocol("WM_DELETE_WINDOW", lambda: None)
        except Exception:
            pass

        #cancel scheduled timer
        if hasattr(self, '_timer_after_id') and self._timer_after_id:
            try:
                self.after_cancel(self._timer_after_id)
            except Exception:
                pass

        #stop execution and turn off laser
        try:
            if hasattr(self, 'puente'):
                if self.puente.is_running:
                    self.puente.stop_execution()
                if self.puente.controlador_hardware:
                    try:
                        self.puente.laser_off()
                        self.puente.controlador_hardware.cerrar()
                    except Exception:
                        pass
        except Exception:
            pass

        #destroy window safely
        try:
            self.destroy()
        except Exception:
            pass

    #layout construction
    def _construir_layout(self):
        #top bar
        self.barra_superior = BarraSuperior(
            self,
            on_com_seleccionado=self._on_com_seleccionado,
            on_dxf_seleccionado=self._on_dxf_seleccionado,
            on_load_file_click=self._on_click_load_file,
            on_toggle_terminal=self._on_toggle_terminal,
            on_idioma_cambiado=self._on_idioma_cambiado,
            on_feedback_toggle=self._on_feedback_toggle
        )
        self.barra_superior.pack(fill="x", padx=16, pady=(10, 4))

        #central frame
        self.frame_cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_cuerpo.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        self.frame_cuerpo.grid_columnconfigure(0, weight=0, minsize=265)
        self.frame_cuerpo.grid_columnconfigure(1, weight=1)
        self.frame_cuerpo.grid_columnconfigure(2, weight=0, minsize=370)
        self.frame_cuerpo.grid_rowconfigure(0, weight=1)

        #left panel configuration and recipes
        self.panel_config = PanelConfiguracion(
            self.frame_cuerpo,
            on_receta_seleccionada=self._on_receta_seleccionada,
            on_crear_receta=self._on_crear_receta,
            on_guardar_receta=self._on_guardar_receta,
            on_eliminar_receta=self._on_eliminar_receta,
            on_rotacion_cambiada=self._on_rotacion_cambiada,
            on_parametro_cambiado=self._on_parametro_cambiado,
            on_click_frame=self._on_click_frame,
            on_click_pause_resume=self._on_click_pause_resume,
            on_click_stop=self._on_click_stop
        )
        self.panel_config.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        #center panel canvas
        self.panel_general = PanelGeneral(
            self.frame_cuerpo,
            on_dimensiones_cambiadas=self._on_dimensiones_cambiadas
        )
        self.panel_general.grid(row=0, column=1, sticky="nsew", padx=6)

        #right panel gauges trace and controls
        self.panel_derecho = PanelDerecho(
            self.frame_cuerpo,
            on_click_start=self._on_click_start,
            on_click_pause_resume=self._on_click_pause_resume,
            on_click_stop=self._on_click_stop,
            on_centro_cambiado=self._on_centro_cambiado,
            on_viewport_cambiado=self._on_viewport_zoom_cambiado
        )
        self.panel_derecho.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        #floating terminal
        self.terminal = TerminalFlotante(
            self,
            on_cerrar=lambda: self.barra_superior.set_terminal_activo(False),
            obtener_historial=lambda: self.puente.gestor_trazabilidad.listar_historial(limite=50)
        )

    def _on_viewport_zoom_cambiado(self, bbox_cm: Optional[Tuple[float, float, float, float]]):
        """synchronize zoom camera frame on main canvas"""
        if hasattr(self, "panel_general"):
            if bbox_cm is not None:
                self.panel_general.actualizar_frustum_zoom(bbox_cm)
            else:
                self.panel_general.ocultar_frustum_zoom()

    def _on_idioma_cambiado(self, nuevo_idioma: str):
        """handle language change notification"""
        if hasattr(self, 'terminal'):
            self.terminal.log(tr("log_lang_changed"))



def iniciar():
    app = AppLaserCTk()
    app.mainloop()


if __name__ == "__main__":
    iniciar()
