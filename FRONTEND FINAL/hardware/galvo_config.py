# -*- coding: utf-8 -*-
"""thorlabs gvs112 galvo parameters"""

DISTANCIA_LENTE_BASE_CM = 56.5

#physical base (work area) in cm
#changing CAMPO_ANCHO_CM / CAMPO_ALTO_CM automatically updates the mm limits and default base
CAMPO_ANCHO_CM = 37.5    #physical width covered by the full optical field (x)
CAMPO_ALTO_CM  = 38.3    #physical height covered by the full optical field (y)
BASE_ANCHO_CM_DEFAULT = CAMPO_ANCHO_CM
BASE_ALTO_CM_DEFAULT  = CAMPO_ALTO_CM

#optical field limits in mm (1 cm = 10 mm, centered at 0.0 mm = 0 V)
CAMPO_X_MIN_MM = -(CAMPO_ANCHO_CM * 10.0) / 2.0
CAMPO_X_MAX_MM =  (CAMPO_ANCHO_CM * 10.0) / 2.0
CAMPO_Y_MIN_MM = -(CAMPO_ALTO_CM * 10.0) / 2.0
CAMPO_Y_MAX_MM =  (CAMPO_ALTO_CM * 10.0) / 2.0

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

#default interface mode used ONLY when ControladorThorlabsGVS() is built without arguments.
#'SIMULACION' = never touch the daq (safe default). The gui does not use this value: it
#probes the hardware on startup / on the 'Scan...' action and passes the mode explicitly.
TIPO_INTERFAZ_DAC = 'SIMULACION'
