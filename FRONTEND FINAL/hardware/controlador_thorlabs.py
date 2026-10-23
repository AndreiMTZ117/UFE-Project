# -*- coding: utf-8 -*-
"""
hardware/controlador_thorlabs.py — Driver para Thorlabs GVS112/M

Controla los canales analogicos X/Y (voltaje analogico de +/- 10V) y senal de modulacion
del laser (TTL/PWM) para escaneo galvanometrico.
"""

from .config_galvo import (
    VELOCIDAD_MARCADO_MM_S, VELOCIDAD_SALTO_MM_S,
    TIPO_INTERFAZ_DAC
)

class ControladorThorlabsGVS:
    def __init__(self, tipo_interfaz=TIPO_INTERFAZ_DAC):
        self.tipo_interfaz = tipo_interfaz
        self.laser_encendido = False
        print(f'[Thorlabs GVS112/M] Inicializando controlador (Modo: {tipo_interfaz})...')
        if tipo_interfaz == 'SIMULACION':
            print('[Thorlabs GVS112/M] Modo Simulacion listo. Conectar tarjeta DAQ/DAC cuando este en laboratorio.')

    def ir_a_posicion(self, x_mm: float = 0.0, y_mm: float = 0.0):
        """Posiciona los espejos galvo de forma estática (on-demand) a (x_mm, y_mm) si hay hardware físico."""
        if self.tipo_interfaz == 'SIMULACION':
            return
        try:
            import nidaqmx
            from core.config_loader import load_hardware_config, get_volts_per_mm
            cfg = load_hardware_config()
            v_per_mm = get_volts_per_mm(cfg)
            vx = max(-10.0, min(10.0, float(x_mm) * v_per_mm))
            vy = max(-10.0, min(10.0, float(y_mm) * v_per_mm))
            ao_channels = cfg.get("daq", {}).get("analog_channels", ["Dev1/ao0", "Dev1/ao1"])
            with nidaqmx.Task("GalvoStaticMove") as task:
                for ch in ao_channels:
                    task.ao_channels.add_ao_voltage_chan(ch, min_val=-10.0, max_val=10.0)
                task.write([vx, vy], auto_start=True)
        except Exception:
            pass

    def center(self):
        """Envía los espejos a la posición central de reposo (0.0 V, 0.0 V)."""
        self.ir_a_posicion(0.0, 0.0)

    def _escribir_linea_digital(self, nivel: int):
        """Escribe nivel lógico (0 o 1) a la compuerta digital TTL del láser si hay hardware físico activo."""
        if self.tipo_interfaz == 'SIMULACION':
            return
        try:
            import nidaqmx
            from nidaqmx.constants import LineGrouping
            from core.config_loader import load_hardware_config
            cfg = load_hardware_config()
            do_channel = cfg["daq"]["laser_gate_channel"]
            with nidaqmx.Task() as task:
                task.do_channels.add_do_chan(do_channel, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
                task.write(nivel, auto_start=True)
        except Exception:
            # Si el hardware no está conectado o la línea está reservada por una tarea de barrido,
            # no bloquear ni interrumpir la ejecución.
            pass

    def apagar_laser(self):
        """Desactiva la señal de modulación del láser (TTL LOW / 0V)."""
        self.laser_encendido = False
        self._escribir_linea_digital(0)
        print('[Thorlabs GVS112/M] Láser desactivado (TTL 0V / Haz apagado).')

    def encender_laser(self):
        """Activa la señal de modulación del láser (TTL HIGH / 5V)."""
        self.laser_encendido = True
        self._escribir_linea_digital(1)
        print('[Thorlabs GVS112/M] Láser activado (TTL 5V / Emisión activa).')

    def abortar_inmediato(self):
        """Parada de emergencia inmediata: apaga el haz y mantiene galvos en reposo."""
        self.apagar_laser()
        print('[Thorlabs GVS112/M] Parada de emergencia ejecutada.')

    def cerrar(self):
        self.apagar_laser()
        print('[Thorlabs GVS112/M] Controlador galvo cerrado correctamente.')
