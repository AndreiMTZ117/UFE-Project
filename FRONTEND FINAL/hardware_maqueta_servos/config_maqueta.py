# -*- coding: utf-8 -*-
"""
hardware_maqueta_servos/config_maqueta.py — Calibración de la Maqueta de Servomotores

Contiene los parámetros geométricos, cinemáticos y de puerto serie específicos
para la maqueta de 2 servomotores con espejos y diodo láser.
"""

# =========================================================
# LÍMITES FÍSICOS DE LA MAQUETA (Coordenadas de los servos)
# =========================================================
# Esquinas del marco físico de proyección:
P1_SUP_IZQ = (55.0, 62.0)
P2_INF_IZQ = (55.0, 39.0)
P3_INF_DER = (63.0, 39.0)
P4_SUP_DER = (63.0, 62.0)

# Límites para clamping y transformación
X_MIN_LIMIT = min(P1_SUP_IZQ[0], P2_INF_IZQ[0])  # 55.0
X_MAX_LIMIT = max(P3_INF_DER[0], P4_SUP_DER[0])  # 63.0
Y_MIN_LIMIT = min(P2_INF_IZQ[1], P3_INF_DER[1])  # 39.0
Y_MAX_LIMIT = max(P1_SUP_IZQ[1], P4_SUP_DER[1])  # 62.0

CENTRO_MAQUETA_X = round((X_MIN_LIMIT + X_MAX_LIMIT) / 2.0, 2)  # 59.00
CENTRO_MAQUETA_Y = round((Y_MIN_LIMIT + Y_MAX_LIMIT) / 2.0, 2)  # 50.50

# Dimensiones físicas estimadas del marco de calibración en centímetros (o 1.0 para relación 1:1)
MARCO_ALTO_CM = 25.0   # Distancia física vertical (Eje X servos: de base P3-P4 a tope P1-P2)
MARCO_ANCHO_CM = 28.0  # Distancia física horizontal (Eje Y servos: de P2-P3 a P1-P4)

# Factor de llenado de la base (0.90 = aprovecha el 90% del ancho/alto disponible)
ESCALA_DIBUJO = 0.90

# Orientación física de los espejos:
# False: Norte del dibujo apunta a P1-P4 (Y=62), Sur a P2-P3 (Y=39)
ROTAR_90_GRADOS = False

# =========================================================
# PARÁMETROS CINEMÁTICOS Y SERIAL (TRAZADO LENTO Y FLUIDO)
# =========================================================
PUERTO_ESP32 = "COM5"
BAUDRATE = 115200

VELOCIDAD_TRAZADO = 2.0      # u/s dibujando con láser encendido (movimiento suave y controlado)
VELOCIDAD_VIAJE   = 3.5      # u/s reposicionando con láser apagado

DURACION_MIN_SEGMENTO_MS = 50  # ms mínimos por waypoint (permite a los servos interpolar con máxima suavidad)
DURACION_MIN_VIAJE_MS    = 300 # ms mínimos por traslado en vacío

TOLERANCIA_RDP   = 0.025     # 0.025 = Filtra micro-pasos sub-deadband en curvas manteniendo geometría fiel
TOLERANCIA_UNION = 0.08      # Tolerancia para unir trazos contiguos (0.08 asegura 100% de contornos cerrados)
LONGITUD_MIN_TRAZO = 0.01    # Descartar ruido < 0.01 u

LIMITES_MAQUETA = {
    'x_min': X_MIN_LIMIT,
    'x_max': X_MAX_LIMIT,
    'y_min': Y_MIN_LIMIT,
    'y_max': Y_MAX_LIMIT,
}
