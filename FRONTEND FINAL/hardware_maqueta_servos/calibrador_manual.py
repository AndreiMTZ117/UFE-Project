# -*- coding: utf-8 -*-
"""
hardware_maqueta_servos/calibrador_manual.py — Herramienta Interactiva de Calibración

Permite:
  1. Encender y apagar el láser a voluntad.
  2. Mover los servos a coordenadas directas (X, Y).
  3. Probar las 4 esquinas del marco de la maqueta (P1, P2, P3, P4) y el Centro.
  4. Trazar el rectángulo perimetral completo con láser encendido.
  5. Ajuste fino paso a paso (Jog) para medir con regla física.
"""

import sys
import time
import os

try:
    from .config_maqueta import (
        P1_SUP_IZQ, P2_INF_IZQ, P3_INF_DER, P4_SUP_DER,
        CENTRO_MAQUETA_X, CENTRO_MAQUETA_Y,
        PUERTO_ESP32, BAUDRATE
    )
    from .controlador_esp32 import ControladorESP32
except ImportError:
    from config_maqueta import (
        P1_SUP_IZQ, P2_INF_IZQ, P3_INF_DER, P4_SUP_DER,
        CENTRO_MAQUETA_X, CENTRO_MAQUETA_Y,
        PUERTO_ESP32, BAUDRATE
    )
    from controlador_esp32 import ControladorESP32


def menu_calibracion():
    print("\n" + "="*55)
    print("   CALIBRADOR MANUAL INTERACTIVO — MAQUETA SERVOS")
    print("="*55)
    print(" [1] Encender Láser (LASER_ON)")
    print(" [2] Apagar Láser (LASER_OFF)")
    print(f" [3] Ir al Centro ({CENTRO_MAQUETA_X}, {CENTRO_MAQUETA_Y})")
    print(f" [4] Probar Esquina P1 - Sup. Izq {P1_SUP_IZQ}")
    print(f" [5] Probar Esquina P2 - Inf. Izq {P2_INF_IZQ}")
    print(f" [6] Probar Esquina P3 - Inf. Der {P3_INF_DER}")
    print(f" [7] Probar Esquina P4 - Sup. Der {P4_SUP_DER}")
    print(" [8] Trazar Rectángulo Perimetral (P1->P4->P3->P2->P1) con Láser ON")
    print(" [9] Mover a Coordenada Libre X, Y (ej: 48.5, 35.0)")
    print(" [0] Salir")
    print("="*55)

def ejecutar_calibrador():
    print(f"Conectando a {PUERTO_ESP32}...")
    controlador = ControladorESP32(puerto=PUERTO_ESP32, baudrate=BAUDRATE)

    if not controlador.conexion:
        print("[ERROR] No se pudo abrir conexión con el ESP32.")
        return

    try:
        while True:
            menu_calibracion()
            opc = input("Selecciona una opción (0-9): ").strip()

            if opc == "1":
                controlador.enviar_comando("LASER_ON")
                print("-> Láser encendido.")
            elif opc == "2":
                controlador.enviar_comando("LASER_OFF")
                print("-> Láser apagado.")
            elif opc == "3":
                controlador.enviar_comando("CENTER")
                print(f"-> Movido al centro ({CENTRO_MAQUETA_X}, {CENTRO_MAQUETA_Y}).")
            elif opc == "4":
                print(f"-> Moviendo a P1 {P1_SUP_IZQ}...")
                controlador.enviar_comando(f"{P1_SUP_IZQ[0]},{P1_SUP_IZQ[1]}")
            elif opc == "5":
                print(f"-> Moviendo a P2 {P2_INF_IZQ}...")
                controlador.enviar_comando(f"{P2_INF_IZQ[0]},{P2_INF_IZQ[1]}")
            elif opc == "6":
                print(f"-> Moviendo a P3 {P3_INF_DER}...")
                controlador.enviar_comando(f"{P3_INF_DER[0]},{P3_INF_DER[1]}")
            elif opc == "7":
                print(f"-> Moviendo a P4 {P4_SUP_DER}...")
                controlador.enviar_comando(f"{P4_SUP_DER[0]},{P4_SUP_DER[1]}")
            elif opc == "8":
                print("-> Trazando perímetro del marco...")
                controlador.enviar_comando("LASER_OFF")
                controlador.enviar_comando(f"P {P1_SUP_IZQ[0]},{P1_SUP_IZQ[1]},300,0")
                controlador.enviar_comando(f"P {P4_SUP_DER[0]},{P4_SUP_DER[1]},800,1")
                controlador.enviar_comando(f"P {P3_INF_DER[0]},{P3_INF_DER[1]},800,1")
                controlador.enviar_comando(f"P {P2_INF_IZQ[0]},{P2_INF_IZQ[1]},800,1")
                controlador.enviar_comando(f"P {P1_SUP_IZQ[0]},{P1_SUP_IZQ[1]},800,1")
                controlador.enviar_comando(f"P {P1_SUP_IZQ[0]},{P1_SUP_IZQ[1]},50,0")
                controlador.enviar_comando("WAIT", timeout_segundos=10.0)
                controlador.enviar_comando("CENTER")
                print("-> Perímetro completado.")
            elif opc == "9":
                coord = input("Ingresa coordenada X,Y (ej: 49.0, 36.5): ").strip()
                controlador.enviar_comando(coord)
            elif opc == "0" or opc.lower() == "q":
                controlador.enviar_comando("LASER_OFF")
                controlador.enviar_comando("CENTER")
                break
            else:
                print("Opción no válida.")

            time.sleep(0.2)

    except KeyboardInterrupt:
        print("\nInterrupción detectada. Apagando láser...")
        controlador.enviar_comando("LASER_OFF")
        controlador.enviar_comando("CENTER")
    finally:
        controlador.cerrar()

if __name__ == "__main__":
    ejecutar_calibrador()
