# -*- coding: utf-8 -*-
"""
core/visualizador.py — Generador Universal de Previsualizacion Gráfica

Genera un reporte gráfico (PNG) comparativo:
  - Panel izquierdo: Espacio CAD original
  - Panel derecho: Espacio de trabajo de la máquina destino
  - Muestra lineas de corte/trazado (laser ON) y traslados (laser OFF)
  - Diagnóstico de entidades geometricas
"""

import os
import colorsys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.ticker as ticker

from .lector_dxf import LectorDXF, obtener_limites_dxf

def generar_colores(n):
    if n == 0:
        return []
    colores = []
    for i in range(n):
        h = (i / n) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.85, 0.90)
        colores.append((r, g, b))
    return colores

def generar_previsualizacion(nombre_dxf, tray_orig, tray_cal, limites_maquina, nombre_salida=None, mostrar_puntos=False):
    """
    Genera una imagen comparativa del DXF vs la máquina destino.
    """
    if nombre_salida is None:
        base = os.path.splitext(os.path.basename(nombre_dxf))[0]
        nombre_salida = f"{base}_preview.png"

    x_min_lim, x_max_lim = limites_maquina['x_min'], limites_maquina['x_max']
    y_min_lim, y_max_lim = limites_maquina['y_min'], limites_maquina['y_max']
    centro_x = (x_min_lim + x_max_lim) / 2.0
    centro_y = (y_min_lim + y_max_lim) / 2.0

    min_xo, max_xo, min_yo, max_yo = obtener_limites_dxf(tray_orig)
    min_xc, max_xc, min_yc, max_yc = obtener_limites_dxf(tray_cal)
    ancho_dxf = max_xo - min_xo
    alto_dxf  = max_yo - min_yo
    pts_orig  = sum(len(r) for r in tray_orig)
    pts_cal   = sum(len(r) for r in tray_cal)

    viajes = []
    pos = (centro_x, centro_y)
    for trazo in tray_cal:
        if trazo:
            viajes.append((pos, trazo[0]))
            pos = trazo[-1]
    viajes.append((pos, (centro_x, centro_y)))

    colores = generar_colores(len(tray_cal))

    fig = plt.figure(figsize=(16, 8), facecolor='#1a1a2e')
    fig.suptitle(
        f"Previsualizacion de Trazado Laser — {os.path.basename(nombre_dxf)}",
        color='white', fontsize=14, fontweight='bold', y=0.98
    )

    # Panel Izquierdo: CAD Original
    ax_orig = fig.add_subplot(1, 2, 1, facecolor='#16213e')
    ax_orig.set_title('DXF Original (Espacio CAD)', color='#e0e0e0', fontsize=11, pad=8)
    for i, trazo in enumerate(tray_orig):
        xs = [p[0] for p in trazo]
        ys = [p[1] for p in trazo]
        col = colores[i % len(colores)] if colores else '#ff4444'
        ax_orig.plot(xs, ys, '-', color=col, linewidth=0.8, alpha=0.9, zorder=3)
        if mostrar_puntos:
            ax_orig.plot(xs, ys, '.', color=col, markersize=1.5, alpha=0.5, zorder=4)

    bb_x = [min_xo, max_xo, max_xo, min_xo, min_xo]
    bb_y = [min_yo, min_yo, max_yo, max_yo, min_yo]
    ax_orig.plot(bb_x, bb_y, '--', color='#666688', linewidth=0.8, alpha=0.5)
    mx = (max_xo - min_xo) * 0.08 if max_xo != min_xo else 1.0
    my = (max_yo - min_yo) * 0.08 if max_yo != min_yo else 1.0
    ax_orig.set_xlim(min_xo - mx, max_xo + mx)
    ax_orig.set_ylim(min_yo - my, max_yo + my)
    ax_orig.set_aspect('equal', adjustable='box')
    ax_orig.set_xlabel('CAD X (unidades DXF)', color='#aaaacc', fontsize=9)
    ax_orig.set_ylabel('CAD Y (unidades DXF)', color='#aaaacc', fontsize=9)
    ax_orig.tick_params(colors='#888899', labelsize=7)
    ax_orig.grid(True, color='#2a2a4a', linewidth=0.5, alpha=0.7)
    for spine in ax_orig.spines.values():
        spine.set_edgecolor('#3a3a6a')

    resumen_orig = (
        f"Trazos: {len(tray_orig)}  |  Puntos: {pts_orig}\n"
        f"Dimensiones CAD: {ancho_dxf:.2f} x {alto_dxf:.2f} u"
    )
    ax_orig.text(0.02, 0.02, resumen_orig, transform=ax_orig.transAxes,
        color='#aabbcc', fontsize=8, verticalalignment='bottom',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='#0f0f1e', alpha=0.7, edgecolor='#3a3a6a'))

    # Panel Derecho: Máquina Destino
    ax_cal = fig.add_subplot(1, 2, 2, facecolor='#16213e')
    ax_cal.set_title('Espacio de Trabajo Calibrado', color='#e0e0e0', fontsize=11, pad=8)
    rect_xs = [x_min_lim, x_max_lim, x_max_lim, x_min_lim, x_min_lim]
    rect_ys = [y_min_lim, y_min_lim, y_max_lim, y_max_lim, y_min_lim]
    ax_cal.fill(rect_xs, rect_ys, color='#0d0d20', alpha=0.6, zorder=1)
    ax_cal.plot(rect_xs, rect_ys, '-', color='#5588bb', linewidth=1.5, zorder=5)

    ax_cal.plot(centro_x, centro_y, '+', color='#88aacc', markersize=10, markeredgewidth=1.2, zorder=6)

    for (x0, y0), (x1, y1) in viajes:
        ax_cal.plot([x0, x1], [y0, y1], '--', color='#444466', linewidth=0.6, alpha=0.7, zorder=2)

    for i, trazo in enumerate(tray_cal):
        xs = [p[0] for p in trazo]
        ys = [p[1] for p in trazo]
        col = colores[i % len(colores)] if colores else '#ff4444'
        ax_cal.plot(xs, ys, '-', color=col, linewidth=1.0, alpha=0.95, zorder=4)
        if mostrar_puntos:
            ax_cal.plot(xs, ys, '.', color=col, markersize=2.0, alpha=0.6, zorder=5)
        ax_cal.plot(trazo[0][0], trazo[0][1], '^', color=col, markersize=4, zorder=6, alpha=0.8)

    margen_cal_x = (x_max_lim - x_min_lim) * 0.1
    margen_cal_y = (y_max_lim - y_min_lim) * 0.1
    ax_cal.set_xlim(x_min_lim - margen_cal_x, x_max_lim + margen_cal_x)
    ax_cal.set_ylim(y_min_lim - margen_cal_y, y_max_lim + margen_cal_y)
    ax_cal.set_aspect('equal', adjustable='box')
    ax_cal.set_xlabel('Eje X Máquina', color='#aaaacc', fontsize=9)
    ax_cal.set_ylabel('Eje Y Máquina', color='#aaaacc', fontsize=9)
    ax_cal.tick_params(colors='#888899', labelsize=7)
    ax_cal.grid(True, color='#2a2a4a', linewidth=0.5, alpha=0.7)
    for spine in ax_cal.spines.values():
        spine.set_edgecolor('#3a3a6a')

    ancho_cal = round(max_xc - min_xc, 3)
    alto_cal  = round(max_yc - min_yc, 3)
    resumen_cal = (
        f"Trazos: {len(tray_cal)}  |  Waypoints: {pts_cal}\n"
        f"BBox Máquina: {ancho_cal} x {alto_cal} u\n"
        f"Limites: X[{x_min_lim:.1f}, {x_max_lim:.1f}], Y[{y_min_lim:.1f}, {y_max_lim:.1f}]"
    )
    ax_cal.text(0.02, 0.02, resumen_cal, transform=ax_cal.transAxes,
        color='#aabbcc', fontsize=8, verticalalignment='bottom',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='#0f0f1e', alpha=0.7, edgecolor='#3a3a6a'))

    leyenda = [
        Line2D([0],[0], color='#ff6655', linewidth=1.5, label='Trazo Laser (ON)'),
        Line2D([0],[0], color='#444466', linewidth=1.0, linestyle='--', label='Traslado Vacío (OFF)'),
        Line2D([0],[0], color='#5588bb', linewidth=1.5, label='Limites Máquina'),
    ]
    ax_cal.legend(handles=leyenda, loc='upper right', fontsize=7,
                  facecolor='#0f0f1e', edgecolor='#3a3a6a', labelcolor='#ccccdd')

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(nombre_salida, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Previsualizacion guardada: {os.path.abspath(nombre_salida)}")
    return nombre_salida
