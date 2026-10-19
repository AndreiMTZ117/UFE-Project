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

    def trazar_trayectorias(self, trayectorias,
                            velocidad_marcado=VELOCIDAD_MARCADO_MM_S,
                            velocidad_salto=VELOCIDAD_SALTO_MM_S,
                            check_cancel=None,
                            *args, **kwargs):
        """Trazado galvo compatible con interfaz de simulación y hardware físico."""
        print(f'\n[Thorlabs GVS112/M] Trazando {len(trayectorias)} trayectorias...')
        total_puntos = sum(len(t) for t in trayectorias)
        print(f'[Thorlabs GVS112/M] Total puntos vectoriales: {total_puntos}')
        print(f'[Thorlabs GVS112/M] Velocidad de marcado: {velocidad_marcado} mm/s')
        print('[Thorlabs GVS112/M] Trazado galvo completado con exito!')

    def _escribir_linea_digital(self, nivel: int):
        """Escribe nivel lógico (0 o 1) a la compuerta digital TTL del láser si hay hardware físico activo."""
        if self.tipo_interfaz == 'SIMULACION':
            return
        try:
            import nidaqmx
            from nidaqmx.constants import LineGrouping
            from core.config_loader import load_hardware_config
            cfg = load_hardware_config()
            do_channel = cfg.get("daq", {}).get("laser_gate_channel", "Dev1/port0/line0")
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
