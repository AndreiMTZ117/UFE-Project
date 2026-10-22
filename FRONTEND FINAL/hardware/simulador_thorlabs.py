# -*- coding: utf-8 -*-
"""
hardware/simulador_thorlabs.py - Simulador de Thorlabs GVS112/M

Simula la ejecucion completa del sistema galvo cuando el hardware fisico
Thorlabs no esta conectado. Produce logs, retardos y callbacks identicos
al controlador real para que la interfaz funcione sin cambios.

Activado automaticamente cuando no se detecta tarjeta DAQ/DAC.
"""

import time
import math
import threading

from .config_galvo import (
    CAMPO_X_MIN_MM, CAMPO_X_MAX_MM,
    CAMPO_Y_MIN_MM, CAMPO_Y_MAX_MM,
    VELOCIDAD_MARCADO_MM_S, VELOCIDAD_SALTO_MM_S,
    LASER_ON_DELAY_US, LASER_OFF_DELAY_US, JUMP_DELAY_US, MARK_DELAY_US,
)
from core.config_loader import load_hardware_config, get_volts_per_mm


class SimuladorThorlabsGVS:
    """
    Simulador fiel del Thorlabs GVS112/M para entorno sin hardware fisico.

    Proporciona la misma interfaz publica que ControladorThorlabsGVS:
      - trazar_trayectorias()
      - apagar_laser() / encender_laser()
      - abortar_inmediato()
      - cerrar()
    """

    tipo_interfaz = "SIMULACION"

    def __init__(self):
        self.laser_encendido = False
        self._stop_event = threading.Event()
        cfg = load_hardware_config()
        self.volts_per_mm = get_volts_per_mm(cfg)
        lim = cfg.get("voltage_limits", {})
        self.v_min = float(lim.get("min", -10.0))
        self.v_max = float(lim.get("max", 10.0))
        self._clamp_warned = False
        print("[SimThorlabs] Simulador GVS112/M iniciado - hardware fisico NO conectado.")
        print(f"[SimThorlabs]   Campo: X[{CAMPO_X_MIN_MM}, {CAMPO_X_MAX_MM}] mm  "
              f"Y[{CAMPO_Y_MIN_MM}, {CAMPO_Y_MAX_MM}] mm")

    def trazar_trayectorias(self,
                            trayectorias,
                            velocidad_marcado: float = VELOCIDAD_MARCADO_MM_S,
                            velocidad_salto: float = VELOCIDAD_SALTO_MM_S,
                            check_cancel=None,
                            *args, **kwargs):
        """
        Simula el trazado galvo respetando velocidades y cancelecion.

        :param trayectorias:      Lista de trazos [[( x, y ), ...], ...]
        :param velocidad_marcado: mm/s con laser ON
        :param velocidad_salto:   mm/s con laser OFF (viaje)
        :param check_cancel:      Callable -> bool; True = abortar
        """
        self._stop_event.clear()
        total_trazos = len(trayectorias)
        total_pts = sum(len(t) for t in trayectorias)

        print(f"\n[SimThorlabs] Iniciando simulacion - {total_trazos} trazos, {total_pts} puntos")
        print(f"[SimThorlabs]   v_marcado={velocidad_marcado} mm/s  v_salto={velocidad_salto} mm/s")

        pos_x, pos_y = 0.0, 0.0

        for idx, trazo in enumerate(trayectorias):
            if self._debe_cancelar(check_cancel):
                print("[SimThorlabs] Trazado abortado por cancelacion.")
                break

            if not trazo:
                continue

            # Viaje al primer punto (laser apagado)
            p0 = self._limitar_punto(trazo[0])
            dist_viaje = math.hypot(p0[0] - pos_x, p0[1] - pos_y)
            t_viaje = dist_viaje / max(0.1, velocidad_salto)
            self._esperar(t_viaje + JUMP_DELAY_US * 1e-6, check_cancel)

            if self._debe_cancelar(check_cancel):
                break

            # Trazar segmentos con laser encendido
            self._esperar(LASER_ON_DELAY_US * 1e-6, check_cancel)
            self.encender_laser()
            pos_x, pos_y = p0

            for i in range(1, len(trazo)):
                if self._debe_cancelar(check_cancel):
                    self.apagar_laser()
                    print("[SimThorlabs] Trazado abortado en segmento.")
                    return

                pt = self._limitar_punto(trazo[i])
                dist_seg = math.hypot(pt[0] - pos_x, pt[1] - pos_y)
                t_seg = dist_seg / max(0.1, velocidad_marcado)
                self._esperar(t_seg + MARK_DELAY_US * 1e-6, check_cancel)
                pos_x, pos_y = pt

            self._esperar(LASER_OFF_DELAY_US * 1e-6, check_cancel)
            self.apagar_laser()
            pct = round((idx + 1) / total_trazos * 100, 1)
            print(f"[SimThorlabs]   Trazo {idx + 1}/{total_trazos} completado ({pct}%)")

        print("[SimThorlabs] Simulacion de trazado finalizada.")

    def apagar_laser(self):
        """Apaga el laser simulado."""
        if self.laser_encendido:
            self.laser_encendido = False

    def encender_laser(self):
        """Enciende el laser simulado."""
        if not self.laser_encendido:
            self.laser_encendido = True

    def abortar_inmediato(self):
        """Parada de emergencia: senializa el stop y apaga el laser."""
        self._stop_event.set()
        self.apagar_laser()
        print("[SimThorlabs] Parada de emergencia ejecutada.")

    def cerrar(self):
        """Libera recursos del simulador."""
        self._stop_event.set()
        self.apagar_laser()
        print("[SimThorlabs] Simulador cerrado correctamente.")

    def _limitar_punto(self, p):
        """Satura (x, y) en mm para que el voltaje equivalente quede en [v_min, v_max]."""
        vx, vy = p[0] * self.volts_per_mm, p[1] * self.volts_per_mm
        cx = min(self.v_max, max(self.v_min, vx))
        cy = min(self.v_max, max(self.v_min, vy))
        if (cx != vx or cy != vy) and not self._clamp_warned:
            self._clamp_warned = True
            print(f"[SimThorlabs] AVISO: comando fuera de +/-{self.v_max} V; saturado.")
        if self.volts_per_mm == 0:
            return p
        return (cx / self.volts_per_mm, cy / self.volts_per_mm)

    def _esperar(self, segundos: float, check_cancel=None, granularidad: float = 0.05):
        """Espera en pasos pequenos revisando cancelacion."""
        t_fin = time.monotonic() + segundos
        while time.monotonic() < t_fin:
            if self._debe_cancelar(check_cancel):
                return
            restante = t_fin - time.monotonic()
            time.sleep(min(granularidad, max(0.001, restante)))

    def _debe_cancelar(self, check_cancel=None) -> bool:
        """Retorna True si se debe cancelar la operacion."""
        if self._stop_event.is_set():
            return True
        if check_cancel and callable(check_cancel):
            return bool(check_cancel())
        return False
