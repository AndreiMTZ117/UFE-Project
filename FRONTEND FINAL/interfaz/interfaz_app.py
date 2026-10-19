# -*- coding: utf-8 -*-
"""
interfaz/interfaz_app.py — Orquestador Principal de la HMI UFE Laser (CustomTkinter)

Estructura modular segmentada en archivos dedicados:
  1. CONSTANTES DE DISEÑO (CYBER-BRUTALISM)                 -> interfaz/constantes.py
  2. BARRA SUPERIOR                                         -> interfaz/barra_superior.py
  3. PANEL IZQUIERDO: CONFIGURACIÓN Y RECETAS (SQLite3)     -> interfaz/panel_configuracion.py
  4. PANEL CENTRAL: CANVAS GENERAL CON REGLAS Y PROP. 1:1   -> interfaz/panel_general.py
  5. PANEL DERECHO: GAUGES + TRACE POINT + CONTROLS         -> interfaz/panel_derecho.py
  6. TERMINAL FLOTANTE (CYBER-BRUTALIST)                    -> interfaz/terminal_flotante.py
  7. CARGA INICIAL Y GESTIÓN DE DATOS                       -> interfaz/gestion_datos.py
  8. EVENTOS DE INTERACCIÓN                                 -> interfaz/eventos_interaccion.py
  9. RENDERIZADO DUAL EN CANVAS (CYBER-BRUTALISM)           -> interfaz/renderizado_dual.py
  10. LÓGICA DE EJECUCIÓN: START, PAUSE/RESUME, STOP        -> interfaz/logica_ejecucion.py
"""

import os
import sys
import customtkinter as ctk
from typing import Dict, List, Tuple

# Rutas del proyecto
_DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
_DIR_RAIZ = os.path.abspath(os.path.join(_DIR_ACTUAL, ".."))
if _DIR_RAIZ not in sys.path:
    sys.path.insert(0, _DIR_RAIZ)

# =============================================================================
# 1. CONSTANTES DE DISEÑO (CYBER-BRUTALISM)
# =============================================================================
from interfaz.constantes import (
    COLOR_BG,
    cargar_fuentes_windows,
    configurar_dpi_awareness
)

# Inicializar configuración del sistema y fuentes TrueType
configurar_dpi_awareness()
cargar_fuentes_windows()

# Puente de conexión con el backend
from interfaz.conexion_interfaz import PuenteLaser

# =============================================================================
# 2 A 6. COMPONENTES VISUALES
# =============================================================================
from interfaz.barra_superior import BarraSuperior
from interfaz.panel_configuracion import PanelConfiguracion
from interfaz.panel_general import PanelGeneral
from interfaz.panel_derecho import PanelDerecho
from interfaz.terminal_flotante import TerminalFlotante

# =============================================================================
# 7 A 10. MÓDULOS DE LÓGICA, DATOS Y EVENTOS
# =============================================================================
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
    """Aplicación principal de la estación de trabajo láser UFE."""

    def __init__(self):
        super().__init__()

        # Configuración de ventana Cyber-Brutalism
        self.title("Thorlabs GVS112/M — Industrial Galvanometer Laser Workstation")
        self.geometry("1280x760")
        self.minsize(1150, 700)
        ctk.set_appearance_mode("light")
        self.configure(fg_color=COLOR_BG)

        # Puente con el backend
        self.puente = PuenteLaser()
        self.receta_activa: Dict = {}
        self.lista_recetas: List[Dict] = []

        # Estado de telemetría y ejecución
        self.tiempo_inicio_ejecucion = 0.0
        self.tiempo_pausa_acumulado = 0.0
        self.tiempo_ultima_pausa = 0.0
        self.pos_laser_actual = (self.puente.ancho_base_cm / 2.0, self.puente.alto_base_cm / 2.0)
        self.trazos_completados: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []

        # Construir layout modular
        self._construir_layout()

        # 7. Carga inicial de datos (desde GestionDatosMixin)
        self._cargar_datos_iniciales()

        # Configurar valores iniciales de límites, centro y dimensiones en los paneles
        self._aplicar_limites_hardware()
        self.panel_derecho.set_centro(self.puente.centro_cm_x, self.puente.centro_cm_y)
        self.panel_general.set_centro(self.puente.centro_cm_x, self.puente.centro_cm_y)
        self.panel_derecho.actualizar_coordenadas(self.puente.centro_cm_x, self.puente.centro_cm_y)
        self.panel_general.actualizar_dimensiones(self.puente.ancho_base_cm, self.puente.alto_base_cm)

        # 10. Bucle de actualización del cronómetro LCD (desde LogicaEjecucionMixin)
        self._actualizar_timer_loop()

        # 11. Manejo seguro de cierre de ventana y liberación de hardware
        self.protocol("WM_DELETE_WINDOW", self._on_cerrar_aplicacion)

    def _on_cerrar_aplicacion(self):
        """Libera de forma segura los recursos del hardware y cierra la aplicacion de inmediato."""
        if getattr(self, '_cerrando', False):
            return
        self._cerrando = True

        # Deshabilitar el protocolo para evitar reentradas
        try:
            self.protocol("WM_DELETE_WINDOW", lambda: None)
        except Exception:
            pass

        # Cancelar timer programado del cronometro
        if hasattr(self, '_timer_after_id') and self._timer_after_id:
            try:
                self.after_cancel(self._timer_after_id)
            except Exception:
                pass

        # Detener la ejecucion y apagar laser de inmediato
        try:
            if hasattr(self, 'puente'):
                if self.puente.en_ejecucion:
                    self.puente.detener_ejecucion()
                if self.puente.controlador_hardware:
                    try:
                        self.puente.apagar_laser()
                        self.puente.controlador_hardware.cerrar()
                    except Exception:
                        pass
        except Exception:
            pass

        # Destruir ventana de forma segura
        try:
            self.destroy()
        except Exception:
            pass

    # =========================================================================
    # CONSTRUCCIÓN DE LAYOUT Y COMPONENTES
    # =========================================================================
    def _construir_layout(self):
        # 2. BARRA SUPERIOR
        self.barra_superior = BarraSuperior(
            self,
            on_com_seleccionado=self._on_com_seleccionado,
            on_dxf_seleccionado=self._on_dxf_seleccionado,
            on_load_file_click=self._on_click_load_file,
            on_toggle_terminal=self._on_toggle_terminal
        )
        self.barra_superior.pack(fill="x", padx=16, pady=(10, 4))

        # Contenedor central (Grid de 3 columnas)
        self.frame_cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_cuerpo.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        self.frame_cuerpo.grid_columnconfigure(0, weight=0, minsize=265)
        self.frame_cuerpo.grid_columnconfigure(1, weight=1)
        self.frame_cuerpo.grid_columnconfigure(2, weight=0, minsize=370)
        self.frame_cuerpo.grid_rowconfigure(0, weight=1)

        # 3. PANEL IZQUIERDO: CONFIGURACIÓN Y RECETAS (SQLite3)
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

        # 4. PANEL CENTRAL: CANVAS GENERAL CON REGLAS Y PROPORCIÓN 1:1 (BASE EDITABLE)
        self.panel_general = PanelGeneral(
            self.frame_cuerpo,
            on_dimensiones_cambiadas=self._on_dimensiones_cambiadas
        )
        self.panel_general.grid(row=0, column=1, sticky="nsew", padx=6)

        # 5. PANEL DERECHO: GAUGES + TRACE POINT + EXECUTION CONTROLS (CENTRO EDITABLE)
        self.panel_derecho = PanelDerecho(
            self.frame_cuerpo,
            on_click_start=self._on_click_start,
            on_click_pause_resume=self._on_click_pause_resume,
            on_click_stop=self._on_click_stop,
            on_centro_cambiado=self._on_centro_cambiado
        )
        self.panel_derecho.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        # 6. TERMINAL FLOTANTE (CYBER-BRUTALIST)
        self.terminal = TerminalFlotante(
            self,
            on_cerrar=lambda: self.barra_superior.set_terminal_activo(False),
            obtener_historial=lambda: self.puente.gestor_trazabilidad.listar_historial(limite=50)
        )


def iniciar():
    app = AppLaserCTk()
    app.mainloop()


if __name__ == "__main__":
    iniciar()
