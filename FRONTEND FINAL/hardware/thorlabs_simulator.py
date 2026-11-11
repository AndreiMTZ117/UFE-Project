# -*- coding: utf-8 -*-
"""thorlabs gvs112 virtual simulator"""

import threading

from .galvo_config import (
    CAMPO_X_MIN_MM, CAMPO_X_MAX_MM,
    CAMPO_Y_MIN_MM, CAMPO_Y_MAX_MM,
)
from core.config_loader import load_hardware_config, get_volts_per_mm


class SimuladorThorlabsGVS:
    """galvo simulator when hardware is disconnected"""

    tipo_interfaz = "SIMULACION"

    def __init__(self):
        self.laser_encendido = False
        self._stop_event = threading.Event()
        cfg = load_hardware_config()
        self.volts_per_mm = get_volts_per_mm(cfg)
        lim = cfg.get("voltage_limits", {})
        self.v_min = float(lim.get("min", -10.0))
        self.v_max = float(lim.get("max", 10.0))
        self.pos_x = 0.0
        self.pos_y = 0.0
        print("[SimThorlabs] Simulador GVS112/M iniciado - hardware fisico NO conectado.")
        print(f"[SimThorlabs]   Campo: X[{CAMPO_X_MIN_MM}, {CAMPO_X_MAX_MM}] mm  "
              f"Y[{CAMPO_Y_MIN_MM}, {CAMPO_Y_MAX_MM}] mm")

    def ir_a_posicion(self, x_mm: float = 0.0, y_mm: float = 0.0):
        """simulated mirror move to position in mm"""
        self.pos_x = float(x_mm)
        self.pos_y = float(y_mm)

    def center(self):
        """simulated mirror park at home"""
        self.ir_a_posicion(0.0, 0.0)

    def apagar_laser(self):
        """switch simulated laser off"""
        if self.laser_encendido:
            self.laser_encendido = False

    def encender_laser(self):
        """switch simulated laser on"""
        if not self.laser_encendido:
            self.laser_encendido = True

    def abortar_inmediato(self):
        """emergency stop switch laser off"""
        self._stop_event.set()
        self.apagar_laser()
        print("[SimThorlabs] Parada de emergencia ejecutada.")

    def cerrar(self):
        """release simulator resources"""
        self._stop_event.set()
        self.apagar_laser()
        print("[SimThorlabs] Simulador cerrado correctamente.")
