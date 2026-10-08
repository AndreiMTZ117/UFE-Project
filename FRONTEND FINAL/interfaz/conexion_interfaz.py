# -*- coding: utf-8 -*-
"""
interfaz/conexion_interfaz.py — Puente de Conexión Backend <-> Interfaz Gráfica

Gestiona:
  1. Base de datos SQLite3 (GestorRecetas y GestorTrazabilidad)
  2. Procesamiento de archivos DXF (LectorDXF y transformar_y_escalar_dxf)
  3. Detección y priorización inteligente de puertos COM USB reales frente a Bluetooth
  4. Hilo asíncrono de ejecución de corte/trazado sincronizado en tiempo real con
     la cinemática física y control estricto del estado del láser, garantizando parada
     instantánea no bloqueante.
"""

import os
import sys
import glob
import time
import math
import threading
from typing import Callable, Optional, Dict, List, Tuple, Any

# Asegurar importación de módulos del proyecto
_DIR_RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _DIR_RAIZ not in sys.path:
    sys.path.insert(0, _DIR_RAIZ)

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

from core.lector_dxf import LectorDXF, obtener_limites_dxf
from core.generador_trayectorias import transformar_y_escalar_dxf
from database.recetas import GestorRecetas
from database.trazabilidad import GestorTrazabilidad
def cargar_perfil_hardware(clave: str) -> Dict[str, Any]:
    """Carga y retorna de forma dinámica el perfil cinemático y geométrico del hardware especificado."""
    if "galvo" in clave.lower() or "thorlabs" in clave.lower():
        try:
            from hardware_thorlabs_galvo.config_galvo import (
                CAMPO_X_MIN_MM, CAMPO_X_MAX_MM,
                CAMPO_Y_MIN_MM, CAMPO_Y_MAX_MM,
                ESCALA_DIBUJO, ROTAR_90_GRADOS,
                VELOCIDAD_MARCADO_MM_S, VELOCIDAD_SALTO_MM_S
            )
            campo_w_cm = round((CAMPO_X_MAX_MM - CAMPO_X_MIN_MM) / 10.0, 2)
            campo_h_cm = round((CAMPO_Y_MAX_MM - CAMPO_Y_MIN_MM) / 10.0, 2)
            return {
                "clave": "thorlabs_galvo",
                "nombre": "Thorlabs Galvo Scanner (GVS112/M)",
                "x_min": CAMPO_X_MIN_MM,
                "x_max": CAMPO_X_MAX_MM,
                "y_min": CAMPO_Y_MIN_MM,
                "y_max": CAMPO_Y_MAX_MM,
                "centro_x": 0.0,
                "centro_y": 0.0,
                "ancho_base_cm": campo_w_cm,
                "alto_base_cm": campo_h_cm,
                "marco_ancho_cm": campo_w_cm,
                "marco_alto_cm": campo_h_cm,
                "escala_dibujo": ESCALA_DIBUJO,
                "rotar_90_grados": ROTAR_90_GRADOS,
                "velocidad_trazado": VELOCIDAD_MARCADO_MM_S,
                "velocidad_viaje": VELOCIDAD_SALTO_MM_S,
                "baudrate": 115200,
            }
        except Exception as e:
            print(f"[HAL] Error cargando config_galvo: {e}")
            return {
                "clave": "thorlabs_galvo",
                "nombre": "Thorlabs Galvo Scanner (GVS112/M)",
                "x_min": -50.0, "x_max": 50.0, "y_min": -50.0, "y_max": 50.0,
                "centro_x": 0.0, "centro_y": 0.0,
                "ancho_base_cm": 10.0, "alto_base_cm": 10.0,
                "marco_ancho_cm": 10.0, "marco_alto_cm": 10.0,
                "baudrate": 115200,
            }
    else:  # maqueta_servos por defecto
        try:
            from hardware_maqueta_servos.config_maqueta import (
                X_MIN_LIMIT, X_MAX_LIMIT, Y_MIN_LIMIT, Y_MAX_LIMIT,
                CENTRO_MAQUETA_X, CENTRO_MAQUETA_Y,
                MARCO_ANCHO_CM, MARCO_ALTO_CM,
                PUERTO_ESP32, BAUDRATE
            )
            return {
                "clave": "maqueta_servos",
                "nombre": "Maqueta Servos (ESP32)",
                "x_min": X_MIN_LIMIT,
                "x_max": X_MAX_LIMIT,
                "y_min": Y_MIN_LIMIT,
                "y_max": Y_MAX_LIMIT,
                "centro_x": CENTRO_MAQUETA_X,
                "centro_y": CENTRO_MAQUETA_Y,
                "ancho_base_cm": MARCO_ANCHO_CM,
                "alto_base_cm": MARCO_ALTO_CM,
                "marco_ancho_cm": MARCO_ANCHO_CM,
                "marco_alto_cm": MARCO_ALTO_CM,
                "baudrate": BAUDRATE,
                "puerto_default": PUERTO_ESP32,
            }
        except Exception as e:
            print(f"[HAL] Error cargando config_maqueta: {e}")
            return {
                "clave": "maqueta_servos",
                "nombre": "Maqueta Servos (ESP32)",
                "x_min": 40.0, "x_max": 140.0, "y_min": 40.0, "y_max": 140.0,
                "centro_x": 90.0, "centro_y": 90.0,
                "ancho_base_cm": 28.0, "alto_base_cm": 25.0,
                "marco_ancho_cm": 28.0, "marco_alto_cm": 25.0,
                "baudrate": 115200,
            }


# Perfiles cinemáticos y de límites de hardware soportados (cargados dinámicamente)
HARDWARE_CONFIG = {
    "maqueta_servos": cargar_perfil_hardware("maqueta_servos"),
    "thorlabs_galvo": cargar_perfil_hardware("thorlabs_galvo")
}


class PuenteLaser:
    """Puente integral entre la interfaz de usuario y el motor backend."""

    def __init__(self):
        self.gestor_recetas = GestorRecetas()
        self.gestor_trazabilidad = GestorTrazabilidad()
        
        self.controlador_hardware: Optional[Any] = None
        self.puerto_conectado: Optional[str] = None
        self.es_simulacion = True
        self._serial_lock = threading.Lock()

        # HAL actual y límites cinemáticos iniciales según perfil por defecto
        self.hal_actual = "maqueta_servos"
        cfg_init = HARDWARE_CONFIG.get(self.hal_actual, {})
        self.x_min_limit = cfg_init.get("x_min", 40.0)
        self.x_max_limit = cfg_init.get("x_max", 140.0)
        self.y_min_limit = cfg_init.get("y_min", 40.0)
        self.y_max_limit = cfg_init.get("y_max", 140.0)

        # Configuración dinámica de la máquina (personalizable desde la UI)
        self.centro_x = cfg_init.get("centro_x", 90.0)
        self.centro_y = cfg_init.get("centro_y", 90.0)
        self.ancho_base_cm = cfg_init.get("ancho_base_cm", 28.0)
        self.alto_base_cm = cfg_init.get("alto_base_cm", 25.0)
        self.centro_cm_x = round(self.ancho_base_cm / 2.0, 2)
        self.centro_cm_y = round(self.alto_base_cm / 2.0, 2)
        
        # Archivo DXF y geometrías cargadas
        self.ruta_dxf_actual: Optional[str] = None
        self.nombre_dxf_actual: Optional[str] = None
        self.trazos_originales: List[List[Tuple[float, float]]] = []
        self.trazos_calibrados: List[List[Tuple[float, float]]] = []
        self.trazos_fisicos_cm: List[List[Tuple[float, float]]] = []
        
        # Estado de ejecución del hilo
        self._hilo_ejecucion: Optional[threading.Thread] = None
        self._evento_pausa = threading.Event()
        self._evento_pausa.set()
        self._evento_detener = threading.Event()
        self._en_ejecucion = False
        self._esta_pausado = False

    def set_dimensiones_base(self, ancho_cm: float, alto_cm: float):
        """Define las dimensiones físicas de la base y recalcula el centro automáticamente."""
        self.ancho_base_cm = float(ancho_cm)
        self.alto_base_cm = float(alto_cm)
        self.centro_cm_x = round(self.ancho_base_cm / 2.0, 2)
        self.centro_cm_y = round(self.alto_base_cm / 2.0, 2)

        # El centro automático en cm corresponde al centro geométrico del hardware activo
        cfg = HARDWARE_CONFIG.get(self.hal_actual, HARDWARE_CONFIG["maqueta_servos"])
        self.centro_x = cfg["centro_x"]
        self.centro_y = cfg["centro_y"]
        print(f"[PuenteLaser] Nuevas dimensiones de base: {self.ancho_base_cm:.1f} x {self.alto_base_cm:.1f} cm | Centro automático: ({self.centro_cm_x:.2f}, {self.centro_cm_y:.2f}) cm")

    def set_centro_cm(self, x_cm: float, y_cm: float):
        """Define el centro de la base en centímetros (alteración manual del usuario)."""
        self.centro_cm_x = float(x_cm)
        self.centro_cm_y = float(y_cm)

        cfg = HARDWARE_CONFIG.get(self.hal_actual, HARDWARE_CONFIG["maqueta_servos"])
        cal_ancho = cfg.get("marco_ancho_cm", 28.0)
        cal_alto = cfg.get("marco_alto_cm", 25.0)
        rango_x = self.x_max_limit - self.x_min_limit
        rango_y = self.y_max_limit - self.y_min_limit
        kx = cal_alto / rango_x if rango_x > 0 else 1.0
        ky = cal_ancho / rango_y if rango_y > 0 else 1.0

        # Desplazamiento respecto al centro geométrico de la base
        dx_cm = self.centro_cm_x - (self.ancho_base_cm / 2.0)
        dy_cm = self.centro_cm_y - (self.alto_base_cm / 2.0)

        hw_cx = cfg["centro_x"]
        hw_cy = cfg["centro_y"]

        self.centro_x = round(hw_cx + (dx_cm / kx), 3)
        self.centro_y = round(hw_cy + (dy_cm / ky), 3)

        # Clamping de seguridad a límites de hardware
        self.centro_x = max(self.x_min_limit, min(self.x_max_limit, self.centro_x))
        self.centro_y = max(self.y_min_limit, min(self.y_max_limit, self.centro_y))

        print(f"[PuenteLaser] Centro manual definido: ({self.centro_cm_x:.2f}, {self.centro_cm_y:.2f}) cm -> Hardware: ({self.centro_x:.2f}, {self.centro_y:.2f})")

    def cambiar_hardware(self, hal_nombre: str):
        """Cambia el perfil de hardware cinemático activo (Servos ESP32 / Thorlabs Galvo)."""
        hal_lower = hal_nombre.lower()
        if "galvo" in hal_lower or "thorlabs" in hal_lower:
            clave = "thorlabs_galvo"
        else:
            clave = "maqueta_servos"

        with self._serial_lock:
            if self.controlador_hardware:
                try:
                    self.controlador_hardware.cerrar()
                except Exception:
                    pass
                self.controlador_hardware = None
                self.puerto_conectado = None
                self.es_simulacion = True

        cfg = HARDWARE_CONFIG.get(clave, HARDWARE_CONFIG["maqueta_servos"])
        self.hal_actual = clave
        self.x_min_limit = cfg["x_min"]
        self.x_max_limit = cfg["x_max"]
        self.y_min_limit = cfg["y_min"]
        self.y_max_limit = cfg["y_max"]
        self.centro_x = cfg["centro_x"]
        self.centro_y = cfg["centro_y"]
        self.ancho_base_cm = cfg["ancho_base_cm"]
        self.alto_base_cm = cfg["alto_base_cm"]
        self.centro_cm_x = round(self.ancho_base_cm / 2.0, 2)
        self.centro_cm_y = round(self.alto_base_cm / 2.0, 2)
        print(f"[PuenteLaser] Hardware cambiado a '{cfg['nombre']}'. Base: {self.ancho_base_cm}x{self.alto_base_cm} cm, Centro: ({self.centro_x}, {self.centro_y})")

    # =========================================================================
    # GESTIÓN DE BASE DE DATOS (RECETAS)
    # =========================================================================
    def obtener_recetas(self) -> List[Dict]:
        """Retorna todas las recetas ordenadas."""
        try:
            return self.gestor_recetas.listar_recetas()
        except Exception as e:
            print(f"[Conexion] Error al listar recetas: {e}")
            return []

    def obtener_receta_por_id(self, receta_id: int) -> Dict:
        """Obtiene la receta por su ID."""
        try:
            return self.gestor_recetas.obtener_receta(receta_id)
        except Exception as e:
            print(f"[Conexion] Error al obtener receta {receta_id}: {e}")
            return {}

    def obtener_receta_default(self) -> Dict:
        """Retorna la receta estándar por defecto."""
        recetas = self.obtener_recetas()
        for r in recetas:
            if "acrílico" in r.get("nombre", "").lower() or "estándar" in r.get("nombre", "").lower():
                return r
        return recetas[0] if recetas else {}

    def guardar_o_actualizar_receta(self, datos: Dict, receta_id: Optional[int] = None) -> int:
        """Crea o actualiza una receta en SQLite3."""
        if receta_id is not None:
            self.gestor_recetas.actualizar_receta(receta_id, datos)
            return receta_id
        else:
            return self.gestor_recetas.crear_receta(datos)

    def eliminar_receta(self, receta_id: int) -> bool:
        """Elimina una receta de la base de datos."""
        try:
            return self.gestor_recetas.eliminar_receta(receta_id)
        except Exception as e:
            print(f"[Conexion] Error al eliminar receta {receta_id}: {e}")
            return False

    # =========================================================================
    # DETECCIÓN INTELIGENTE Y COMUNICACIÓN SERIAL (ESP32)
    # =========================================================================
    def listar_puertos_com(self) -> List[str]:
        """
        Detecta y prioriza los puertos COM USB físicos reales (CP210x, CH340, FTDI)
        colocándolos al inicio de la lista y filtrando puertos virtuales Bluetooth.
        """
        if serial is None:
            return []
        try:
            todos_puertos = list(serial.tools.list_ports.comports())
            puertos_usb = []
            puertos_otros = []

            for p in todos_puertos:
                desc_lower = (p.description or "").lower()
                hwid_lower = (p.hwid or "").lower()

                # Reconocimiento de chips UART USB típicos (Silicon Labs CP210x, CH340, etc.)
                es_usb = any(k in desc_lower or k in hwid_lower for k in [
                    "cp210", "ch340", "ftdi", "usb", "silicon labs", "arduino", "esp32", "vid:pid"
                ])
                es_bluetooth = "bluetooth" in desc_lower or "bthenum" in hwid_lower

                if es_usb and not es_bluetooth:
                    puertos_usb.append(p.device)
                else:
                    puertos_otros.append(p.device)

            # Puertos USB reales siempre al principio
            resultado = puertos_usb + [p for p in puertos_otros if p not in puertos_usb]
            return resultado
        except Exception as e:
            print(f"[Conexion] Error al listar puertos COM: {e}")
            return []

    def conectar_puerto(self, puerto: str) -> bool:
        """
        Conecta y valida la comunicación física con el controlador del hardware activo.
        Retorna True si la conexión física y la inicialización fueron exitosas.
        """
        cfg = HARDWARE_CONFIG.get(self.hal_actual, HARDWARE_CONFIG["maqueta_servos"])

        with self._serial_lock:
            try:
                if self.controlador_hardware:
                    try:
                        self.controlador_hardware.cerrar()
                    except Exception:
                        pass
                    self.controlador_hardware = None

                if self.hal_actual == "thorlabs_galvo":
                    from hardware_thorlabs_galvo.controlador_thorlabs import ControladorThorlabsGVS
                    self.controlador_hardware = ControladorThorlabsGVS()
                    self.puerto_conectado = "Thorlabs GVS (Simulación/DAQ)"
                    self.es_simulacion = (getattr(self.controlador_hardware, 'tipo_interfaz', '') == 'SIMULACION')
                    return True
                else:
                    if not puerto or puerto.startswith("Escanear"):
                        self.es_simulacion = True
                        return False

                    puerto_limpio = puerto.split(" ")[0].strip()
                    baudrate = cfg.get("baudrate", 115200)
                    from hardware_maqueta_servos.controlador_esp32 import ControladorESP32
                    self.controlador_hardware = ControladorESP32(puerto=puerto_limpio, baudrate=baudrate)
                    if self.controlador_hardware and getattr(self.controlador_hardware, 'conexion', None) and self.controlador_hardware.conexion.is_open:
                        self.puerto_conectado = puerto_limpio
                        self.es_simulacion = False
                        return True
                    else:
                        self.puerto_conectado = puerto_limpio
                        self.es_simulacion = True
                        return False
            except Exception as e:
                print(f"[Conexion] Excepción conectando hardware ({self.hal_actual}): {e}")
                self.puerto_conectado = puerto
                self.es_simulacion = True
                return False

    def esta_conectado_fisico(self) -> bool:
        """Informa si existe un hardware real listo para recibir comandos."""
        if not self.controlador_hardware:
            return False
        if self.hal_actual == "thorlabs_galvo":
            # True si está instanciado y no es exclusivamente simulación sin DAC
            return getattr(self.controlador_hardware, 'tipo_interfaz', '') not in ('SIMULACION', '')
        return bool(
            getattr(self.controlador_hardware, 'conexion', None) and 
            self.controlador_hardware.conexion.is_open
        )

    def obtener_nombre_hardware(self) -> str:
        """Retorna el nombre legible del hardware actualmente configurado."""
        cfg = HARDWARE_CONFIG.get(self.hal_actual, {})
        return cfg.get("nombre", self.hal_actual)

    def apagar_laser(self):
        """Apaga el láser de forma segura en el hardware activo."""
        if self.controlador_hardware:
            try:
                if hasattr(self.controlador_hardware, "apagar_laser"):
                    self.controlador_hardware.apagar_laser()
                elif hasattr(self.controlador_hardware, "enviar_comando"):
                    self.controlador_hardware.enviar_comando("LASER_OFF", timeout_segundos=1.0)
            except Exception as e:
                print(f"[PuenteLaser] Error apagando láser: {e}")

    # =========================================================================
    # PROCESAMIENTO Y CARGA DE ARCHIVOS DXF
    # =========================================================================
    def listar_archivos_dxf(self) -> List[str]:
        """Busca archivos .dxf en la carpeta dxf/ y en el directorio raíz."""
        patrones = [
            os.path.join(_DIR_RAIZ, "dxf", "*.dxf"),
            os.path.join(_DIR_RAIZ, "*.dxf")
        ]
        archivos = []
        for p in patrones:
            archivos.extend(glob.glob(p))
        
        vistos = set()
        resultado = []
        for f in archivos:
            nombre = os.path.basename(f)
            if nombre not in vistos:
                vistos.add(nombre)
                resultado.append(f)
        return resultado

    def cargar_dxf(self, ruta_archivo: str, params_receta: Dict) -> Dict:
        """Extrae y calibra las trayectorias del archivo DXF aplicando los parámetros de receta."""
        if not os.path.exists(ruta_archivo):
            raise FileNotFoundError(f"No existe el archivo: {ruta_archivo}")

        self.ruta_dxf_actual = ruta_archivo
        self.nombre_dxf_actual = os.path.basename(ruta_archivo)

        lector = LectorDXF(ruta_archivo)
        self.trazos_originales = lector.extraer_coordenadas()

        if not self.trazos_originales:
            raise ValueError(f"No se encontraron entidades vectoriales en {self.nombre_dxf_actual}")

        return self.recalcular_trayectorias(params_receta)

    def recalcular_trayectorias(self, params_receta: Dict) -> Dict:
        """Aplica escala, rotación y optimización TSP a los trazos originales."""
        if not self.trazos_originales:
            return {}

        escala = float(params_receta.get("escala_dibujo", 0.90))
        rotar_90 = bool(params_receta.get("rotar_90_grados", 0))
        rotacion_grados = params_receta.get("rotacion_grados", None)
        tol_rdp = float(params_receta.get("tolerancia_rdp", 0.005))
        tol_union = float(params_receta.get("tolerancia_union", 0.08))
        long_min = float(params_receta.get("longitud_min_trazo", 0.01))

        cfg = HARDWARE_CONFIG.get(self.hal_actual, HARDWARE_CONFIG["maqueta_servos"])
        cal_ancho = cfg.get("marco_ancho_cm", 28.0)
        cal_alto = cfg.get("marco_alto_cm", 25.0)

        self.trazos_calibrados = transformar_y_escalar_dxf(
            self.trazos_originales,
            x_min_limit=self.x_min_limit,
            x_max_limit=self.x_max_limit,
            y_min_limit=self.y_min_limit,
            y_max_limit=self.y_max_limit,
            escala=escala,
            rotar_90_grados=rotar_90,
            rotacion_grados=rotacion_grados,
            marco_ancho_cm=cal_ancho,
            marco_alto_cm=cal_alto,
            base_ancho_cm=self.ancho_base_cm,
            base_alto_cm=self.alto_base_cm,
            tolerancia_rdp=tol_rdp,
            tolerancia_union=tol_union,
            longitud_min_trazo=long_min,
            optimizar_recorrido=True,
            centro_x=self.centro_x,
            centro_y=self.centro_y
        )

        # Generar trazos métricos en centímetros para el Canvas (1:1 estricto sobre el área base)
        self.trazos_fisicos_cm = []
        rango_x = self.x_max_limit - self.x_min_limit
        rango_y = self.y_max_limit - self.y_min_limit
        kx = cal_alto / rango_x if rango_x > 0 else 1.0
        ky = cal_ancho / rango_y if rango_y > 0 else 1.0

        cx_base = self.ancho_base_cm / 2.0
        cy_base = self.alto_base_cm / 2.0

        for ruta in self.trazos_calibrados:
            ruta_cm = []
            for xs, ys in ruta:
                x_cm = cx_base + (xs - self.centro_x) * kx
                y_cm = cy_base + (ys - self.centro_y) * ky
                ruta_cm.append((round(x_cm, 3), round(y_cm, 3)))
            self.trazos_fisicos_cm.append(ruta_cm)

        min_x, max_x, min_y, max_y = obtener_limites_dxf(self.trazos_calibrados)
        total_puntos = sum(len(t) for t in self.trazos_calibrados)

        return {
            "archivo": self.nombre_dxf_actual,
            "ruta": self.ruta_dxf_actual,
            "num_trazos": len(self.trazos_calibrados),
            "num_waypoints": total_puntos,
            "ancho_cm": round(max_x - min_x, 2),
            "alto_cm": round(max_y - min_y, 2),
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "limites_hardware": {
                "x_min": self.x_min_limit, "x_max": self.x_max_limit,
                "y_min": self.y_min_limit, "y_max": self.y_max_limit
            }
        }

    # =========================================================================
    # MOTOR DE EJECUCIÓN ASÍNCRONO EN TIEMPO REAL
    # =========================================================================
    def iniciar_ejecucion(self,
                          params_receta: Dict,
                          on_progress: Callable,
                          on_log: Callable,
                          on_finished: Callable):
        """Lanza el proceso de trazado en un hilo de ejecución independiente."""
        if self._en_ejecucion:
            return

        self._evento_detener.clear()
        self._evento_pausa.set()
        self._en_ejecucion = True
        self._esta_pausado = False

        self._hilo_ejecucion = threading.Thread(
            target=self._hilo_trabajo,
            args=(params_receta, on_progress, on_log, on_finished),
            daemon=True
        )
        self._hilo_ejecucion.start()

    def pausar_o_reanudar(self) -> bool:
        """Alterna entre pausa y reanudación de forma no bloqueante."""
        if not self._en_ejecucion:
            return False

        if self._esta_pausado:
            self._esta_pausado = False
            self._evento_pausa.set()
            if self.hal_actual == "thorlabs_galvo":
                if hasattr(self.controlador_hardware, "encender_laser"):
                    self.controlador_hardware.encender_laser()
            elif self.esta_conectado_fisico():
                threading.Thread(target=lambda: self._enviar_seguro("LASER_ON"), daemon=True).start()
            return False
        else:
            self._esta_pausado = True
            self._evento_pausa.clear()
            if self.hal_actual == "thorlabs_galvo":
                if hasattr(self.controlador_hardware, "apagar_laser"):
                    self.controlador_hardware.apagar_laser()
            elif self.esta_conectado_fisico():
                threading.Thread(target=lambda: self._enviar_seguro("LASER_OFF"), daemon=True).start()
            return True

    def pausar_por_seguridad(self):
        """Pausa inmediata del láser preventivamente de forma no bloqueante."""
        if not self._en_ejecucion:
            return
        self._esta_pausado = True
        self._evento_pausa.clear()

    def detener_ejecucion(self):
        """
        Detiene la ejecución activa inmediatamente.
        Activa flags de detención y ejecuta parada de emergencia en el controlador activo.
        """
        if not self._en_ejecucion:
            return
        self._evento_detener.set()
        self._evento_pausa.set()
        if self.controlador_hardware:
            try:
                if hasattr(self.controlador_hardware, "abortar_inmediato"):
                    self.controlador_hardware.abortar_inmediato()
                else:
                    self.apagar_laser()
            except Exception as e:
                print(f"[PuenteLaser] Error al invocar abortar_inmediato: {e}")

    def _enviar_seguro(self, comando: str, timeout: float = 15.0) -> str:
        """Envía un comando al controlador serial verificando cancelación previa y durante la espera."""
        if self._evento_detener.is_set():
            return "DETENIDO"

        with self._serial_lock:
            if self._evento_detener.is_set():
                return "DETENIDO"
            if self.esta_conectado_fisico() and hasattr(self.controlador_hardware, "enviar_comando"):
                try:
                    return self.controlador_hardware.enviar_comando(
                        comando,
                        timeout_segundos=timeout,
                        check_cancel=lambda: self._evento_detener.is_set()
                    )
                except Exception as e:
                    print(f"[PuenteLaser] Error enviando '{comando}': {e}")
            return "OK"

    @property
    def en_ejecucion(self) -> bool:
        return self._en_ejecucion

    @property
    def esta_pausado(self) -> bool:
        return self._esta_pausado

    def _hilo_trabajo(self,
                      params: Dict,
                      on_progress: Callable,
                      on_log: Callable,
                      on_finished: Callable):
        """
        Motor de ejecución cinemática y telemetría de alta fidelidad:
        - Alimenta continuamente el buffer FIFO (64 slots) del ESP32 sin inanición (cero vibración).
        - Mantiene sincronización exacta de velocidad y tiempo físico entre el hardware y la GUI.
        - Tiempos de espera adaptativos para garantizar que trazos largos no provoquen timeouts ni desincronización.
        """
        t_inicio = time.time()
        estado = "COMPLETADO"
        error_msg = ""

        trazos = self.trazos_calibrados
        if not trazos:
            self._en_ejecucion = False
            on_finished("ERROR", "No hay trayectorias calculadas para ejecutar", 0)
            return

        v_trazado = float(params.get("velocidad_trazado", 2.0))
        v_viaje = float(params.get("velocidad_viaje", 3.5))
        dur_min_seg = int(params.get("duracion_min_segmento_ms", 50))
        dur_min_viaje = int(params.get("duracion_min_viaje_ms", 300))

        total_trazos = len(trazos)
        total_puntos = sum(len(t) for t in trazos)

        on_log(f"=== INICIO DE CORTE / TRAZADO: {self.nombre_dxf_actual} ===")
        on_log(f"Hardware: {self.obtener_nombre_hardware()} | Modo: {'HARDWARE ACTIVO (' + str(self.puerto_conectado) + ')' if self.esta_conectado_fisico() else 'SIMULACIÓN VIRTUAL'}")
        on_log(f"Trazos: {total_trazos} | Waypoints totales: {total_puntos}")
        on_log(f"Velocidad trazado: {v_trazado} mm/s | Viaje: {v_viaje} mm/s")

        try:
            # 1. Construir secuencia determinista de waypoints idéntica a backend puro
            waypoints = []
            pos_x = self.centro_x
            pos_y = self.centro_y

            for idx_t, ruta in enumerate(trazos):
                if not ruta:
                    continue

                total_segs_trazo = max(1, len(ruta) - 1)
                primer_pt = ruta[0]
                dx = primer_pt[0] - pos_x
                dy = primer_pt[1] - pos_y
                dist_viaje = math.hypot(dx, dy)
                dur_viaje_ms = max(dur_min_viaje, int((dist_viaje / max(0.1, v_viaje)) * 1000))

                # Segmento de traslado rápido con láser apagado (0)
                waypoints.append({
                    "cmd": f"P {primer_pt[0]:.2f},{primer_pt[1]:.2f},{dur_viaje_ms},0",
                    "x": primer_pt[0],
                    "y": primer_pt[1],
                    "p_ini_x": pos_x,
                    "p_ini_y": pos_y,
                    "dur_ms": dur_viaje_ms,
                    "laser": 0,
                    "trazo_idx": idx_t,
                    "seg_idx": 0,
                    "total_segs_trazo": total_segs_trazo,
                    "pt_idx": 0,
                    "total_pts_trazo": len(ruta),
                    "es_corte": False
                })
                pos_x, pos_y = primer_pt

                # Segmentos de trazado activo con láser encendido (1)
                for i_pt in range(1, len(ruta)):
                    pt = ruta[i_pt]
                    dx = pt[0] - pos_x
                    dy = pt[1] - pos_y
                    dist_seg = math.hypot(dx, dy)
                    dur_seg_ms = max(dur_min_seg, int((dist_seg / max(0.1, v_trazado)) * 1000))

                    waypoints.append({
                        "cmd": f"P {pt[0]:.2f},{pt[1]:.2f},{dur_seg_ms},1",
                        "x": pt[0],
                        "y": pt[1],
                        "p_ini_x": pos_x,
                        "p_ini_y": pos_y,
                        "dur_ms": dur_seg_ms,
                        "laser": 1,
                        "trazo_idx": idx_t,
                        "seg_idx": i_pt - 1,
                        "total_segs_trazo": total_segs_trazo,
                        "pt_idx": i_pt,
                        "total_pts_trazo": len(ruta),
                        "es_corte": True
                    })
                    pos_x, pos_y = pt

                # Apagar láser al completar el trazo (50ms estándar)
                waypoints.append({
                    "cmd": f"P {pos_x:.2f},{pos_y:.2f},50,0",
                    "x": pos_x,
                    "y": pos_y,
                    "p_ini_x": pos_x,
                    "p_ini_y": pos_y,
                    "dur_ms": 50,
                    "laser": 0,
                    "trazo_idx": idx_t,
                    "seg_idx": total_segs_trazo - 1,
                    "total_segs_trazo": total_segs_trazo,
                    "pt_idx": len(ruta) - 1,
                    "total_pts_trazo": len(ruta),
                    "es_corte": False
                })

            total_wps = len(waypoints)
            total_puntos_corte = max(1, sum(1 for wp in waypoints if wp["es_corte"]))
            puntos_corte_acum = 0

            # 2. Hilo de transmisión serie continua directa al hardware
            def _hilo_transmision():
                for wp in waypoints:
                    if self._evento_detener.is_set():
                        break
                    while not self._evento_pausa.is_set():
                        if self._evento_detener.is_set():
                            break
                        time.sleep(0.05)

                    timeout_seg = max(30.0, (wp["dur_ms"] / 1000.0) * 1.5 + 15.0)
                    resp = self._enviar_seguro(wp["cmd"], timeout=timeout_seg)
                    if resp in ("ABORTADO", "DETENIDO") or self._evento_detener.is_set():
                        break
                    if resp == "TIMEOUT" or resp.startswith("ERR"):
                        on_log(f"[ESP32] Advertencia en '{wp['cmd']}': {resp}")

                # Cleanup de parada de emergencia: enviar CLEAR+LASER_OFF bajo lock
                if self._evento_detener.is_set() and self.esta_conectado_fisico():
                    with self._serial_lock:
                        try:
                            self.controlador_hardware.conexion.reset_input_buffer()
                            self.controlador_hardware.conexion.write(b"CLEAR\nLASER_OFF\n")
                            self.controlador_hardware.conexion.flush()
                        except Exception:
                            pass

                if not self._evento_detener.is_set():
                    on_log("Esperando finalización física del trazado en el microcontrolador...")
                    resp_wait = self._enviar_seguro("WAIT", timeout=90.0)
                    if not self._evento_detener.is_set() and resp_wait != "ABORTADO":
                        on_log(f"-> Retornando al centro de reposo ({self.centro_x:.2f}, {self.centro_y:.2f})...")
                        cmd_home = f"P {self.centro_x:.2f},{self.centro_y:.2f},400,0"
                        self._enviar_seguro(cmd_home, timeout=15.0)
                        self._enviar_seguro("WAIT", timeout=10.0)

            def _hilo_transmision_galvo():
                try:
                    if hasattr(self.controlador_hardware, "trazar_trayectorias"):
                        self.controlador_hardware.trazar_trayectorias(
                            trazos,
                            velocidad_marcado=v_trazado,
                            velocidad_salto=v_viaje
                        )
                except Exception as e:
                    on_log(f"[Thorlabs GVS] Excepción en trazado galvo: {e}")

            hilo_tx = None
            if self.hal_actual == "thorlabs_galvo":
                hilo_tx = threading.Thread(target=_hilo_transmision_galvo, daemon=True)
                hilo_tx.start()
            elif self.esta_conectado_fisico():
                with self._serial_lock:
                    try:
                        self.controlador_hardware.conexion.reset_input_buffer()
                        # Limpiar flag de aborto del firmware para permitir nuevos waypoints
                        self.controlador_hardware.conexion.write(b"RESUME\n")
                        self.controlador_hardware.conexion.flush()
                        # Esperar y descartar la respuesta del RESUME
                        time.sleep(0.05)
                        self.controlador_hardware.conexion.reset_input_buffer()
                    except Exception:
                        pass
                hilo_tx = threading.Thread(target=_hilo_transmision, daemon=True)
                hilo_tx.start()

            # 3. Telemetría visual en tiempo real sincronizada con la cinemática a 35 fps
            for wp in waypoints:
                if self._evento_detener.is_set():
                    estado = "DETENIDO"
                    break

                dur_s = wp["dur_ms"] / 1000.0
                t_seg_start = time.time()

                while True:
                    if self._evento_detener.is_set():
                        estado = "DETENIDO"
                        break

                    while not self._evento_pausa.is_set():
                        if self._evento_detener.is_set():
                            estado = "DETENIDO"
                            break
                        time.sleep(0.05)
                        t_seg_start += 0.05

                    transcurrido = time.time() - t_seg_start
                    frac = min(1.0, transcurrido / max(0.001, dur_s))

                    cur_x = wp["p_ini_x"] + (wp["x"] - wp["p_ini_x"]) * frac
                    cur_y = wp["p_ini_y"] + (wp["y"] - wp["p_ini_y"]) * frac

                    p_corte_frac = (puntos_corte_acum + frac) if wp["es_corte"] else puntos_corte_acum
                    pct_total = round((p_corte_frac / total_puntos_corte) * 100.0, 1)

                    if wp["es_corte"]:
                        pct_trazo = round(((wp.get("seg_idx", 0) + frac) / max(1, wp.get("total_segs_trazo", 1))) * 100.0, 1)
                    else:
                        pct_trazo = 0.0 if wp["pt_idx"] == 0 else 100.0

                    on_progress(
                        wp["trazo_idx"], total_trazos,
                        wp["pt_idx"], wp["total_pts_trazo"],
                        cur_x, cur_y, min(100.0, pct_trazo), min(100.0, pct_total), wp["es_corte"]
                    )

                    if frac >= 1.0:
                        break
                    time.sleep(0.028)

                if wp["es_corte"]:
                    puntos_corte_acum += 1

            # 4. Esperar finalización del hilo de hardware (rápido en caso de stop)
            if hilo_tx and hilo_tx.is_alive():
                timeout_join = 1.0 if self._evento_detener.is_set() else 100.0
                hilo_tx.join(timeout=timeout_join)

            # 5. Manejo de fin o parada de emergencia
            if self._evento_detener.is_set():
                estado = "DETENIDO"
                on_log("[STOP] Parada de emergencia ejecutada.")
                if self.hal_actual == "thorlabs_galvo":
                    self.apagar_laser()
                    if hasattr(self.controlador_hardware, "abortar_inmediato"):
                        self.controlador_hardware.abortar_inmediato()
                    on_log("[STOP] Cabezal Thorlabs GVS en reposo seguro.")
                elif self.esta_conectado_fisico() and getattr(self.controlador_hardware, "conexion", None):
                    # Red de seguridad final: hilo_tx ya terminó, nadie más tiene el lock
                    with self._serial_lock:
                        try:
                            self.controlador_hardware.conexion.reset_input_buffer()
                            self.controlador_hardware.conexion.write(b"CLEAR\nLASER_OFF\n")
                            self.controlador_hardware.conexion.flush()
                            time.sleep(0.05)
                            cmd_home = f"P {self.centro_x:.2f},{self.centro_y:.2f},400,0\n".encode('utf-8')
                            self.controlador_hardware.conexion.write(cmd_home)
                            self.controlador_hardware.conexion.flush()
                        except Exception:
                            pass
                    on_log("[STOP] Microcontrolador reseteado y en Home.")
            else:
                on_log("¡Ciclo de trabajo completado con éxito!")

        except Exception as e:
            estado = "ERROR"
            error_msg = str(e)
            on_log(f"[ERROR] Excepción durante ejecución: {e}")
            self.apagar_laser()

        finally:
            duracion_s = round(time.time() - t_inicio, 2)
            self._en_ejecucion = False
            self._esta_pausado = False

            try:
                receta_id = params.get("_receta_id")
                receta_nom = params.get("_receta_nombre", "Manual")
                self.gestor_trazabilidad.registrar_ciclo({
                    "operador": "Operador",
                    "archivo_dxf": self.nombre_dxf_actual or "Desconocido",
                    "hardware_usado": self.hal_actual,
                    "receta_id": receta_id,
                    "receta_nombre": receta_nom,
                    "velocidad_trazado": v_trazado,
                    "velocidad_viaje": v_viaje,
                    "escala_dibujo": float(params.get("escala_dibujo", 0.9)),
                    "tolerancia_rdp": float(params.get("tolerancia_rdp", 0.005)),
                    "tolerancia_union": float(params.get("tolerancia_union", 0.08)),
                    "trazos_totales": total_trazos,
                    "waypoints_totales": total_puntos,
                    "estado": estado,
                    "mensaje_error": error_msg,
                    "duracion_segundos": duracion_s
                })
                on_log(f"[BD] Ciclo registrado en historial_produccion: Estado={estado}, Duración={duracion_s}s")
            except Exception as e_bd:
                on_log(f"[BD] Aviso: no se pudo guardar trazabilidad: {e_bd}")

            on_finished(estado, error_msg, duracion_s)
