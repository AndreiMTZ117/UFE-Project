# -*- coding: utf-8 -*-
"""
hardware/config_galvo.py — Configuracion Cabezal Galvo Thorlabs GVS112/M

Parametros para cabezal de escaneo galvanometrico de alta velocidad de 2 ejes.
Especificaciones Thorlabs GVS112/M:
  * Rango de escaneo optico: +/- 20 grados (+/- 10V entrada analogica, escala 1.0 V/grado)
  * Ancho de banda de pequena senal: 1 kHz
  * Tiempo de salto (step response 1%): ~300 us
  * Resolucion angular: menor a 15 urad
"""

# Campo de trabajo optico (en milimetros, ej: 100 mm x 100 mm con lente F-Theta)
CAMPO_X_MIN_MM = -50.0   # mm
CAMPO_X_MAX_MM =  50.0   # mm
CAMPO_Y_MIN_MM = -50.0   # mm
CAMPO_Y_MAX_MM =  50.0   # mm

LIMITES_GALVO = {
    'x_min': CAMPO_X_MIN_MM,
    'x_max': CAMPO_X_MAX_MM,
    'y_min': CAMPO_Y_MIN_MM,
    'y_max': CAMPO_Y_MAX_MM,
}

# Factor de escala (0.90 = 90% del campo de escaneo)
ESCALA_DIBUJO = 0.90

# Orientacion del cabezal galvo
ROTAR_90_GRADOS = False

# Cinematica de escaneo Galvo (alta velocidad mm/s)
VELOCIDAD_MARCADO_MM_S = 500.0   # mm/s marcando con laser encendido
VELOCIDAD_SALTO_MM_S   = 2000.0  # mm/s saltos en vacio

# Delays caracteristicos de galvanometros (en microsegundos; consumidos por el simulador)
LASER_ON_DELAY_US  = 20    # Retardo para encender laser tras alcanzar posicion
LASER_OFF_DELAY_US = 20    # Retardo para apagar laser antes de saltar
JUMP_DELAY_US      = 150   # Retardo de estabilizacion mecanica en saltos
MARK_DELAY_US      = 50    # Retardo de estabilizacion en vectores de marcado

# Dispositivo de interfaz DAC para cabezal Thorlabs GVS112/M
TIPO_INTERFAZ_DAC = 'SIMULACION'  # 'NI_DAQ', 'SIMULACION'
