# -*- coding: utf-8 -*-
"""
principal.py — Orquestador Principal del Sistema de Trazado Laser Vectorial

Arquitectura orientada exclusivamente al cabezal Thorlabs GVS112/M:
  1. Lee y procesa archivos DXF (.dxf) o G-code (.gcode, .nc, .ngc).
  2. Escala, orienta y optimiza las trayectorias (TSP + RDP) o interpreta G-code.
  3. Transmite las señales al driver Thorlabs (SIMULACIÓN o PXI-6229 REAL).
  4. Registra automáticamente cada ciclo en la base de datos SQLite3.

Uso:
  python principal.py                      # procesa el primer DXF/G-code encontrado
  python principal.py Autobots.dxf         # procesa el archivo DXF indicado
  python principal.py pieza.gcode          # procesa el archivo G-code indicado
  python principal.py batman.dxf --preview # genera previsualización y traza
"""

import os
import sys
import glob
import time

# =========================================================
# MÓDULO DE BASE DE DATOS (Recetas y Trazabilidad)
# =========================================================
from database.trazabilidad import GestorTrazabilidad
from database.recetas import GestorRecetas

# =========================================================
# IDENTIFICACIÓN DEL OPERADOR Y RECETA ACTIVA
# =========================================================
OPERADOR_ACTIVO = "Operador"   # Nombre del técnico responsable
RECETA_ID       = None          # ID de la receta a usar (None = parámetros del config estático)


from core.lector_dxf import LectorDXF, obtener_limites_dxf
from core.lector_gcode import LectorGcode
from core.generador_matriz_temporal import GeneradorMatrizTemporal
from core.generador_trayectorias import transformar_y_escalar_dxf
from core.visualizador import generar_previsualizacion

# Único motor de hardware: Thorlabs GVS112/M
from hardware_thorlabs_galvo.config_galvo import (
    CAMPO_X_MIN_MM as X_MIN_LIMIT, CAMPO_X_MAX_MM as X_MAX_LIMIT,
    CAMPO_Y_MIN_MM as Y_MIN_LIMIT, CAMPO_Y_MAX_MM as Y_MAX_LIMIT,
    ESCALA_DIBUJO, ROTAR_90_GRADOS, LIMITES_GALVO,
    VELOCIDAD_MARCADO_MM_S as VELOCIDAD_TRAZADO,
    VELOCIDAD_SALTO_MM_S as VELOCIDAD_VIAJE,
    FRECUENCIA_MUESTREO_HZ, ESCALA_VX_POR_MM, ESCALA_VY_POR_MM,
    OFFSET_VX, OFFSET_VY, JUMP_DELAY_US, LASER_ON_DELAY_US, LASER_OFF_DELAY_US
)
from hardware_thorlabs_galvo.controlador_thorlabs import ControladorThorlabsGVS

HARDWARE_ACTIVO    = "thorlabs_galvo"
MARCO_ANCHO_CM     = None
MARCO_ALTO_CM      = None
TOLERANCIA_RDP     = 0.005
TOLERANCIA_UNION   = 0.01
LONGITUD_MIN_TRAZO = 0.005
DriverHardware     = ControladorThorlabsGVS


def buscar_archivo(nombre_solicitado=None):
    extensiones = ('.dxf', '.gcode', '.nc', '.ngc')
    if nombre_solicitado:
        # Buscar directo o en carpeta dxf/
        if os.path.exists(nombre_solicitado):
            return nombre_solicitado
        en_carpeta = os.path.join('dxf', nombre_solicitado)
        if os.path.exists(en_carpeta):
            return en_carpeta
        print(f"[ERROR] No se encontro el archivo '{nombre_solicitado}' (ni en raiz ni en dxf/).")
        sys.exit(1)

    # Búsqueda automática en carpeta dxf/ o raiz
    candidatos = []
    for ext in extensiones:
        candidatos.extend(glob.glob(f'dxf/*{ext}'))
        candidatos.extend([f for f in glob.glob(f'*{ext}') if 'prueba' not in f.lower()])

    if not candidatos:
        for ext in extensiones:
            candidatos.extend(glob.glob(f'*{ext}'))

    if not candidatos:
        print("[ERROR] No se encontro ningun archivo DXF o G-code (.dxf, .gcode, .nc, .ngc) en dxf/ ni en raiz.")
        sys.exit(1)
    return candidatos[0]


def ejecutar():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    archivo_arg = args[0] if args else None
    ruta_archivo = buscar_archivo(archivo_arg)
    nombre_archivo = os.path.basename(ruta_archivo)
    es_gcode = ruta_archivo.lower().endswith(('.gcode', '.nc', '.ngc'))

    print("=" * 60)
    print(f"  SISTEMA DE TRAZADO LASER VECTORIAL (THORLABS GVS112/M)")
    print(f"  Hardware activo: [{HARDWARE_ACTIVO.upper()}]")
    print(f"  Archivo cargado: {nombre_archivo} ({'G-CODE' if es_gcode else 'DXF'})")
    print("=" * 60)

    gt = GestorTrazabilidad()
    gr = GestorRecetas()
    receta_nombre_log = "Manual (config estático)"
    if RECETA_ID is not None:
        receta_info = gr.obtener_receta(RECETA_ID)
        receta_nombre_log = receta_info.get("nombre", "Manual") if receta_info else "Manual"

    datos_log_base = {
        "operador":          OPERADOR_ACTIVO,
        "archivo_dxf":       nombre_archivo,
        "hardware_usado":    HARDWARE_ACTIVO,
        "receta_id":         RECETA_ID,
        "receta_nombre":     receta_nombre_log,
        "velocidad_trazado": VELOCIDAD_TRAZADO,
        "velocidad_viaje":   VELOCIDAD_VIAJE,
        "escala_dibujo":     ESCALA_DIBUJO,
        "tolerancia_rdp":    TOLERANCIA_RDP,
        "tolerancia_union":  TOLERANCIA_UNION,
    }

    controlador = DriverHardware()
    t_inicio = time.time()
    estado_ciclo  = "COMPLETADO"
    mensaje_error = ""

    try:
        if es_gcode:
            # Flujo G-code directo
            lector_gc = LectorGcode(ruta_archivo, feed_defecto_mm_min=VELOCIDAD_TRAZADO * 60.0, feed_viaje_mm_min=VELOCIDAD_VIAJE * 60.0)
            segmentos = lector_gc.leer()
            if not segmentos:
                raise ValueError("No se encontraron comandos de movimiento en el archivo G-code.")

            gen = GeneradorMatrizTemporal(
                fs=FRECUENCIA_MUESTREO_HZ,
                escala_vx=ESCALA_VX_POR_MM,
                escala_vy=ESCALA_VY_POR_MM,
                offset_vx=OFFSET_VX,
                offset_vy=OFFSET_VY,
                jump_delay_us=JUMP_DELAY_US,
                laser_on_delay_us=LASER_ON_DELAY_US,
                laser_off_delay_us=LASER_OFF_DELAY_US,
                velocidad_defecto_mm_s=VELOCIDAD_TRAZADO,
                velocidad_viaje_mm_s=VELOCIDAD_VIAJE,
            )
            M, L, info = gen.generar(segmentos)
            datos_log_base["trazos_totales"]    = info["n_segmentos_corte"]
            datos_log_base["waypoints_totales"] = info["n_muestras"]

            print(f"\n[G-code] Tiempo analitico exacto: {info['tiempo_total_s']:.4f} s ({info['n_muestras']:,} muestras)")
            print(f"[G-code] Segmentos de corte: {info['n_segmentos_corte']} | Segmentos de viaje: {info['n_segmentos_viaje']}")
            print(f"[G-code] Voltaje max: |Vx|={info['max_vx']:.3f}V, |Vy|={info['max_vy']:.3f}V")

            controlador.trazar_matriz(M, L, fs=FRECUENCIA_MUESTREO_HZ)

        else:
            # Flujo DXF universal
            lector = LectorDXF(ruta_archivo)
            trayectorias_orig = lector.extraer_coordenadas()
            if not trayectorias_orig:
                raise ValueError("No se pudieron extraer trayectorias del archivo DXF.")

            min_xo, max_xo, min_yo, max_yo = obtener_limites_dxf(trayectorias_orig)
            ancho_cad = max_xo - min_xo
            alto_cad  = max_yo - min_yo
            pts_orig  = sum(len(r) for r in trayectorias_orig)

            print(f"\nGeometria DXF original:")
            print(f"  Trazos extraidos: {len(trayectorias_orig)} | Puntos totales: {pts_orig}")
            print(f"  Dimensiones CAD:  {ancho_cad:.2f} x {alto_cad:.2f} unidades")

            trayectorias_cal = transformar_y_escalar_dxf(
                trayectorias_orig,
                x_min_limit=X_MIN_LIMIT,
                x_max_limit=X_MAX_LIMIT,
                y_min_limit=Y_MIN_LIMIT,
                y_max_limit=Y_MAX_LIMIT,
                escala=ESCALA_DIBUJO,
                rotar_90_grados=ROTAR_90_GRADOS,
                marco_ancho_cm=MARCO_ANCHO_CM,
                marco_alto_cm=MARCO_ALTO_CM,
                tolerancia_rdp=TOLERANCIA_RDP,
                tolerancia_union=TOLERANCIA_UNION,
                longitud_min_trazo=LONGITUD_MIN_TRAZO,
                optimizar_recorrido=True
            )

            min_xc, max_xc, min_yc, max_yc = obtener_limites_dxf(trayectorias_cal)
            ancho_cal = max_xc - min_xc
            alto_cal  = max_yc - min_yc
            pts_cal   = sum(len(r) for r in trayectorias_cal)

            print(f"\nGeometria calibrada para Thorlabs:")
            print(f"  Trazos optimizados: {len(trayectorias_cal)} | Waypoints totales: {pts_cal}")
            print(f"  Area de trabajo:    {ancho_cal:.2f} x {alto_cal:.2f} mm")
            print(f"  Limites:            X[{min_xc:.2f}, {max_xc:.2f}]  Y[{min_yc:.2f}, {max_yc:.2f}]")

            generar_previsualizacion(ruta_archivo, trayectorias_orig, trayectorias_cal, LIMITES_GALVO)

            datos_log_base["trazos_totales"]    = len(trayectorias_cal)
            datos_log_base["waypoints_totales"] = pts_cal

            controlador.trazar_trayectorias(trayectorias_cal)

    except KeyboardInterrupt:
        estado_ciclo  = "ABORTADO"
        mensaje_error = "Interrupción manual por el operador (KeyboardInterrupt)."
        print("\n[Principal] [!] Ciclo abortado manualmente.")
    except Exception as e:
        estado_ciclo  = "FALLO_HARDWARE"
        mensaje_error = str(e)
        print(f"\n[Principal] [ERROR] Fallo durante ejecucion: {e}")
    finally:
        controlador.cerrar()
        duracion = round(time.time() - t_inicio, 2)

        datos_log_base["estado"]            = estado_ciclo
        datos_log_base["mensaje_error"]     = mensaje_error
        datos_log_base["duracion_segundos"] = duracion

        id_log = gt.registrar_ciclo(datos_log_base)
        print(f"\n[Principal] [BD] Ciclo registrado en BD - ID={id_log} | "
              f"Estado: {estado_ciclo} | Duracion: {duracion}s")


if __name__ == "__main__":
    ejecutar()
