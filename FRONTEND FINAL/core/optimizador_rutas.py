# -*- coding: utf-8 -*-
"""
core/optimizador_rutas.py — Algoritmos de Optimización de Trayectorias Vectoriales

Incluye:
  1. Simplificación RDP (Ramer-Douglas-Peucker) para eliminar puntos colineales redundantes.
  2. Algoritmo TSP de Vecinos Más Cercanos (Greedy Nearest Neighbor) con inversión de sentido.
  3. Heurística 2-Opt para eliminar cruces de traslados en vacío (láser apagado).
  4. Fusión de trazos continuos contiguos y cierre de bucles.
"""

import math

def simplificar_trayectoria_rdp(puntos, epsilon=0.01):
    #Algoritmo Ramer-Douglas-Peucker (RDP) para simplificacion vectorial
    #Reduce la cantidad de puntos en lineas rectas manteniendo la fidelidad en esquinas y curvas
    
    if len(puntos) < 3:
        return puntos

    p_inicio = puntos[0]
    p_fin = puntos[-1]

    dmax = 0.0
    index = 0

    dx = p_fin[0] - p_inicio[0]
    dy = p_fin[1] - p_inicio[1]
    norma = math.hypot(dx, dy)

    for i in range(1, len(puntos) - 1):
        p = puntos[i]
        if norma == 0.0:
            d = math.hypot(p[0] - p_inicio[0], p[1] - p_inicio[1])
        else:
            d = abs(dy * p[0] - dx * p[1] + p_fin[0] * p_inicio[1] - p_fin[1] * p_inicio[0]) / norma
        if d > dmax:
            index = i
            dmax = d

    if dmax > epsilon:
        res1 = simplificar_trayectoria_rdp(puntos[:index + 1], epsilon)
        res2 = simplificar_trayectoria_rdp(puntos[index:], epsilon)
        return res1[:-1] + res2
    else:
        return [p_inicio, p_fin]


def optimizar_y_unir_trazos(trayectorias, tol_union=0.02, pos_inicial=(0.0, 0.0)):
    """
    Optimiza el orden de dibujo de los trazos vectoriales y fusiona líneas contiguas:
      1. Greedy Nearest-Neighbor (Vecino Más Cercano) con inversión bidireccional de trazo.
      2. Heurística 2-Opt (TSP) para eliminar cruces en los viajes en vacío.
      3. Fusión de trazos continuos cuyos extremos distan <= tol_union.
      4. Cierre automático de bucles cerrados.
    """
    if not trayectorias:
        return []

    restantes = [list(r) for r in trayectorias if len(r) >= 2]
    if not restantes:
        return []

    ordenados = []
    pos_actual = pos_inicial

    #Greedy Nearest-Neighbor
    while restantes:
        mejor_idx = 0
        mejor_dist = float('inf')
        invertir = False

        for i, trazo in enumerate(restantes):
            d_ini = math.hypot(trazo[0][0] - pos_actual[0], trazo[0][1] - pos_actual[1])
            d_fin = math.hypot(trazo[-1][0] - pos_actual[0], trazo[-1][1] - pos_actual[1])

            if d_ini < mejor_dist:
                mejor_dist = d_ini
                mejor_idx = i
                invertir = False
            if d_fin < mejor_dist:
                mejor_dist = d_fin
                mejor_idx = i
                invertir = True

        trazo_elegido = restantes.pop(mejor_idx)
        if invertir:
            trazo_elegido = trazo_elegido[::-1]

        ordenados.append(trazo_elegido)
        pos_actual = ordenados[-1][-1]

    #Heuristica 2-Opt para TSP
    def _dist_total_viajes(trazos):
        d = 0.0
        for k in range(len(trazos) -1):
            d += math.hypot(trazos[k][-1][0] - trazos[k + 1][0][0],trazos[k][-1][1] - trazos[k + 1][0][1])
        return d

    n = len(ordenados)
    if n > 2:
        mejor_dist = _dist_total_viajes(ordenados)
        mejora = True
        iter_count = 0
        while mejora and iter_count < 50:
            mejora = False
            iter_count += 1
            for i in range(n - 1):
                for j in range(i + 1, n):
                    nuevo_sub = [t[::-1] for t in reversed(ordenados[i:j + 1])]
                    candidato = ordenados[:i] + nuevo_sub + ordenados[j + 1:]
                    d_cand = _dist_total_viajes(candidato)
                    if d_cand < mejor_dist - 1e-4:
                        mejor_dist = d_cand
                        ordenados = candidato
                        mejora = True
                        break
                if mejora:
                    break

    #Fusión de trazos contiguos
    fusionados = []
    for trazo in ordenados:
        if fusionados and math.hypot(trazo[0][0] - fusionados[-1][-1][0],
                                    trazo[0][1] - fusionados[-1][-1][1]) <= tol_union:
            fusionados[-1].extend(trazo[1:])
        else:
            fusionados.append(trazo)

    #Cierre de bucles
    for trazo in fusionados:
        if len(trazo) >= 3:
            dist_cierre = math.hypot(trazo[-1][0] - trazo[0][0], trazo[-1][1] - trazo[0][1])
            if 0.0001 < dist_cierre <= (tol_union * 1.5):
                trazo.append(trazo[0])

    return fusionados
