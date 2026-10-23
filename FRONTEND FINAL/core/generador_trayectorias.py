# -*- coding: utf-8 -*-
"""dxf vector scaling and geometric mapping"""

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
    """map dxf trajectories to hardware workspace with uniform scaling"""
    if not trayectorias:
        return []

    #determine effective rotation angle
    if rotacion_grados is not None:
        angulo_deg = float(rotacion_grados)
    else:
        angulo_deg = 0.0

    angulo_rad = math.radians(angulo_deg)
    cos_a = math.cos(angulo_rad)
    sin_a = math.sin(angulo_rad)

    min_x, max_x, min_y, max_y = obtener_limites_dxf(trayectorias)

    #dxf geometric center
    dxf_cx = (min_x + max_x) / 2.0
    dxf_cy = (min_y + max_y) / 2.0

    #calculate rotated dxf bounding box
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

    #hardware kinematic calibration
    cal_alto = float(marco_alto_cm) if marco_alto_cm is not None else (rango_dest_x if rango_dest_x > 0 else 1.0)
    cal_ancho = float(marco_ancho_cm) if marco_ancho_cm is not None else (rango_dest_y if rango_dest_y > 0 else 1.0)
    kx = cal_alto / rango_dest_x if rango_dest_x > 0 else 1.0
    ky = cal_ancho / rango_dest_y if rango_dest_y > 0 else 1.0

    #destination centers
    dest_cx = float(centro_x) if centro_x is not None else (x_min_limit + x_max_limit) / 2.0
    dest_cy = float(centro_y) if centro_y is not None else (y_min_limit + y_max_limit) / 2.0

    #scanner optical frame in cm
    marco_ref_w = float(marco_ancho_cm) if marco_ancho_cm is not None else cal_ancho
    marco_ref_h = float(marco_alto_cm) if marco_alto_cm is not None else cal_alto

    #strict isometric uniform scale
    scale_x = (marco_ref_w * escala) / rot_ancho
    scale_y = (marco_ref_h * escala) / rot_alto
    s_phys = min(scale_x, scale_y)  #physical scale factor
    sx = s_phys / kx
    sy = s_phys / ky

    trayectorias_transformadas = []

    for ruta in trayectorias:
        nueva_ruta = []
        ultimo_pt = None

        for x, y in ruta:
            #center at dxf origin
            dx = x - dxf_cx
            dy = y - dxf_cy

            #rotate around center
            rx = dx * cos_a - dy * sin_a
            ry = dx * sin_a + dy * cos_a

            #scale and translate to destination center
            phys_x = dest_cx + sx * rx
            phys_y = dest_cy + sy * ry

            #strict safety limit clamping
            x_final = round(max(x_min_limit, min(x_max_limit, phys_x)), 3)
            y_final = round(max(y_min_limit, min(y_max_limit, phys_y)), 3)

            pt = (x_final, y_final)
            if pt != ultimo_pt:
                nueva_ruta.append(pt)
                ultimo_pt = pt

        #close loops if original was closed
        if len(ruta) >= 3:
            if math.hypot(ruta[-1][0] - ruta[0][0], ruta[-1][1] - ruta[0][1]) < 0.05:
                if len(nueva_ruta) >= 2 and nueva_ruta[0] != nueva_ruta[-1]:
                    nueva_ruta.append(nueva_ruta[0])

        if len(nueva_ruta) >= 2:
            trayectorias_transformadas.append(nueva_ruta)

        #optimize paths and merge segments
    if optimizar_recorrido and len(trayectorias_transformadas) > 1:
        centro_reposo = (dest_cx, dest_cy)
        trayectorias_transformadas = optimizar_y_unir_trazos(
            trayectorias_transformadas,
            tol_union=tolerancia_union,
            pos_inicial=centro_reposo
        )

    #rdp vector simplification
    if tolerancia_rdp > 0:
        simplificadas = []
        for ruta in trayectorias_transformadas:
            if len(ruta) >= 2:
                r_simp = simplificar_trayectoria_rdp(ruta, epsilon=tolerancia_rdp)
                simplificadas.append(r_simp if len(r_simp) >= 2 else ruta)
        trayectorias_transformadas = simplificadas

    #filter micro artifacts
    trazos_validos = []
    for ruta in trayectorias_transformadas:
        if len(ruta) >= 2:
            longitud = sum(math.hypot(ruta[k][0] - ruta[k - 1][0],
                                      ruta[k][1] - ruta[k - 1][1])
                           for k in range(1, len(ruta)))
            if longitud >= longitud_min_trazo:
                trazos_validos.append(ruta)

    return trazos_validos

