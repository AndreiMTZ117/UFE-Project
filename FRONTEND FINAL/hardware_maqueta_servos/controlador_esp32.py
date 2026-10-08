# -*- coding: utf-8 -*-
"""
hardware_maqueta_servos/controlador_esp32.py — Driver Serial para ESP32 y Servos

Maneja la transmisión continua de waypoints hacia el firmware lectorESP32.ino
mediante el protocolo "P x,y,duracion_ms,laser" con control de flujo y timeouts.
"""

import serial
import time
import math
from typing import Optional, Callable
from .config_maqueta import (
    CENTRO_MAQUETA_X, CENTRO_MAQUETA_Y,
    VELOCIDAD_TRAZADO, VELOCIDAD_VIAJE,
    DURACION_MIN_SEGMENTO_MS, DURACION_MIN_VIAJE_MS,
    PUERTO_ESP32, BAUDRATE
)

class ControladorESP32:
    def __init__(self, puerto=PUERTO_ESP32, baudrate=BAUDRATE):
        self.puerto = puerto
        self.baudrate = baudrate
        self.conexion = None

        try:
            self.conexion = serial.Serial(puerto, baudrate, timeout=10)
            time.sleep(2)  # Espera reinicio del ESP32
            self.conexion.reset_input_buffer()
            print(f"Conectado al ESP32 en {puerto} a {baudrate} baudios.")
        except serial.SerialException as e:
            print(f"[ERROR] No se pudo abrir el puerto {puerto}: {e}")
            self.conexion = None

    def enviar_comando(self, comando, timeout_segundos=15.0, check_cancel: Optional[Callable[[], bool]] = None):
        """Envía un comando de texto y espera respuesta del ESP32 con cancelación inmediata."""
        if not self.conexion or not self.conexion.is_open:
            return "OK"

        linea = (comando.strip() + "\n").encode('utf-8')
        self.conexion.write(linea)
        self.conexion.flush()

        t_inicio = time.time()
        while time.time() - t_inicio < timeout_segundos:
            if check_cancel and check_cancel():
                try:
                    self.conexion.write(b"CLEAR\nLASER_OFF\n")
                    self.conexion.flush()
                except Exception:
                    pass
                return "ABORTADO"

            if self.conexion.in_waiting > 0:
                resp = self.conexion.readline().decode('utf-8', errors='ignore').strip()
                if resp == "OK":
                    return "OK"
                elif resp.startswith("ERR"):
                    print(f"  [ALERTA ESP32] '{comando}' -> {resp}")
                    return resp
                elif resp:
                    print(f"  [ESP32] {resp}")
            time.sleep(0.001)

        print(f"  [TIMEOUT] El ESP32 no respondió a: {comando}")
        return "TIMEOUT"

    def abortar_inmediato(self):
        """Parada de emergencia inmediata por hardware: vacía la cola y apaga el láser en <1ms."""
        if self.conexion and self.conexion.is_open:
            try:
                self.conexion.write(b"CLEAR\nLASER_OFF\n")
                self.conexion.flush()
                print("  [HARDWARE] Parada de emergencia ejecutada (CLEAR + LASER_OFF).")
            except Exception as e:
                print(f"  [HARDWARE] Error al abortar inmediato: {e}")

    def apagar_laser(self):
        """Apaga el láser inmediatamente de forma segura."""
        return self.enviar_comando("LASER_OFF", timeout_segundos=1.0)

    def encender_laser(self):
        """Enciende el láser."""
        return self.enviar_comando("LASER_ON", timeout_segundos=1.0)

    def trazar_trayectorias(self, trayectorias,
                            velocidad_trazado=VELOCIDAD_TRAZADO,
                            velocidad_viaje=VELOCIDAD_VIAJE):
        """Transmite la secuencia completa de trazos vectoriales al ESP32."""
        if not self.conexion:
            print("[Simulación] Transmisión simulada (sin ESP32 conectado).")
            return

        total_trazos = len(trayectorias)
        print(f"\n--- TRANSMISIÓN CONTINUA ({total_trazos} trazo/s) ---")

        pos_actual_x = CENTRO_MAQUETA_X
        pos_actual_y = CENTRO_MAQUETA_Y

        for idx, ruta in enumerate(trayectorias):
            if not ruta:
                continue

            primer_pt = ruta[0]

            #Traslado con laser apagado
            dx = primer_pt[0] - pos_actual_x
            dy = primer_pt[1] - pos_actual_y
            dist_viaje = math.hypot(dx, dy)
            dur_viaje = int(max(DURACION_MIN_VIAJE_MS, (dist_viaje / velocidad_viaje) * 1000))

            print(f"Traslado al inicio del Trazo {idx + 1} ({primer_pt[0]}, {primer_pt[1]})...")
            self.enviar_comando(f"P {primer_pt[0]:.2f},{primer_pt[1]:.2f},{dur_viaje},0")
            pos_actual_x, pos_actual_y = primer_pt

            #Trazado con laser encendido
            print(f"Transmitiendo Trazo {idx + 1}/{total_trazos} ({len(ruta)} waypoints)...")
            for i in range(1, len(ruta)):
                pt = ruta[i]
                dx = pt[0] - pos_actual_x
                dy = pt[1] - pos_actual_y
                dist_seg = math.hypot(dx, dy)
                dur_seg = int(max(DURACION_MIN_SEGMENTO_MS, (dist_seg / velocidad_trazado) * 1000))

                self.enviar_comando(f"P {pt[0]:.2f},{pt[1]:.2f},{dur_seg},1")
                pos_actual_x, pos_actual_y = pt

            # 3. Apagar láser al completar el trazo
            self.enviar_comando(f"P {pos_actual_x:.2f},{pos_actual_y:.2f},50,0")

        # 4. Esperar finalización física
        print("Esperando finalización física del trazado...")
        self.enviar_comando("WAIT", timeout_segundos=90.0)
        print("¡Trazado completado exitosamente!")

        # 5. Regresar al centro de reposo
        print(f"Regresando al centro de reposo ({CENTRO_MAQUETA_X}, {CENTRO_MAQUETA_Y})...")
        self.enviar_comando(f"P {CENTRO_MAQUETA_X:.2f},{CENTRO_MAQUETA_Y:.2f},400,0")
        self.enviar_comando("WAIT", timeout_segundos=10.0)

    def cerrar(self):
        if self.conexion and self.conexion.is_open:
            time.sleep(0.1)
            self.conexion.close()
            print("Conexión serial cerrada limpiamente.")
