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
                               base_ancho_cm=None,
                               base_alto_cm=None,
                               area_x_min=None, area_x_max=None,
                               area_y_min=None, area_y_max=None,
                               *args, **kwargs):
    """map dxf trajectories to hardware workspace with uniform scaling

    marco_*_cm: physical size covered by the full hardware range (calibration).
    base_*_cm: physical base (work area) centered on the hardware origin; the drawing is scaled
    to fit inside it (never larger than the optical frame).
    area_*: base perimeter in hardware units, used as the clamping box (defaults to the limits).
    """
    if not trayectorias:
        return []

    angulo_rad = math.radians(float(rotacion_grados or 0.0))
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
    rot_ancho = max(0.001, max(rotated_xs) - min(rotated_xs))
    rot_alto = max(0.001, max(rotated_ys) - min(rotated_ys))

    rango_dest_x = x_max_limit - x_min_limit
    rango_dest_y = y_max_limit - y_min_limit

    #hardware kinematic calibration: x axis <-> width, y axis <-> height
    cal_ancho = float(marco_ancho_cm) if marco_ancho_cm is not None else (rango_dest_x if rango_dest_x > 0 else 1.0)
    cal_alto = float(marco_alto_cm) if marco_alto_cm is not None else (rango_dest_y if rango_dest_y > 0 else 1.0)
    kx = cal_ancho / rango_dest_x if rango_dest_x > 0 else 1.0
    ky = cal_alto / rango_dest_y if rango_dest_y > 0 else 1.0

    #usable work area in cm: the base, never larger than the optical frame
    work_ancho = min(float(base_ancho_cm), cal_ancho) if base_ancho_cm is not None else cal_ancho
    work_alto = min(float(base_alto_cm), cal_alto) if base_alto_cm is not None else cal_alto

    #clamping box (base perimeter), always inside the hardware limits
    clamp_x_min = x_min_limit if area_x_min is None else max(x_min_limit, float(area_x_min))
    clamp_x_max = x_max_limit if area_x_max is None else min(x_max_limit, float(area_x_max))
    clamp_y_min = y_min_limit if area_y_min is None else max(y_min_limit, float(area_y_min))
    clamp_y_max = y_max_limit if area_y_max is None else min(y_max_limit, float(area_y_max))

    #destination centers
    dest_cx = float(centro_x) if centro_x is not None else (x_min_limit + x_max_limit) / 2.0
    dest_cy = float(centro_y) if centro_y is not None else (y_min_limit + y_max_limit) / 2.0

    #strict isometric uniform scale over the scanner optical frame in cm
    s_phys = min(work_ancho * escala / rot_ancho, work_alto * escala / rot_alto)
    sx = s_phys / kx
    sy = s_phys / ky

    trayectorias_transformadas = []

    for ruta in trayectorias:
        nueva_ruta = []
        ultimo_pt = None

        for x, y in ruta:
            dx = x - dxf_cx
            dy = y - dxf_cy

            #rotate around dxf center, scale and translate to destination center
            phys_x = dest_cx + sx * (dx * cos_a - dy * sin_a)
            phys_y = dest_cy + sy * (dx * sin_a + dy * cos_a)

            #strict safety limit clamping
            pt = (round(max(clamp_x_min, min(clamp_x_max, phys_x)), 3),
                  round(max(clamp_y_min, min(clamp_y_max, phys_y)), 3))
            if pt != ultimo_pt:
                nueva_ruta.append(pt)
                ultimo_pt = pt

        #close loops if original was closed
        if (len(ruta) >= 3 and math.dist(ruta[0], ruta[-1]) < 0.05
                and len(nueva_ruta) >= 2 and nueva_ruta[0] != nueva_ruta[-1]):
            nueva_ruta.append(nueva_ruta[0])

        if len(nueva_ruta) >= 2:
            trayectorias_transformadas.append(nueva_ruta)

    #optimize paths and merge segments
    if optimizar_recorrido and len(trayectorias_transformadas) > 1:
        trayectorias_transformadas = optimizar_y_unir_trazos(
            trayectorias_transformadas,
            tol_union=tolerancia_union,
            pos_inicial=(dest_cx, dest_cy)
        )

    #rdp vector simplification
    if tolerancia_rdp > 0:
        simplificadas = []
        for ruta in trayectorias_transformadas:
            r_simp = simplificar_trayectoria_rdp(ruta, epsilon=tolerancia_rdp)
            simplificadas.append(r_simp if len(r_simp) >= 2 else ruta)
        trayectorias_transformadas = simplificadas

    #filter micro artifacts
    return [
        ruta for ruta in trayectorias_transformadas
        if sum(math.dist(a, b) for a, b in zip(ruta, ruta[1:])) >= longitud_min_trazo
    ]

