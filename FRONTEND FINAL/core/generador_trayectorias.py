# -*- coding: utf-8 -*-
"""
core/generador_trayectorias.py — Transformación, Escalado Uniforme y Mapeo Geométrico

Transforma vectores del espacio CAD al espacio de trabajo del hardware:
  - Mantiene relación de aspecto 1:1 estricta (escala uniforme).
  - Centra la figura dentro del campo de trabajo (Field of View / FOV).
  - Aplica rotación de orientación según el montaje físico.
  - Ejecuta optimización de trayectorias (TSP) y simplificación RDP.
"""

import math
from .lector_dxf import obtener_limites_dxf
from .PathOptimizer import optimizar_y_unir_trazos, simplificar_trayectoria_rdp

def transform_and_scale_dxf(trayectorias,
                               x_min_limit, x_max_limit,
                               y_min_limit, y_max_limit,
                               escala=0.75,
                               rotar_90_grados=True,
                               rotacion_grados=None,
                               marco_ancho_cm=None,
                               marco_alto_cm=None,
                               tolerancia_rdp=0.0,
                               tolerancia_union=0.02,
                               longitud_min_trazo=0.01,
                               optimizar_recorrido=True,
                               centro_x=None,
                               centro_y=None,
                               *args, **kwargs):
    """
    Mapea trayectorias DXF al espacio físico destino manteniendo proporciones exactas.

    Args:
        trayectorias:       Lista de rutas vectoriales en coordenadas DXF.
        x_min_limit, x_max_limit: Rango del eje X destino.
        y_min_limit, y_max_limit: Rango del eje Y destino.
        escala:             Factor de llenado del campo de trabajo (0.1 a 1.0).
        rotar_90_grados:    Retrocompatibilidad: si True y rotacion_grados es None, usa 90°.
        rotacion_grados:    Ángulo de rotación libre en grados (0-360). Prioridad sobre rotar_90_grados.
        marco_ancho_cm:     Ancho físico de calibración del hardware (opcional).
        marco_alto_cm:      Alto físico de calibración del hardware (opcional).
        base_ancho_cm:      Ancho físico de la base de trabajo/material en cm (opcional).
        base_alto_cm:       Alto físico de la base de trabajo/material en cm (opcional).
        tolerancia_rdp:     Tolerancia RDP para eliminar puntos redundantes.
        tolerancia_union:   Distancia para fusionar trazos que se tocan.
        longitud_min_trazo: Longitud mínima para filtrar micro-artefactos.
        optimizar_recorrido:Si True, ejecuta ordenamiento TSP.

    Returns:
        Lista de trazos transformados y optimizados en coordenadas destino.
    """
    if not trayectorias:
        return []

    # Determinar ángulo de rotación efectivo
    if rotacion_grados is not None:
        angulo_deg = float(rotacion_grados)
    else:
        angulo_deg = 0.0

    angulo_rad = math.radians(angulo_deg)
    cos_a = math.cos(angulo_rad)
    sin_a = math.sin(angulo_rad)

    min_x, max_x, min_y, max_y = obtener_limites_dxf(trayectorias)

    # Centro geométrico del DXF
    dxf_cx = (min_x + max_x) / 2.0
    dxf_cy = (min_y + max_y) / 2.0

    # Calcular bounding box del DXF rotado para escalar correctamente
    corners = [
        (min_x - dxf_cx, min_y - dxf_cy),
        (max_x - dxf_cx, min_y - dxf_cy),
        (max_x - dxf_cx, max_y - dxf_cy),
        (min_x - dxf_cx, max_y - dxf_cy),
    ]
    rotated_xs = [cx * cos_a - cy * sin_a for cx, cy in corners]
    rotated_ys = [cx * sin_a + cy * cos_a for cx, cy in corners]
    rot_ancho = max(rotated_xs) - min(rotated_xs)
    rot_alto = max(rotated_ys) - min(rotated_ys)
    rot_ancho = max(0.001, rot_ancho)
    rot_alto = max(0.001, rot_alto)

    rango_dest_x = x_max_limit - x_min_limit
    rango_dest_y = y_max_limit - y_min_limit

    # Calibración cinemática fija del hardware (cm por unidad de servo)
    cal_alto = float(marco_alto_cm) if marco_alto_cm is not None else (rango_dest_x if rango_dest_x > 0 else 1.0)
    cal_ancho = float(marco_ancho_cm) if marco_ancho_cm is not None else (rango_dest_y if rango_dest_y > 0 else 1.0)
    kx = cal_alto / rango_dest_x if rango_dest_x > 0 else 1.0
    ky = cal_ancho / rango_dest_y if rango_dest_y > 0 else 1.0

    # Centros destino
    dest_cx = float(centro_x) if centro_x is not None else (x_min_limit + x_max_limit) / 2.0
    dest_cy = float(centro_y) if centro_y is not None else (y_min_limit + y_max_limit) / 2.0

    # Marco óptico del escáner en cm (calibración física del hardware)
    marco_ref_w = float(marco_ancho_cm) if marco_ancho_cm is not None else cal_ancho
    marco_ref_h = float(marco_alto_cm) if marco_alto_cm is not None else cal_alto

    # Escala uniforme isométrica estricta (preserva proporción 1:1, nunca deforma la figura).
    # La escala física de la figura está gobernada exclusivamente por el marco óptico del escáner
    # y el parámetro 'escala' (Drawing scale a la izquierda), SIN alterarse por las dimensiones
    # de la base/material ni quedar confinada/recortada en un cuadrado artificial.
    scale_x = (marco_ref_w * escala) / rot_ancho
    scale_y = (marco_ref_h * escala) / rot_alto
    s_phys = min(scale_x, scale_y)  # Factor de escala físico uniforme en cm / unidad DXF
    sx = s_phys / kx
    sy = s_phys / ky

    trayectorias_transformadas = []

    for ruta in trayectorias:
        nueva_ruta = []
        ultimo_pt = None

        for x, y in ruta:
            # 1. Centrar en origen del DXF
            dx = x - dxf_cx
            dy = y - dxf_cy

            # 2. Rotar alrededor del centro
            rx = dx * cos_a - dy * sin_a
            ry = dx * sin_a + dy * cos_a

            # 3. Escalar y trasladar al centro destino
            phys_x = dest_cx + sx * rx
            phys_y = dest_cy + sy * ry

            # Clamping estricto de seguridad a los límites
            x_final = round(max(x_min_limit, min(x_max_limit, phys_x)), 3)
            y_final = round(max(y_min_limit, min(y_max_limit, phys_y)), 3)

            pt = (x_final, y_final)
            if pt != ultimo_pt:
                nueva_ruta.append(pt)
                ultimo_pt = pt

        # Cierre de bucles si la figura original estaba cerrada
        if len(ruta) >= 3:
            if math.hypot(ruta[-1][0] - ruta[0][0], ruta[-1][1] - ruta[0][1]) < 0.05:
                if len(nueva_ruta) >= 2 and nueva_ruta[0] != nueva_ruta[-1]:
                    nueva_ruta.append(nueva_ruta[0])

        if len(nueva_ruta) >= 2:
            trayectorias_transformadas.append(nueva_ruta)

    # Optimización de recorrido y unión de segmentos
    if optimizar_recorrido and len(trayectorias_transformadas) > 1:
        centro_reposo = (dest_cx, dest_cy)
        trayectorias_transformadas = optimizar_y_unir_trazos(
            trayectorias_transformadas,
            tol_union=tolerancia_union,
            pos_inicial=centro_reposo
        )

    # Simplificación RDP de vectores (elimina puntos colineales redundantes)
    if tolerancia_rdp > 0:
        simplificadas = []
        for ruta in trayectorias_transformadas:
            if len(ruta) >= 2:
                r_simp = simplificar_trayectoria_rdp(ruta, epsilon=tolerancia_rdp)
                simplificadas.append(r_simp if len(r_simp) >= 2 else ruta)
        trayectorias_transformadas = simplificadas

    # Filtrar micro-artefactos
    trazos_validos = []
    for ruta in trayectorias_transformadas:
        if len(ruta) >= 2:
            longitud = sum(math.hypot(ruta[k][0] - ruta[k - 1][0],
                                      ruta[k][1] - ruta[k - 1][1])
                           for k in range(1, len(ruta)))
            if longitud >= longitud_min_trazo:
                trazos_validos.append(ruta)

    return trazos_validos
