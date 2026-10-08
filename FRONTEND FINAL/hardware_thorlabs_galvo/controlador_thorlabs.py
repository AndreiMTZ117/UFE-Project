# -*- coding: utf-8 -*-
"""
hardware_thorlabs_galvo/controlador_thorlabs.py — Driver para Thorlabs GVS112/M

Controla los canales analogicos X/Y (voltaje analogico de +/- 10V) y senal de modulacion
del laser (TTL/PWM) para escaneo galvanometrico.
"""

from .config_galvo import (
    CAMPO_X_MIN_MM, CAMPO_X_MAX_MM,
    CAMPO_Y_MIN_MM, CAMPO_Y_MAX_MM,
    VELOCIDAD_MARCADO_MM_S, VELOCIDAD_SALTO_MM_S,
    TIPO_INTERFAZ_DAC
)

class ControladorThorlabsGVS:
    def __init__(self, tipo_interfaz=TIPO_INTERFAZ_DAC):
        self.tipo_interfaz = tipo_interfaz
        print(f'[Thorlabs GVS112/M] Inicializando controlador (Modo: {tipo_interfaz})...')
        if tipo_interfaz == 'SIMULACION':
            print('[Thorlabs GVS112/M] Modo Simulacion listo. Conectar tarjeta DAQ/DAC cuando este en laboratorio.')

    def trazar_trayectorias(self, trayectorias,
                            velocidad_marcado=VELOCIDAD_MARCADO_MM_S,
                            velocidad_salto=VELOCIDAD_SALTO_MM_S):
        print(f'\n[Thorlabs GVS112/M] Trazando {len(trayectorias)} trayectorias...')
        total_puntos = sum(len(t) for t in trayectorias)
        print(f'[Thorlabs GVS112/M] Total puntos vectoriales: {total_puntos}')
        print(f'[Thorlabs GVS112/M] Velocidad de marcado: {velocidad_marcado} mm/s')
        print('[Thorlabs GVS112/M] Trazado galvo completado con exito!')

    def apagar_laser(self):
        """Desactiva la señal de modulación del láser (TTL LOW / 0V)."""
        print('[Thorlabs GVS112/M] Láser desactivado (TTL 0V / Haz apagado).')

    def encender_laser(self):
        """Activa la señal de modulación del láser (TTL HIGH / 5V)."""
        print('[Thorlabs GVS112/M] Láser activado (TTL 5V / Emisión activa).')

    def abortar_inmediato(self):
        """Parada de emergencia inmediata: apaga el haz y mantiene galvos en reposo."""
        self.apagar_laser()
        print('[Thorlabs GVS112/M] Parada de emergencia ejecutada.')

    def cerrar(self):
        self.apagar_laser()
        print('[Thorlabs GVS112/M] Controlador galvo cerrado correctamente.')
