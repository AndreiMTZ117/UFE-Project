# -*- coding: utf-8 -*-
"""
visualizar_comparativa.py — Visualizador Comparativo: CAD DXF Original vs. Trayectoria Optimizada

Genera una comparativa gráfica exhaustiva de alta resolución que contrasta:
  1. Espacio CAD Original: geometrías sin procesar, orden de corte desordenado, vértices brutos.
  2. Espacio de Trabajo Galvo: trayectorias continuas optimizadas (TSP 2-Opt), filtrado RDP,
     escala métrica calibrada, delimitación del campo óptico (Thorlabs GVS112/M) y líneas de salto.
  3. Diagnóstico Cuantitativo: % de reducción en saltos en vacío, % de reducción de nodos y tiempos.
     (Organizado en tarjetas independientes debajo de cada dibujo para evitar cualquier superposición).

Uso:
  python visualizar_comparativa.py                           # Modo interactivo / selección automática
  python visualizar_comparativa.py dxf/head.dxf              # Visualiza un DXF específico
  python visualizar_comparativa.py dxf/batman.dxf --guardar  # Guarda imagen PNG comparativa
  python visualizar_comparativa.py --todos --guardar        # Genera comparativas para todos los DXF
  python visualizar_comparativa.py dxf/head.dxf --no-gui     # Modo headless para servidores / scripts
"""

import os
import sys
import math
import argparse
import glob
import colorsys

# Asegurar importación de módulos del proyecto
_DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
_DIR_PROYECTO = os.path.abspath(os.path.join(_DIR_ACTUAL, "..", "..", "FRONTEND FINAL - v0.1"))
for p in [_DIR_ACTUAL, _DIR_PROYECTO]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np

try:
    from core.lector_dxf import LectorDXF, obtener_limites_dxf
    from core.generador_trayectorias import transformar_y_escalar_dxf
    from hardware.config_galvo import (
        CAMPO_X_MIN_MM, CAMPO_X_MAX_MM,
        CAMPO_Y_MIN_MM, CAMPO_Y_MAX_MM,
        LIMITES_GALVO, ESCALA_DIBUJO,
        VELOCIDAD_MARCADO_MM_S, VELOCIDAD_SALTO_MM_S,
        LASER_ON_DELAY_US, LASER_OFF_DELAY_US,
        JUMP_DELAY_US, MARK_DELAY_US
    )
except ImportError:
    try:
        from core.lector_dxf import LectorDXF, obtener_limites_dxf
        from core.generador_trayectorias import transformar_y_escalar_dxf
    except ImportError:
        sys.path.insert(0, r"c:\Andrei\Documents\RESIDENCIA PROFESIONAL -------------------------------------------\PROYECTO\FRONTEND FINAL - v0.1")
        from core.lector_dxf import LectorDXF, obtener_limites_dxf
        from core.generador_trayectorias import transformar_y_escalar_dxf
    CAMPO_X_MIN_MM, CAMPO_X_MAX_MM = -50.0, 50.0
    CAMPO_Y_MIN_MM, CAMPO_Y_MAX_MM = -50.0, 50.0
    LIMITES_GALVO = {'x_min': -50.0, 'x_max': 50.0, 'y_min': -50.0, 'y_max': 50.0}
    ESCALA_DIBUJO = 0.85
    VELOCIDAD_MARCADO_MM_S = 500.0
    VELOCIDAD_SALTO_MM_S = 2000.0
    LASER_ON_DELAY_US, LASER_OFF_DELAY_US = 20, 20
    JUMP_DELAY_US, MARK_DELAY_US = 150, 50


def generar_paleta_colores(n):
    """Genera una paleta cíclica de colores vibrantes y contrastantes en espacio HSV."""
    if n <= 0:
        return ['#00FFCC']
    colores = []
    for i in range(n):
        h = (i / max(1, n)) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.85, 0.95)
        colores.append((r, g, b))
    return colores


def calcular_longitud_trazo(puntos):
    """Calcula la distancia acumulada de corte de un contorno poli-línea."""
    d = 0.0
    for i in range(len(puntos) - 1):
        d += math.hypot(puntos[i+1][0] - puntos[i][0], puntos[i+1][1] - puntos[i][1])
    return d


def calcular_viajes_rapidos(trazos, punto_origen=(0.0, 0.0)):
    """
    Calcula los saltos en vacío (G0 / Láser OFF) entre el final de un trazo
    y el inicio del siguiente, iniciando y finalizando en el punto de reposo (Home).
    """
    viajes = []
    dist_total = 0.0
    pos_actual = punto_origen
    for trazo in trazos:
        if trazo and len(trazo) > 0:
            inicio = trazo[0]
            viajes.append((pos_actual, inicio))
            dist_total += math.hypot(inicio[0] - pos_actual[0], inicio[1] - pos_actual[1])
            pos_actual = trazo[-1]
    viajes.append((pos_actual, punto_origen))
    dist_total += math.hypot(punto_origen[0] - pos_actual[0], punto_origen[1] - pos_actual[1])
    return viajes, dist_total


def generar_grafico_comparativo(
    ruta_dxf,
    escala=ESCALA_DIBUJO,
    rotacion_grados=0.0,
    tolerancia_rdp=0.025,
    tolerancia_union=0.05,
    limites_campo=LIMITES_GALVO,
    guardar_imagen=True,
    mostrar_gui=True,
    archivo_salida=None
):
    """
    Carga el DXF, procesa la optimización y genera el lienzo comparativo.
    Separa limpiamente los gráficos de las tarjetas de diagnóstico para evitar superposición.
    """
    if not os.path.exists(ruta_dxf):
        print(f"[ERROR] Archivo DXF no encontrado: {ruta_dxf}")
        return None

    nombre_base = os.path.splitext(os.path.basename(ruta_dxf))[0]
    if archivo_salida is None:
        archivo_salida = f"{nombre_base}_comparativa_optimizada.png"

    print(f"\n================================================================================")
    print(f"PROCESANDO COMPARATIVA: {os.path.basename(ruta_dxf)}")
    print(f"================================================================================")

    # 1. EXTRACCIÓN DEL ESPACIO CAD ORIGINAL
    lector = LectorDXF(ruta_dxf)
    trazos_originales = lector.extraer_coordenadas()
    if not trazos_originales:
        print(f"[ERROR] El archivo {ruta_dxf} no contiene primitivas geométricas legibles.")
        return None

    min_xo, max_xo, min_yo, max_yo = obtener_limites_dxf(trazos_originales)
    ancho_orig = max_xo - min_xo
    alto_orig = max_yo - min_yo
    num_trazos_orig = len(trazos_originales)
    num_pts_orig = sum(len(t) for t in trazos_originales)
    long_corte_orig = sum(calcular_longitud_trazo(t) for t in trazos_originales)

    centro_cad = ((min_xo + max_xo) / 2.0, (min_yo + max_yo) / 2.0)
    viajes_orig, dist_viaje_orig = calcular_viajes_rapidos(trazos_originales, punto_origen=centro_cad)

    # 2. TRANSFORMACIÓN, ESCALADO Y OPTIMIZACIÓN (ESPACIO MÁQUINA GALVO)
    x_min, x_max = limites_campo['x_min'], limites_campo['x_max']
    y_min, y_max = limites_campo['y_min'], limites_campo['y_max']
    centro_galvo = (0.0, 0.0)

    trazos_optimizados = transformar_y_escalar_dxf(
        trazos_originales,
        x_min, x_max, y_min, y_max,
        escala=escala,
        rotacion_grados=rotacion_grados,
        tolerancia_rdp=tolerancia_rdp,
        tolerancia_union=tolerancia_union,
        longitud_min_trazo=0.01,
        optimizar_recorrido=True,
        centro_x=centro_galvo[0],
        centro_y=centro_galvo[1]
    )

    min_xc, max_xc, min_yc, max_yc = obtener_limites_dxf(trazos_optimizados)
    ancho_opt = max_xc - min_xc
    alto_opt = max_yc - min_yc
    num_trazos_opt = len(trazos_optimizados)
    num_pts_opt = sum(len(t) for t in trazos_optimizados)
    long_corte_opt = sum(calcular_longitud_trazo(t) for t in trazos_optimizados)

    viajes_opt, dist_viaje_opt = calcular_viajes_rapidos(trazos_optimizados, punto_origen=centro_galvo)

    # 3. CÁLCULO DE MÉTRICAS DE RENDIMIENTO
    escala_geom = ancho_opt / max(0.0001, ancho_orig)
    dist_viaje_orig_escalada = dist_viaje_orig * escala_geom

    if dist_viaje_orig_escalada > 0:
        ahorro_viaje_pct = max(0.0, ((dist_viaje_orig_escalada - dist_viaje_opt) / dist_viaje_orig_escalada) * 100.0)
    else:
        ahorro_viaje_pct = 0.0

    if num_pts_orig > 0:
        reduccion_nodos_pct = max(0.0, ((num_pts_orig - num_pts_opt) / num_pts_orig) * 100.0)
    else:
        reduccion_nodos_pct = 0.0

    t_marcado = long_corte_opt / VELOCIDAD_MARCADO_MM_S
    t_viaje = dist_viaje_opt / VELOCIDAD_SALTO_MM_S
    t_delays = (num_trazos_opt * (LASER_ON_DELAY_US + LASER_OFF_DELAY_US + JUMP_DELAY_US + MARK_DELAY_US)) / 1_000_000.0
    t_ciclo_total = t_marcado + t_viaje + t_delays

    print(f"[*] CAD Original    : {num_trazos_orig:>4} trazos | {num_pts_orig:>5} pts | Dim: {ancho_orig:.1f}x{alto_orig:.1f} u | Viaje: {dist_viaje_orig:.1f} u")
    print(f"[*] Galvo Optimizado: {num_trazos_opt:>4} trazos | {num_pts_opt:>5} pts | Dim: {ancho_opt:.1f}x{alto_opt:.1f} mm | Viaje: {dist_viaje_opt:.1f} mm")
    print(f"[+] Reducción de Saltos en Vacío (TSP 2-Opt) : {ahorro_viaje_pct:.1f}%")
    print(f"[+] Reducción de Densidad Nodal (RDP {tolerancia_rdp} mm): {reduccion_nodos_pct:.1f}%")
    print(f"[+] Fusión de Contornos Contiguos             : {num_trazos_orig} -> {num_trazos_opt} contornos")
    print(f"[+] Tiempo Estimado de Ejecución             : {t_ciclo_total:.2f} s")

    # 4. RENDERIZADO GRÁFICO (CON SUBPLOTS DEDICADOS PARA INFORMACIÓN)
    if not mostrar_gui:
        matplotlib.use('Agg')

    plt.style.use('dark_background')
    fig = plt.figure(figsize=(18, 10.5), facecolor='#0B0F19')

    # GridSpec con 2 filas: Fila 0 para los dibujos, Fila 1 para las tarjetas de diagnóstico
    # 'top=0.86' y 'suptitle y=0.965' garantizan separación total entre el encabezado principal y los títulos
    gs = fig.add_gridspec(
        nrows=2, ncols=2,
        height_ratios=[1.0, 0.22],
        hspace=0.18, wspace=0.15,
        top=0.86, bottom=0.03, left=0.05, right=0.96
    )

    fig.suptitle(
        f"DIAGNÓSTICO COMPARATIVO: VECTOR CAD vs. TRAYECTORIA OPTIMIZADA (THORLABS GVS112/M)\n"
        f"Archivo: {os.path.basename(ruta_dxf)}  |  Algoritmo: TSP 2-Opt + RDP Filter ({tolerancia_rdp} mm)",
        color='#F3F4F6', fontsize=12.0, fontweight='bold', y=0.955, fontfamily='monospace'
    )

    paleta_colores_orig = generar_paleta_colores(num_trazos_orig)
    paleta_colores_opt = generar_paleta_colores(num_trazos_opt)

    # -------------------------------------------------------------------------
    # PANEL SUPERIOR IZQUIERDO: DIBUJO CAD ORIGINAL (LIMPIO DE TEXTO ENCIMADO)
    # -------------------------------------------------------------------------
    ax_orig = fig.add_subplot(gs[0, 0], facecolor='#111827')
    ax_orig.set_title(
        "1. ESPACIO CAD ORIGINAL (DXF SIN PROCESAR)",
        color='#93C5FD', fontsize=11, fontweight='bold', pad=8, fontfamily='monospace'
    )

    # Saltos en vacío desordenados
    for (x0, y0), (x1, y1) in viajes_orig:
        ax_orig.plot([x0, x1], [y0, y1], ':', color='#EF4444', linewidth=0.75, alpha=0.55, zorder=2)

    # Trazos originales
    for i, trazo in enumerate(trazos_originales):
        xs = [p[0] for p in trazo]
        ys = [p[1] for p in trazo]
        color_trazo = paleta_colores_orig[i % len(paleta_colores_orig)]
        ax_orig.plot(xs, ys, '-', color=color_trazo, linewidth=1.2, alpha=0.95, zorder=4)
        ax_orig.plot(xs, ys, '.', color=color_trazo, markersize=2.0, alpha=0.6, zorder=5)

    # Bounding Box
    bb_x = [min_xo, max_xo, max_xo, min_xo, min_xo]
    bb_y = [min_yo, min_yo, max_yo, max_yo, min_yo]
    ax_orig.plot(bb_x, bb_y, '--', color='#6B7280', linewidth=1.0, alpha=0.7, zorder=3)

    margen_x = max(0.5, ancho_orig * 0.10)
    margen_y = max(0.5, alto_orig * 0.10)
    ax_orig.set_xlim(min_xo - margen_x, max_xo + margen_x)
    ax_orig.set_ylim(min_yo - margen_y, max_yo + margen_y)
    ax_orig.set_aspect('equal', adjustable='box')
    ax_orig.grid(True, color='#1F2937', linestyle='--', linewidth=0.5, alpha=0.7)
    ax_orig.set_xlabel("Coordenada X (Unidades CAD DXF)", color='#9CA3AF', fontsize=8.5, fontfamily='monospace')
    ax_orig.set_ylabel("Coordenada Y (Unidades CAD DXF)", color='#9CA3AF', fontsize=8.5, fontfamily='monospace')
    ax_orig.tick_params(colors='#9CA3AF', labelsize=8)
    for spine in ax_orig.spines.values():
        spine.set_color('#374151')

    leyenda_orig = [
        Line2D([0], [0], color='#10B981', linewidth=1.5, label='Entidades CAD (ON)'),
        Line2D([0], [0], color='#EF4444', linewidth=1.0, linestyle=':', label='Salto Desordenado (OFF)'),
        Line2D([0], [0], color='#6B7280', linewidth=1.0, linestyle='--', label='Caja Delimitadora'),
    ]
    ax_orig.legend(handles=leyenda_orig, loc='upper right', fontsize=7.5, facecolor='#0B0F19', edgecolor='#374151', framealpha=0.75)

    # -------------------------------------------------------------------------
    # PANEL SUPERIOR DERECHO: DIBUJO GALVO OPTIMIZADO (LIMPIO DE TEXTO ENCIMADO)
    # -------------------------------------------------------------------------
    ax_opt = fig.add_subplot(gs[0, 1], facecolor='#111827')
    ax_opt.set_title(
        "2. ESPACIO GALVO CALIBRADO Y OPTIMIZADO (THORLABS ±50 mm / ±10V)",
        color='#34D399', fontsize=11, fontweight='bold', pad=8, fontfamily='monospace'
    )

    # Campo óptico
    campo_rect = Rectangle(
        (x_min, y_min), x_max - x_min, y_max - y_min,
        fill=True, facecolor='#080D1A', edgecolor='#3B82F6', linewidth=1.5, linestyle='-', zorder=1
    )
    ax_opt.add_patch(campo_rect)

    # Ejes y centro Home
    ax_opt.axhline(0, color='#1E3A8A', linestyle='--', linewidth=0.8, alpha=0.8, zorder=2)
    ax_opt.axvline(0, color='#1E3A8A', linestyle='--', linewidth=0.8, alpha=0.8, zorder=2)
    ax_opt.plot(0, 0, '+', color='#F59E0B', markersize=12, markeredgewidth=2.0, zorder=7)

    # Saltos en vacío optimizados TSP
    for (x0, y0), (x1, y1) in viajes_opt:
        ax_opt.plot([x0, x1], [y0, y1], '--', color='#F59E0B', linewidth=1.0, alpha=0.85, zorder=3)

    # Trazos continuos optimizados
    for i, trazo in enumerate(trazos_optimizados):
        xs = [p[0] for p in trazo]
        ys = [p[1] for p in trazo]
        color_trazo = paleta_colores_opt[i % len(paleta_colores_opt)]
        ax_opt.plot(xs, ys, '-', color=color_trazo, linewidth=1.4, alpha=0.98, zorder=4)
        ax_opt.plot(xs, ys, '.', color=color_trazo, markersize=2.5, alpha=0.7, zorder=5)
        ax_opt.plot(trazo[0][0], trazo[0][1], '^', color='#10B981', markersize=5.5, zorder=6)
        ax_opt.plot(trazo[-1][0], trazo[-1][1], 's', color='#EF4444', markersize=4.5, zorder=6)

    margen_campo_x = (x_max - x_min) * 0.08
    margen_campo_y = (y_max - y_min) * 0.08
    ax_opt.set_xlim(x_min - margen_campo_x, x_max + margen_campo_x)
    ax_opt.set_ylim(y_min - margen_campo_y, y_max + margen_campo_y)
    ax_opt.set_aspect('equal', adjustable='box')
    ax_opt.grid(True, color='#1F2937', linestyle='--', linewidth=0.5, alpha=0.7)
    ax_opt.set_xlabel("Eje Óptico X [mm] (±10V a 0.200 V/mm)", color='#9CA3AF', fontsize=8.5, fontfamily='monospace')
    ax_opt.set_ylabel("Eje Óptico Y [mm] (±10V a 0.200 V/mm)", color='#9CA3AF', fontsize=8.5, fontfamily='monospace')
    ax_opt.tick_params(colors='#9CA3AF', labelsize=8)
    for spine in ax_opt.spines.values():
        spine.set_color('#374151')

    leyenda_opt = [
        Line2D([0], [0], color='#34D399', linewidth=1.5, label='Trazo de Corte (ON)'),
        Line2D([0], [0], color='#F59E0B', linewidth=1.2, linestyle='--', label='Salto Óptimo TSP (OFF)'),
        Line2D([0], [0], color='#3B82F6', linewidth=1.2, label='Límite Campo (±50 mm)'),
        Line2D([0], [0], marker='^', color='#10B981', linestyle='None', markersize=5.5, label='Inicio'),
        Line2D([0], [0], marker='s', color='#EF4444', linestyle='None', markersize=4.5, label='Fin'),
        Line2D([0], [0], marker='+', color='#F59E0B', linestyle='None', markersize=8, label='Home (0,0)'),
    ]
    ax_opt.legend(handles=leyenda_opt, loc='upper right', fontsize=7.0, facecolor='#0B0F19', edgecolor='#374151', framealpha=0.75)

    # -------------------------------------------------------------------------
    # PANEL INFERIOR IZQUIERDO: TARJETA DEDICADA DE MÉTRICAS CAD
    # -------------------------------------------------------------------------
    ax_card_orig = fig.add_subplot(gs[1, 0], facecolor='#0B0F19')
    ax_card_orig.axis('off')

    card_orig_text = (
        f"┌── [DIAGNÓSTICO ESPACIO CAD ORIGINAL (DXF BRUTO)] ────────────────────────────────────────────────────────┐\n"
        f"│  • Contornos Brutos     : {num_trazos_orig:<5} trazos independientes     • Vértices Nodos     : {num_pts_orig:<7,} puntos     │\n"
        f"│  • Dimensiones CAD      : {ancho_orig:<7.2f} × {alto_orig:<7.2f} u            • Longitud de Corte  : {long_corte_orig:<7.2f} u          │\n"
        f"│  • Saltos Desordenados  : {dist_viaje_orig:<7.2f} u (tránsito caótico en vacío representado en rojo punteado)      │\n"
        f"└────────────────────────────────────────────────────────────────────────────────────────────────────────────┘"
    )
    ax_card_orig.text(
        0.0, 0.50, card_orig_text, transform=ax_card_orig.transAxes,
        color='#93C5FD', fontsize=8.2, fontfamily='monospace',
        verticalalignment='center'
    )

    # -------------------------------------------------------------------------
    # PANEL INFERIOR DERECHO: TARJETA DEDICADA DE MÉTRICAS GALVO OPTIMIZADO
    # -------------------------------------------------------------------------
    ax_card_opt = fig.add_subplot(gs[1, 1], facecolor='#0B0F19')
    ax_card_opt.axis('off')

    card_opt_text = (
        f"┌── [DIAGNÓSTICO ESPACIO GALVO OPTIMIZADO (THORLABS GVS112/M)] ─────────────────────────────────────────────┐\n"
        f"│  • Contornos Fusionados : {num_trazos_opt:<4} ({num_trazos_orig} → {num_trazos_opt})               • Waypoints (Post-RDP): {num_pts_opt:<6,} (-{reduccion_nodos_pct:>4.1f}%)    │\n"
        f"│  • Dimensiones Calibr.  : {ancho_opt:<6.2f} × {alto_opt:<6.2f} mm         • Tránsito TSP Óptimo : {dist_viaje_opt:<6.2f} mm (-{ahorro_viaje_pct:>4.1f}%)   │\n"
        f"│  ★ AHORRO SALTOS EN VACÍO: -{ahorro_viaje_pct:>5.1f}%  │  ★ TIEMPO ESTIMADO CICLO: {t_ciclo_total:>5.2f} s (Marcado: {t_marcado:.2f}s)    │\n"
        f"└────────────────────────────────────────────────────────────────────────────────────────────────────────────┘"
    )
    ax_card_opt.text(
        0.0, 0.50, card_opt_text, transform=ax_card_opt.transAxes,
        color='#34D399', fontsize=8.2, fontfamily='monospace',
        verticalalignment='center'
    )

    if guardar_imagen:
        plt.savefig(archivo_salida, dpi=180, facecolor=fig.get_facecolor(), bbox_inches='tight')
        print(f"\n[+] Imagen comparativa exportada exitosamente en:\n    {os.path.abspath(archivo_salida)}")

    if mostrar_gui:
        print("[*] Abriendo ventana gráfica interactiva (usa la barra para zoom/pan)...")
        plt.show()
    else:
        plt.close(fig)

    return archivo_salida


def main():
    parser = argparse.ArgumentParser(
        description="Visualizador Comparativo: Espacio CAD DXF Original vs. Trayectoria Galvo Optimizada"
    )
    parser.add_argument("dxf", nargs="?", default=None, help="Ruta al archivo .dxf (opcional)")
    parser.add_argument("--guardar", action="store_true", default=True, help="Guarda la comparativa en formato PNG")
    parser.add_argument("--no-gui", action="store_true", help="Desactiva la ventana interactiva (modo headless)")
    parser.add_argument("--todos", action="store_true", help="Procesa todos los archivos .dxf de la carpeta dxf/")
    parser.add_argument("--escala", type=float, default=ESCALA_DIBUJO, help="Factor de escala en el campo óptico (0.1 a 1.0)")
    parser.add_argument("--rotacion", type=float, default=0.0, help="Ángulo de rotación en grados (0 a 360)")
    parser.add_argument("--rdp", type=float, default=0.025, help="Tolerancia del filtro Ramer-Douglas-Peucker en mm")
    parser.add_argument("--salida", type=str, default=None, help="Nombre del archivo PNG de salida")

    args = parser.parse_args()

    archivos_a_procesar = []

    carpetas_busqueda = [
        os.path.join(_DIR_ACTUAL, "dxf"),
        os.path.join(_DIR_PROYECTO, "dxf"),
        "dxf",
        "."
    ]

    if args.todos:
        cands = []
        for c_dir in carpetas_busqueda:
            if os.path.exists(c_dir):
                cands.extend(glob.glob(os.path.join(c_dir, "*.dxf")))
        archivos_a_procesar = sorted(list(set(cands)))
        if not archivos_a_procesar:
            print("[ERROR] No se encontraron archivos .dxf en la carpeta dxf/")
            sys.exit(1)
        print(f"Modo masivo activado: se procesarán {len(archivos_a_procesar)} archivos DXF.")
    elif args.dxf:
        ruta = args.dxf
        if not os.path.exists(ruta):
            encontrado = False
            for c_dir in carpetas_busqueda:
                posible = os.path.join(c_dir, os.path.basename(ruta))
                if os.path.exists(posible):
                    ruta = posible
                    encontrado = True
                    break
            if not encontrado:
                print(f"[ERROR] Archivo no encontrado: {args.dxf}")
                sys.exit(1)
        archivos_a_procesar.append(ruta)
    else:
        cands = []
        for c_dir in carpetas_busqueda:
            if os.path.exists(c_dir):
                cands.extend(glob.glob(os.path.join(c_dir, "*.dxf")))
        cands = sorted(list(set(cands)))
        if not cands:
            print("[ERROR] No se encontraron archivos .dxf para visualizar.")
            sys.exit(1)
        
        pref = [c for c in cands if "batman" in c.lower()]
        if not pref:
            pref = [c for c in cands if "head" in c.lower()]
        if not pref:
            pref = cands
        
        archivos_a_procesar.append(pref[0])
        print(f"[INFO] No se especificó archivo. Seleccionado automáticamente: {os.path.basename(pref[0])}")

    for arc in archivos_a_procesar:
        generar_grafico_comparativo(
            arc,
            escala=args.escala,
            rotacion_grados=args.rotacion,
            tolerancia_rdp=args.rdp,
            guardar_imagen=args.guardar,
            mostrar_gui=not args.no_gui and not args.todos,
            archivo_salida=args.salida
        )


if __name__ == "__main__":
    main()
