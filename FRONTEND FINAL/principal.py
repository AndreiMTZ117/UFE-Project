# -*- coding: utf-8 -*-
"""
principal.py — Orquestador Principal del Sistema de Trazado Láser Vectorial

Arquitectura desacoplada (Hardware Abstraction Layer):
  1. Lee y procesa el DXF con los algoritmos matemáticos universales en core/.
  2. Escala, orienta y optimiza las trayectorias (TSP + RDP).
  3. Transmite las órdenes al hardware seleccionado (Maqueta Servos o Thorlabs GVS112/M).
  4. Registra automáticamente cada ciclo en la base de datos SQLite3 (trazabilidad).

Uso:
  python principal.py                      # procesa el primer DXF encontrado
  python principal.py Autobots.dxf         # procesa el archivo indicado
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
# Modificar antes de cada sesión de trabajo, o integrar con la GUI.
OPERADOR_ACTIVO = "Operador"   # Nombre del técnico responsable
RECETA_ID       = None          # ID de la receta a usar (None = parámetros del config estático)

# =========================================================
# SELECCIÓN DEL HARDWARE ACTIVO
# =========================================================
HARDWARE_ACTIVO = "maqueta_servos"

from core.lector_dxf import LectorDXF, obtener_limites_dxf
from core.generador_trayectorias import transformar_y_escalar_dxf
from core.visualizador import generar_previsualizacion

if HARDWARE_ACTIVO == "maqueta_servos":
    from hardware_maqueta_servos.config_maqueta import (
        X_MIN_LIMIT, X_MAX_LIMIT, Y_MIN_LIMIT, Y_MAX_LIMIT,
        ESCALA_DIBUJO, ROTAR_90_GRADOS,
        TOLERANCIA_RDP, TOLERANCIA_UNION, LONGITUD_MIN_TRAZO,
        LIMITES_MAQUETA, PUERTO_ESP32,
        MARCO_ANCHO_CM, MARCO_ALTO_CM,
        VELOCIDAD_TRAZADO, VELOCIDAD_VIAJE
    )
    from hardware_maqueta_servos.controlador_esp32 import ControladorESP32
    DriverHardware = ControladorESP32
elif HARDWARE_ACTIVO == "thorlabs_galvo":
    from hardware_thorlabs_galvo.config_galvo import (
        CAMPO_X_MIN_MM as X_MIN_LIMIT, CAMPO_X_MAX_MM as X_MAX_LIMIT,
        CAMPO_Y_MIN_MM as Y_MIN_LIMIT, CAMPO_Y_MAX_MM as Y_MAX_LIMIT,
        ESCALA_DIBUJO, ROTAR_90_GRADOS, LIMITES_GALVO as LIMITES_MAQUETA,
        VELOCIDAD_MARCADO_MM_S as VELOCIDAD_TRAZADO,
        VELOCIDAD_SALTO_MM_S as VELOCIDAD_VIAJE
    )
    from hardware_thorlabs_galvo.controlador_thorlabs import ControladorThorlabsGVS
    MARCO_ANCHO_CM = None
    MARCO_ALTO_CM = None
    TOLERANCIA_RDP = 0.005
    TOLERANCIA_UNION = 0.01
    LONGITUD_MIN_TRAZO = 0.005
    DriverHardware = ControladorThorlabsGVS


def buscar_archivo_dxf(nombre_solicitado=None):
    if nombre_solicitado:
        # Buscar directo o en carpeta dxf/
        if os.path.exists(nombre_solicitado):
            return nombre_solicitado
        en_carpeta = os.path.join('dxf', nombre_solicitado)
        if os.path.exists(en_carpeta):
            return en_carpeta
        print(f"[ERROR] No se encontró el archivo '{nombre_solicitado}' (ni en raíz ni en dxf/).")
        sys.exit(1)

    # Búsqueda automática en carpeta dxf/ o raíz
    candidatos = glob.glob('dxf/*.dxf') + [f for f in glob.glob('*.dxf') if 'prueba' not in f.lower()]
    if not candidatos:
        candidatos = glob.glob('*.dxf')
    if not candidatos:
        print("[ERROR] No se encontró ningún archivo .dxf en la carpeta dxf/ ni en el directorio actual.")
        sys.exit(1)
    return candidatos[0]


def ejecutar():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    archivo_arg = args[0] if args else None
    ruta_dxf = buscar_archivo_dxf(archivo_arg)
    nombre_archivo = os.path.basename(ruta_dxf)

    print("=" * 60)
    print(f"  SISTEMA DE TRAZADO LÁSER VECTORIAL")
    print(f"  Hardware activo: [{HARDWARE_ACTIVO.upper()}]")
    print(f"  Archivo DXF:     {nombre_archivo}")
    print("=" * 60)

    # 1. Extracción vectorial con el Core universal
    lector = LectorDXF(ruta_dxf)
    trayectorias_orig = lector.extraer_coordenadas()

    if not trayectorias_orig:
        print("[ERROR] No se pudieron extraer trayectorias del archivo DXF.")
        sys.exit(1)

    min_xo, max_xo, min_yo, max_yo = obtener_limites_dxf(trayectorias_orig)
    ancho_cad = max_xo - min_xo
    alto_cad  = max_yo - min_yo
    pts_orig  = sum(len(r) for r in trayectorias_orig)

    print(f"\nGeometría DXF original:")
    print(f"  Trazos extraídos: {len(trayectorias_orig)} | Puntos totales: {pts_orig}")
    print(f"  Dimensiones CAD:  {ancho_cad:.2f} × {alto_cad:.2f} unidades")

    # 2. Transformación, escalado uniforme y optimización TSP
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

    print(f"\nGeometría calibrada para {HARDWARE_ACTIVO}:")
    print(f"  Trazos optimizados: {len(trayectorias_cal)} | Waypoints totales: {pts_cal}")
    print(f"  Área de trabajo:    {ancho_cal:.2f} × {alto_cal:.2f} unidades")
    print(f"  Límites:            X[{min_xc:.2f}, {max_xc:.2f}]  Y[{min_yc:.2f}, {max_yc:.2f}]")

    # Generar previsualización gráfica automática
    generar_previsualizacion(ruta_dxf, trayectorias_orig, trayectorias_cal, LIMITES_MAQUETA)

    # 3. Transmisión al driver de hardware con registro de trazabilidad
    gt = GestorTrazabilidad()
    gr = GestorRecetas()

    # Preparar snapshot de parámetros para el log
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
        "trazos_totales":    len(trayectorias_cal),
        "waypoints_totales": pts_cal,
    }

    controlador = DriverHardware()
    t_inicio = time.time()
    estado_ciclo   = "COMPLETADO"
    mensaje_error  = ""

    try:
        controlador.trazar_trayectorias(trayectorias_cal)
    except KeyboardInterrupt:
        estado_ciclo  = "ABORTADO"
        mensaje_error = "Interrupción manual por el operador (KeyboardInterrupt)."
        print(f"\n[Principal] ⚠ Ciclo abortado manualmente.")
    except Exception as e:
        estado_ciclo  = "FALLO_HARDWARE"
        mensaje_error = str(e)
        print(f"\n[Principal] ❌ Fallo de hardware: {e}")
    finally:
        controlador.cerrar()
        duracion = round(time.time() - t_inicio, 2)

        datos_log_base["estado"]             = estado_ciclo
        datos_log_base["mensaje_error"]      = mensaje_error
        datos_log_base["duracion_segundos"]  = duracion

        id_log = gt.registrar_ciclo(datos_log_base)
        print(f"\n[Principal] 📋 Ciclo registrado en BD — ID={id_log} | "
              f"Estado: {estado_ciclo} | Duración: {duracion}s")


if __name__ == "__main__":
    ejecutar()
