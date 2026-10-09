# -*- coding: utf-8 -*-
"""
test_integracion_fases.py — Suite completa de pruebas de validación de las 5 Fases
"""
import sys
import os
import numpy as np

# Asegurar path
sys.path.insert(0, os.path.abspath("."))

def test_todo():
    print("=== FASE 1: VERIFICACION DE PURGA DE MAQUETA ===")
    assert not os.path.exists("hardware_maqueta_servos"), "hardware_maqueta_servos no debe existir"
    print("[PASS] hardware_maqueta_servos eliminado correctamente")

    print("\n=== FASE 2: G-CODE PARSER & MATRIZ TEMPORAL ===")
    from core.lector_gcode import LectorGcode, leer_gcode
    segs = leer_gcode("dxf/cuadrado_test.gcode")
    assert len(segs) > 0, "Debe haber segmentos extraidos"
    cortes = [s for s in segs if s["laser_on"]]
    viajes = [s for s in segs if not s["laser_on"]]
    print(f"  Segmentos extraidos: {len(segs)} (Cortes: {len(cortes)}, Viajes: {len(viajes)})")
    assert len(cortes) > 0 and len(viajes) > 0

    from core.generador_matriz_temporal import GeneradorMatrizTemporal
    gen = GeneradorMatrizTemporal(fs=100000.0, escala_vx=0.20, escala_vy=0.20)
    M, L, info = gen.generar(segs)
    print(f"  M shape: {M.shape}, L shape: {L.shape}")
    assert M.shape[0] == 2
    assert M.shape[1] == len(L)
    assert M.shape[1] == info["n_muestras"]
    assert abs(info["tiempo_total_s"] - (M.shape[1] / 100000.0)) < 1e-6
    print(f"  Tiempo analitico: {info['tiempo_total_s']:.4f} s ({info['n_muestras']:,} muestras)")
    print(f"  |Vx|_max={info['max_vx']:.3f} V | |Vy|_max={info['max_vy']:.3f} V")
    assert np.max(np.abs(M)) <= 10.0, "Clamping estricto +-10V violado"
    print("[PASS] LectorGcode y GeneradorMatrizTemporal validados")

    print("\n=== FASE 3: AISLAMIENTO MODULO HARDWARE THORLABS ===")
    from hardware_thorlabs_galvo.config_galvo import (
        MODO_HARDWARE, DISPOSITIVO_NI, CANAL_AO_X, CANAL_AO_Y, CANAL_DO_LASER,
        FRECUENCIA_MUESTREO_HZ, ESCALA_VX_POR_MM, ESCALA_VY_POR_MM,
        JUMP_DELAY_US, LASER_ON_DELAY_US, LASER_OFF_DELAY_US
    )
    print(f"  Modo Hardware: {MODO_HARDWARE}")
    print(f"  DAQ: {DISPOSITIVO_NI} ({CANAL_AO_X}, {CANAL_AO_Y}, {CANAL_DO_LASER}) @ {FRECUENCIA_MUESTREO_HZ} Hz")
    print(f"  Delays: Jump={JUMP_DELAY_US}us, Lon={LASER_ON_DELAY_US}us, Loff={LASER_OFF_DELAY_US}us")
    assert FRECUENCIA_MUESTREO_HZ == 100000
    assert ESCALA_VX_POR_MM == 0.20
    assert JUMP_DELAY_US == 250

    from hardware_thorlabs_galvo.controlador_thorlabs import ControladorThorlabsGVS
    drv = ControladorThorlabsGVS(modo="SIMULACION")
    assert drv.modo == "SIMULACION"
    drv.centrar_espejos()
    drv.trazar_matriz(M, L)
    drv.abortar_inmediato()
    drv.cerrar()
    print("[PASS] ControladorThorlabsGVS validado")

    print("\n=== FASE 4: HMI, SELECTOR DUAL & MONITOR DE TIEMPO/VOLTAJES ===")
    from interfaz.conexion_interfaz import PuenteLaser, HARDWARE_CONFIG
    puente = PuenteLaser()
    assert "thorlabs_galvo" in HARDWARE_CONFIG
    assert "maqueta_servos" not in HARDWARE_CONFIG
    print(f"  Perfil activo: {puente.obtener_nombre_hardware()}")

    archivos = puente.listar_archivos_dxf()
    print(f"  Archivos detectados (DXF/G-code): {len(archivos)}")
    assert any(f.endswith(".gcode") for f in archivos)
    assert any(f.endswith(".dxf") for f in archivos)

    # 4.1 Test G-code en PuenteLaser
    res_gc = puente.cargar_dxf("dxf/cuadrado_test.gcode", {"velocidad_trazado": 500, "velocidad_viaje": 2000})
    print(f"  [G-code] {res_gc['archivo']} -> T.Est={res_gc['tiempo_estimado_s']:.4f} s | {res_gc['n_muestras_daq']:,} pts | |V|_max={max(res_gc['max_vx'], res_gc['max_vy']):.2f} V")
    assert puente.es_gcode is True
    assert len(puente.saltos_fisicos_cm) > 0, "Debe haber saltos rápidos para previsualización"
    assert len(puente.trazos_fisicos_cm) > 0, "Debe haber trazos de corte para previsualización"

    # 4.2 Test DXF en PuenteLaser
    res_dxf = puente.cargar_dxf("dxf/batman.dxf", {"velocidad_trazado": 500, "velocidad_viaje": 2000, "escala_dibujo": 0.9})
    print(f"  [DXF] {res_dxf['archivo']} -> T.Est={res_dxf['tiempo_estimado_s']:.4f} s | {res_dxf['n_muestras_daq']:,} pts | |V|_max={max(res_dxf['max_vx'], res_dxf['max_vy']):.2f} V")
    assert puente.es_gcode is False
    assert len(puente.saltos_fisicos_cm) > 0
    assert len(puente.trazos_fisicos_cm) > 0
    print("[PASS] Selector dual y metricas analiticas validadas en PuenteLaser")

    print("\n=== FASE 5: DATABASE & REGISTRO DE HISTORIAL ===")
    from database.trazabilidad import GestorTrazabilidad
    from database.recetas import GestorRecetas
    gt = GestorTrazabilidad()
    gr = GestorRecetas()
    recetas = gr.listar_recetas()
    print(f"  Recetas disponibles: {len(recetas)}")
    assert len(recetas) > 0

    id_log = gt.registrar_ciclo({
        "operador": "Test Automático",
        "archivo_dxf": "cuadrado_test.gcode",
        "hardware_usado": "thorlabs_galvo",
        "duracion_segundos": 1.23,
        "estado": "COMPLETADO"
    })
    hist = gt.listar_historial(limite=1)
    print(f"  Ultimo ciclo registrado ID={id_log}: {hist[0]['archivo_dxf']} en {hist[0]['hardware_usado']}")
    assert hist[0]["hardware_usado"] == "thorlabs_galvo"
    print("[PASS] Base de datos y trazabilidad validadas")

    print("\n" + "=" * 60)
    print("  TODAS LAS 5 FASES DEL PLAN DE TRABAJO ESTAN 100% OPERATIVAS!")
    print("=" * 60)

if __name__ == "__main__":
    test_todo()
