# -*- coding: utf-8 -*-
"""thorlabs gvs112 driver"""

import logging
from typing import Callable, Optional

from .config_galvo import (
    VELOCIDAD_MARCADO_MM_S, VELOCIDAD_SALTO_MM_S,
    TIPO_INTERFAZ_DAC
)

logger = logging.getLogger(__name__)


class ControladorThorlabsGVS:
    def __init__(self, tipo_interfaz=TIPO_INTERFAZ_DAC):
        #any value other than 'SIMULACION' (e.g. 'NI_DAQ', 'DAC') talks to the real daq
        self.tipo_interfaz = tipo_interfaz
        self.laser_encendido = False
        #optional callback(msg, critico) so the gui can surface hardware failures
        self.on_alerta: Optional[Callable[[str, bool], None]] = None
        print(f'[Thorlabs GVS112/M] Inicializando controlador (Modo: {tipo_interfaz})...')
        if tipo_interfaz == 'SIMULACION':
            print('[Thorlabs GVS112/M] Modo Simulacion listo. Conectar tarjeta DAQ/DAC cuando este en laboratorio.')

    def _alertar(self, mensaje: str, critico: bool = False) -> None:
        """notify gui about a hardware failure without ever raising"""
        print(f'[Thorlabs GVS112/M] {mensaje}')
        if self.on_alerta is not None:
            try:
                self.on_alerta(mensaje, critico)
            except Exception as error:
                logger.error("on_alerta callback failed: %s", error)

    def ir_a_posicion(self, x_mm: float = 0.0, y_mm: float = 0.0):
        """static move mirrors to position in mm"""
        if self.tipo_interfaz == 'SIMULACION':
            return
        try:
            import nidaqmx
            from core.config_loader import load_hardware_config, get_volts_per_mm, get_daq_identity
            cfg = load_hardware_config()
            v_per_mm = get_volts_per_mm(cfg)
            vx = max(-10.0, min(10.0, float(x_mm) * v_per_mm))
            vy = max(-10.0, min(10.0, float(y_mm) * v_per_mm))
            ao_channels = get_daq_identity(cfg)["analog_channels"]
            with nidaqmx.Task("GalvoStaticMove") as task:
                for ch in ao_channels:
                    task.ao_channels.add_ao_voltage_chan(ch, min_val=-10.0, max_val=10.0)
                task.write([vx, vy], auto_start=True)
        except Exception as error:
            #never raise here (ui/e-stop callers), but never fail silently either
            logger.error("Static galvo move to (%.3f, %.3f) mm failed: %s", x_mm, y_mm, error)
            self._alertar(f'No se pudo mover los espejos a ({x_mm:.2f}, {y_mm:.2f}) mm: {error}')

    def center(self):
        """park mirrors at center 0v"""
        self.ir_a_posicion(0.0, 0.0)

    def _escribir_linea_digital(self, nivel: int) -> bool:
        """write digital level to laser gate, returns True if the line was written"""
        if self.tipo_interfaz == 'SIMULACION':
            return True
        try:
            import nidaqmx
            from nidaqmx.constants import LineGrouping
            from core.config_loader import load_hardware_config, get_daq_identity
            cfg = load_hardware_config()
            do_channel = get_daq_identity(cfg)["laser_gate_channel"]
            with nidaqmx.Task() as task:
                task.do_channels.add_do_chan(do_channel, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
                task.write(bool(nivel), auto_start=True)
            return True
        except Exception as error:
            #hardware disconnected, line busy or bad config: report it
            logger.error("Laser gate write (level=%s) failed: %s", nivel, error)
            return False

    def apagar_laser(self):
        """switch laser off ttl low"""
        self.laser_encendido = False
        if self._escribir_linea_digital(0):
            print('[Thorlabs GVS112/M] Láser desactivado (TTL 0V / Haz apagado).')
        else:
            self._alertar('¡ATENCIÓN! No se pudo confirmar el apagado del láser en hardware. Verificar manualmente.', critico=True)

    def encender_laser(self):
        """switch laser on ttl high"""
        if self._escribir_linea_digital(1):
            self.laser_encendido = True
            print('[Thorlabs GVS112/M] Láser activado (TTL 5V / Emisión activa).')
        else:
            self.laser_encendido = False
            self._alertar('No se pudo activar el láser (error de hardware o configuración).', critico=True)

    def abortar_inmediato(self):
        """emergency stop switch laser off"""
        self.apagar_laser()
        print('[Thorlabs GVS112/M] Parada de emergencia ejecutada.')

    def cerrar(self):
        self.apagar_laser()
        print('[Thorlabs GVS112/M] Controlador galvo cerrado correctamente.')
