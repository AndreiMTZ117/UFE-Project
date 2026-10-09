# -*- coding: utf-8 -*-
"""
hardware_thorlabs_galvo/config_galvo.py — Configuración Central del Sistema Thorlabs GVS112/M

Único archivo de configuración para producción. Un técnico de laboratorio
solo necesita editar este archivo para adaptar el sistema a una nueva instalación.

Especificaciones Thorlabs GVS112/M:
  * Rango de escaneo óptico: ±20° (±10 V entrada analógica, escala 1.0 V/grado)
  * Ancho de banda de pequeña señal: 1 kHz
  * Tiempo de salto (step response 1%): ~300 µs
  * Resolución angular: < 15 µrad
"""

# =============================================================================
# MODO DE OPERACIÓN
# =============================================================================
MODO_HARDWARE = 'SIMULACION'   # Cambiar a 'REAL' al conectar al PXI-6229

# =============================================================================
# CONFIGURACIÓN NATIONAL INSTRUMENTS (PXI-6229)
# =============================================================================
DISPOSITIVO_NI = 'Dev1'         # Nombre en NI Measurement & Automation Explorer
CANAL_AO_X     = 'ao0'          # Salida analógica Eje X (+/-10 V)
CANAL_AO_Y     = 'ao1'          # Salida analógica Eje Y (+/-10 V)
CANAL_DO_LASER = 'port0/line0'  # Salida digital para compuerta láser (TTL)

FRECUENCIA_MUESTREO_HZ = 100_000  # 100 kS/s — frecuencia de muestreo de la tarea DAQ

# =============================================================================
# CAMPO DE TRABAJO ÓPTICO (simétrico, centrado en el origen)
# =============================================================================
CAMPO_X_MIN_MM = -50.0   # mm — límite izquierdo del campo F-Theta
CAMPO_X_MAX_MM =  50.0   # mm — límite derecho
CAMPO_Y_MIN_MM = -50.0   # mm — límite inferior
CAMPO_Y_MAX_MM =  50.0   # mm — límite superior

LIMITES_GALVO = {
    'x_min': CAMPO_X_MIN_MM,
    'x_max': CAMPO_X_MAX_MM,
    'y_min': CAMPO_Y_MIN_MM,
    'y_max': CAMPO_Y_MAX_MM,
}

# =============================================================================
# CALIBRACIÓN ÓPTICA / LENTE F-THETA
# =============================================================================
ESCALA_VX_POR_MM = 0.20   # Voltios por mm (ajustar según distancia focal de la lente)
ESCALA_VY_POR_MM = 0.20   # Voltios por mm

OFFSET_VX = 0.00   # Corrección de cero eje X [V]
OFFSET_VY = 0.00   # Corrección de cero eje Y [V]

# =============================================================================
# CINEMÁTICA DE ESCANEO (velocidades nominales)
# =============================================================================
VELOCIDAD_MARCADO_MM_S = 500.0    # mm/s — marcado con láser encendido
VELOCIDAD_SALTO_MM_S   = 2000.0   # mm/s — saltos en vacío (láser apagado)

# Factor de escala del dibujo sobre el campo total (0.90 = 90 % del campo)
ESCALA_DIBUJO   = 0.90
ROTAR_90_GRADOS = False

# =============================================================================
# RETARDOS DE GALVANÓMETRO (microsegundos)
# =============================================================================
JUMP_DELAY_US      = 250   # Estabilización mecánica de espejos tras un salto G0
LASER_ON_DELAY_US  = 100   # Inercia óptica al encender el haz (evita punto caliente inicial)
LASER_OFF_DELAY_US =  50   # Inercia óptica al apagar el haz (evita cola de sobrequemado)
CORNER_DELAY_US    =  50   # Retardo adicional en esquinas agudas

# =============================================================================
# COMPATIBILIDAD INTERNA
# =============================================================================
# Estos alias permiten que el resto del código (conexion_interfaz, principal)
# sigan funcionando sin cambios de nombre.
TIPO_INTERFAZ_DAC = MODO_HARDWARE  # 'SIMULACION' | 'REAL'
