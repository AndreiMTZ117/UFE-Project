# -*- coding: utf-8 -*-
"""thorlabs gvs112 galvo parameters"""

#optical field limits in mm
CAMPO_X_MIN_MM = -50.0
CAMPO_X_MAX_MM =  50.0
CAMPO_Y_MIN_MM = -50.0
CAMPO_Y_MAX_MM =  50.0

LIMITES_GALVO = {
    'x_min': CAMPO_X_MIN_MM,
    'x_max': CAMPO_X_MAX_MM,
    'y_min': CAMPO_Y_MIN_MM,
    'y_max': CAMPO_Y_MAX_MM,
}

#scale factor
ESCALA_DIBUJO = 0.90

#galvo head orientation
ROTAR_90_GRADOS = False

#scan speeds in mm/s
VELOCIDAD_MARCADO_MM_S = 500.0
VELOCIDAD_SALTO_MM_S   = 2000.0

#optical delays in us
LASER_ON_DELAY_US  = 20
LASER_OFF_DELAY_US = 20
JUMP_DELAY_US      = 150
MARK_DELAY_US      = 50

#dac interface mode
TIPO_INTERFAZ_DAC = 'SIMULACION'
