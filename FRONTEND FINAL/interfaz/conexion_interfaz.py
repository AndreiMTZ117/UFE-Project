# -*- coding: utf-8 -*-
"""
interfaz/conexion_interfaz.py — Puente de Conexión Backend <-> Interfaz Gráfica

Gestiona:
  1. Base de datos SQLite3 (GestorRecetas y GestorTrazabilidad)
  2. Procesamiento de archivos DXF y G-code (LectorDXF, LectorGcode y GeneradorMatrizTemporal)
  3. Control unificado del hardware Thorlabs GVS112/M (SIMULACIÓN o PXI-6229 REAL)
  4. Hilo asíncrono de ejecucion de corte/trazado sincronizado en tiempo real con
     la cinemática física y control estricto del estado del laser.
"""

import os
import sys
import glob
import time
import math
import threading
from typing import Callable, Optional, Dict, List, Tuple, Any

import numpy as np

# Asegurar importación de módulos del proyecto
_DIR_RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _DIR_RAIZ not in sys.path:
    sys.path.insert(0, _DIR_RAIZ)

from core.lector_dxf import LectorDXF, obtener_limites_dxf
from core.lector_gcode import LectorGcode
from core.generador_matriz_temporal import GeneradorMatrizTemporal
from core.generador_trayectorias import transformar_y_escalar_dxf
from database.recetas import GestorRecetas
from database.trazabilidad import GestorTrazabilidad
from hardware_thorlabs_galvo.config_galvo import (
    CAMPO_X_MIN_MM, CAMPO_X_MAX_MM,
    CAMPO_Y_MIN_MM, CAMPO_Y_MAX_MM,
    ESCALA_DIBUJO, ROTAR_90_GRADOS,
    VELOCIDAD_MARCADO_MM_S, VELOCIDAD_SALTO_MM_S,
    FRECUENCIA_MUESTREO_HZ, ESCALA_VX_POR_MM, ESCALA_VY_POR_MM,
    OFFSET_VX, OFFSET_VY, JUMP_DELAY_US, LASER_ON_DELAY_US, LASER_OFF_DELAY_US,
    MODO_HARDWARE
)


def cargar_perfil_hardware(clave: str = "thorlabs_galvo") -> Dict[str, Any]:
    """Carga el perfil cinemático y geométrico del hardware Thorlabs GVS112/M."""
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
    }


# Único perfil de hardware: Thorlabs GVS112/M
HARDWARE_CONFIG = {
    "thorlabs_galvo": cargar_perfil_hardware("thorlabs_galvo")
}


class PuenteLaser:
    """Puente integral entre la interfaz de usuario y el motor backend Thorlabs."""

    def __init__(self):
        self.gestor_recetas = GestorRecetas()
        self.gestor_trazabilidad = GestorTrazabilidad()

        self.controlador_hardware: Optional[Any] = None
        self.puerto_conectado: Optional[str] = None
        self.es_simulacion = True

        # HAL: siempre Thorlabs GVS112/M
        self.hal_actual = "thorlabs_galvo"
        cfg_init = HARDWARE_CONFIG["thorlabs_galvo"]
        self.x_min_limit = cfg_init.get("x_min", -50.0)
        self.x_max_limit = cfg_init.get("x_max",  50.0)
        self.y_min_limit = cfg_init.get("y_min", -50.0)
        self.y_max_limit = cfg_init.get("y_max",  50.0)

        # Centro en el origen óptico nativo del galvo (0,0)
        self.centro_x = cfg_init.get("centro_x", 0.0)
        self.centro_y = cfg_init.get("centro_y", 0.0)
        self.ancho_base_cm = cfg_init.get("ancho_base_cm", 10.0)
        self.alto_base_cm  = cfg_init.get("alto_base_cm",  10.0)
        self.centro_cm_x = round(self.ancho_base_cm / 2.0, 2)
        self.centro_cm_y = round(self.alto_base_cm  / 2.0, 2)

        # Archivo DXF/G-code y geometrías cargadas
        self.ruta_dxf_actual: Optional[str] = None
        self.nombre_dxf_actual: Optional[str] = None
        self.es_gcode: bool = False
        self.trazos_originales: List[List[Tuple[float, float]]] = []
        self.trazos_calibrados: List[List[Tuple[float, float]]] = []
        self.trazos_fisicos_cm: List[List[Tuple[float, float]]] = []

        # Saltos rápidos (G0 / laser OFF) para visualización dual
        self.saltos_rapidos: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        self.saltos_fisicos_cm: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []

        # Señales discretas DAQ y metricas analiticas
        self.tiempo_estimado_s: float = 0.0
        self.n_muestras_daq: int = 0
        self.max_vx: float = 0.0
        self.max_vy: float = 0.0
        self._matriz_voltajes: Optional[np.ndarray] = None
        self._mascara_laser: Optional[np.ndarray] = None

        # Estado de ejecucion del hilo
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

        cfg = HARDWARE_CONFIG["thorlabs_galvo"]
        self.centro_x = cfg["centro_x"]
        self.centro_y = cfg["centro_y"]
        print(f"[PuenteLaser] Dimensiones base: {self.ancho_base_cm:.1f} x {self.alto_base_cm:.1f} cm | Centro: ({self.centro_cm_x:.2f}, {self.centro_cm_y:.2f}) cm")

    def set_centro_cm(self, x_cm: float, y_cm: float):
        """Define el centro de la base en centímetros (alteración manual del usuario)."""
        self.centro_cm_x = float(x_cm)
        self.centro_cm_y = float(y_cm)

        cfg = HARDWARE_CONFIG["thorlabs_galvo"]
        cal_ancho = cfg.get("marco_ancho_cm", 10.0)
        cal_alto = cfg.get("marco_alto_cm", 10.0)
        rango_x = self.x_max_limit - self.x_min_limit
        rango_y = self.y_max_limit - self.y_min_limit
        kx = cal_alto / rango_x if rango_x > 0 else 1.0
        ky = cal_ancho / rango_y if rango_y > 0 else 1.0

        dx_cm = self.centro_cm_x - (self.ancho_base_cm / 2.0)
        dy_cm = self.centro_cm_y - (self.alto_base_cm / 2.0)

        hw_cx = cfg["centro_x"]
        hw_cy = cfg["centro_y"]

        self.centro_x = round(hw_cx + (dx_cm / kx), 3)
        self.centro_y = round(hw_cy + (dy_cm / ky), 3)

        self.centro_x = max(self.x_min_limit, min(self.x_max_limit, self.centro_x))
        self.centro_y = max(self.y_min_limit, min(self.y_max_limit, self.centro_y))

        print(f"[PuenteLaser] Centro manual: ({self.centro_cm_x:.2f}, {self.centro_cm_y:.2f}) cm -> Hardware: ({self.centro_x:.2f}, {self.centro_y:.2f}) mm")

    def cambiar_hardware(self, hal_nombre: str = "thorlabs_galvo"):
        """Método de compatibilidad — el hardware siempre es Thorlabs GVS112/M."""
        cfg = HARDWARE_CONFIG["thorlabs_galvo"]
        self.hal_actual = "thorlabs_galvo"
        self.x_min_limit = cfg.get("x_min", -50.0)
        self.x_max_limit = cfg.get("x_max",  50.0)
        self.y_min_limit = cfg.get("y_min", -50.0)
        self.y_max_limit = cfg.get("y_max",  50.0)
        self.centro_x = cfg.get("centro_x", 0.0)
        self.centro_y = cfg.get("centro_y", 0.0)
        self.ancho_base_cm = cfg.get("ancho_base_cm", 10.0)
        self.alto_base_cm  = cfg.get("alto_base_cm",  10.0)
        self.centro_cm_x = round(self.ancho_base_cm / 2.0, 2)
        self.centro_cm_y = round(self.alto_base_cm  / 2.0, 2)

    # =========================================================================
    # GESTIÓN DE BASE DE DATOS (RECETAS)
    # =========================================================================
    def obtener_recetas(self) -> List[Dict]:
        try:
            return self.gestor_recetas.listar_recetas()
        except Exception as e:
            print(f"[Conexion] Error al listar recetas: {e}")
            return []

    def obtener_receta_por_id(self, receta_id: int) -> Dict:
        try:
            return self.gestor_recetas.obtener_receta(receta_id)
        except Exception as e:
            print(f"[Conexion] Error al obtener receta {receta_id}: {e}")
            return {}

    def obtener_receta_default(self) -> Dict:
        recetas = self.obtener_recetas()
        for r in recetas:
            if "acrílico" in r.get("nombre", "").lower() or "estándar" in r.get("nombre", "").lower():
                return r
        return recetas[0] if recetas else {}

    def guardar_o_actualizar_receta(self, datos: Dict, receta_id: Optional[int] = None) -> int:
        if receta_id is not None:
            self.gestor_recetas.actualizar_receta(receta_id, datos)
            return receta_id
        else:
            return self.gestor_recetas.crear_receta(datos)

    def eliminar_receta(self, receta_id: int) -> bool:
        try:
            return self.gestor_recetas.eliminar_receta(receta_id)
        except Exception as e:
            print(f"[Conexion] Error al eliminar receta {receta_id}: {e}")
            return False

    # =========================================================================
    # CONEXIÓN AL HARDWARE THORLABS (DAQ o Simulación)
    # =========================================================================
    def listar_puertos_com(self) -> List[str]:
        """Stub de compatibilidad — Thorlabs no usa puertos COM serie."""
        return []

    def conectar_puerto(self, puerto: str = "Thorlabs GVS") -> bool:
        """Inicializa el controlador Thorlabs GVS112/M."""
        return self.conectar_thorlabs()

    def conectar_thorlabs(self) -> bool:
        """Inicializa el driver unificado Thorlabs GVS112/M (SIMULACIÓN o PXI-6229 REAL)."""
        try:
            if self.controlador_hardware:
                try:
                    self.controlador_hardware.cerrar()
                except Exception:
                    pass
                self.controlador_hardware = None

            from hardware_thorlabs_galvo.controlador_thorlabs import ControladorThorlabsGVS
            self.controlador_hardware = ControladorThorlabsGVS()
            self.puerto_conectado = "Thorlabs GVS (NI PXI-6229 / Sim)"
            modo = getattr(self.controlador_hardware, 'modo', 'SIMULACION')
            self.es_simulacion = (modo != 'REAL')
            return True
        except Exception as e:
            print(f"[Conexion] Excepcion al inicializar Thorlabs: {e}")
            self.es_simulacion = True
            return False

    def esta_conectado_fisico(self) -> bool:
        """Informa si el controlador está en modo REAL (con tarjeta NI conectada)."""
        if not self.controlador_hardware:
            return False
        modo = getattr(self.controlador_hardware, 'modo', 'SIMULACION')
        return modo == 'REAL'

    def obtener_nombre_hardware(self) -> str:
        cfg = HARDWARE_CONFIG["thorlabs_galvo"]
        return cfg.get("nombre", "Thorlabs Galvo Scanner (GVS112/M)")

    def centrar_espejos(self):
        """Posiciona los espejos galvo en el origen óptico (0.0 V, 0.0 V)."""
        if self.controlador_hardware and hasattr(self.controlador_hardware, "centrar_espejos"):
            try:
                self.controlador_hardware.centrar_espejos()
            except Exception as e:
                print(f"[PuenteLaser] Error al centrar espejos: {e}")

    def apagar_laser(self):
        """Apaga el laser de forma segura en el hardware Thorlabs."""
        if self.controlador_hardware and hasattr(self.controlador_hardware, "apagar_laser"):
            try:
                self.controlador_hardware.apagar_laser()
            except Exception as e:
                print(f"[PuenteLaser] Error apagando laser: {e}")

    # =========================================================================
    # PROCESAMIENTO Y CARGA DE ARCHIVOS DXF / G-CODE
    # =========================================================================
    def listar_archivos_dxf(self) -> List[str]:
        """Busca archivos DXF y G-code en la carpeta dxf/ y en el directorio raiz."""
        extensiones = ["*.dxf", "*.gcode", "*.nc", "*.ngc"]
        archivos = []
        for ext in extensiones:
            archivos.extend(glob.glob(os.path.join(_DIR_RAIZ, "dxf", ext)))
            archivos.extend(glob.glob(os.path.join(_DIR_RAIZ, ext)))

        vistos = set()
        resultado = []
        for f in archivos:
            nombre = os.path.basename(f)
            if nombre not in vistos:
                vistos.add(nombre)
                resultado.append(f)
        return resultado

    def cargar_dxf(self, ruta_archivo: str, params_receta: Dict) -> Dict:
        """
        Carga y procesa un archivo vectorial DXF o de máquina G-code (.gcode, .nc, .ngc).
        """
        if not os.path.exists(ruta_archivo):
            raise FileNotFoundError(f"No existe el archivo: {ruta_archivo}")

        self.ruta_dxf_actual = ruta_archivo
        self.nombre_dxf_actual = os.path.basename(ruta_archivo)
        self.es_gcode = ruta_archivo.lower().endswith(('.gcode', '.nc', '.ngc'))

        if self.es_gcode:
            return self._cargar_gcode(ruta_archivo, params_receta)
        else:
            lector = LectorDXF(ruta_archivo)
            self.trazos_originales = lector.extraer_coordenadas()
            if not self.trazos_originales:
                raise ValueError(f"No se encontraron entidades vectoriales en {self.nombre_dxf_actual}")
            return self.recalcular_trayectorias(params_receta)

    def _cargar_gcode(self, ruta_archivo: str, params_receta: Dict) -> Dict:
        """Intérprete y discretizador para archivos G-code estándar."""
        v_trazado = float(params_receta.get("velocidad_trazado", VELOCIDAD_MARCADO_MM_S))
        v_viaje   = float(params_receta.get("velocidad_viaje", VELOCIDAD_SALTO_MM_S))

        lector = LectorGcode(
            ruta_archivo,
            feed_defecto_mm_min=v_trazado * 60.0,
            feed_viaje_mm_min=v_viaje * 60.0
        )
        segmentos = lector.leer()
        if not segmentos:
            raise ValueError(f"No se encontraron comandos de movimiento en {self.nombre_dxf_actual}")

        gen = GeneradorMatrizTemporal(
            fs=FRECUENCIA_MUESTREO_HZ,
            escala_vx=ESCALA_VX_POR_MM,
            escala_vy=ESCALA_VY_POR_MM,
            offset_vx=OFFSET_VX,
            offset_vy=OFFSET_VY,
            jump_delay_us=JUMP_DELAY_US,
            laser_on_delay_us=LASER_ON_DELAY_US,
            laser_off_delay_us=LASER_OFF_DELAY_US,
            velocidad_defecto_mm_s=v_trazado,
            velocidad_viaje_mm_s=v_viaje,
        )
        M, L, info = gen.generar(segmentos)
        self._matriz_voltajes = M
        self._mascara_laser = L
        self.tiempo_estimado_s = info["tiempo_total_s"]
        self.n_muestras_daq = info["n_muestras"]
        self.max_vx = info["max_vx"]
        self.max_vy = info["max_vy"]

        # Extraer trazos de corte (marcado) y saltos de viaje
        trazos_corte: List[List[Tuple[float, float]]] = []
        saltos: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        trazo_actual: List[Tuple[float, float]] = []

        for seg in segmentos:
            p1 = (float(seg["x1"]), float(seg["y1"]))
            p2 = (float(seg["x2"]), float(seg["y2"]))
            if seg["laser_on"]:
                if not trazo_actual:
                    trazo_actual.append(p1)
                trazo_actual.append(p2)
            else:
                if trazo_actual:
                    trazos_corte.append(trazo_actual)
                    trazo_actual = []
                saltos.append((p1, p2))
        if trazo_actual:
            trazos_corte.append(trazo_actual)

        self.trazos_calibrados = trazos_corte
        self.saltos_rapidos = saltos

        # Mapear a centímetros para el Canvas 1:1
        cfg = HARDWARE_CONFIG["thorlabs_galvo"]
        cal_ancho = cfg.get("marco_ancho_cm", 10.0)
        cal_alto  = cfg.get("marco_alto_cm", 10.0)
        rango_x = self.x_max_limit - self.x_min_limit
        rango_y = self.y_max_limit - self.y_min_limit
        kx = cal_alto / rango_x if rango_x > 0 else 1.0
        ky = cal_ancho / rango_y if rango_y > 0 else 1.0
        cx_base = self.ancho_base_cm / 2.0
        cy_base = self.alto_base_cm / 2.0

        self.trazos_fisicos_cm = []
        for ruta in self.trazos_calibrados:
            ruta_cm = []
            for xs, ys in ruta:
                x_cm = cx_base + (xs - self.centro_x) * kx
                y_cm = cy_base + (ys - self.centro_y) * ky
                ruta_cm.append((round(x_cm, 3), round(y_cm, 3)))
            self.trazos_fisicos_cm.append(ruta_cm)

        self.saltos_fisicos_cm = []
        for p1, p2 in saltos:
            p1_cm = (round(cx_base + (p1[0] - self.centro_x) * kx, 3),
                     round(cy_base + (p1[1] - self.centro_y) * ky, 3))
            p2_cm = (round(cx_base + (p2[0] - self.centro_x) * kx, 3),
                     round(cy_base + (p2[1] - self.centro_y) * ky, 3))
            self.saltos_fisicos_cm.append((p1_cm, p2_cm))

        min_x, max_x, min_y, max_y = obtener_limites_dxf(self.trazos_calibrados) if self.trazos_calibrados else (0,0,0,0)
        total_puntos = sum(len(t) for t in self.trazos_calibrados)

        return {
            "archivo": self.nombre_dxf_actual,
            "ruta": self.ruta_dxf_actual,
            "num_trazos": len(self.trazos_calibrados),
            "num_waypoints": total_puntos,
            "ancho_cm": round((max_x - min_x) / 10.0, 2),
            "alto_cm": round((max_y - min_y) / 10.0, 2),
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "tiempo_estimado_s": self.tiempo_estimado_s,
            "n_muestras_daq": self.n_muestras_daq,
            "max_vx": self.max_vx,
            "max_vy": self.max_vy,
            "limites_hardware": {
                "x_min": self.x_min_limit, "x_max": self.x_max_limit,
                "y_min": self.y_min_limit, "y_max": self.y_max_limit
            }
        }

    def recalcular_trayectorias(self, params_receta: Dict) -> Dict:
        """Aplica escala, rotación, optimización TSP a los trazos DXF y genera matriz temporal."""
        if not self.trazos_originales:
            return {}

        escala = float(params_receta.get("escala_dibujo", 0.90))
        rotar_90 = bool(params_receta.get("rotar_90_grados", 0))
        rotacion_grados = params_receta.get("rotacion_grados", None)
        tol_rdp = float(params_receta.get("tolerancia_rdp", 0.005))
        tol_union = float(params_receta.get("tolerancia_union", 0.08))
        long_min = float(params_receta.get("longitud_min_trazo", 0.01))
        v_trazado = float(params_receta.get("velocidad_trazado", VELOCIDAD_MARCADO_MM_S))
        v_viaje   = float(params_receta.get("velocidad_viaje", VELOCIDAD_SALTO_MM_S))

        cfg = HARDWARE_CONFIG["thorlabs_galvo"]
        cal_ancho = cfg.get("marco_ancho_cm", 10.0)
        cal_alto = cfg.get("marco_alto_cm", 10.0)

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

        # Generar matriz temporal analítica y metricas de voltajes/tiempo
        gen = GeneradorMatrizTemporal(
            fs=FRECUENCIA_MUESTREO_HZ,
            escala_vx=ESCALA_VX_POR_MM,
            escala_vy=ESCALA_VY_POR_MM,
            offset_vx=OFFSET_VX,
            offset_vy=OFFSET_VY,
            jump_delay_us=JUMP_DELAY_US,
            laser_on_delay_us=LASER_ON_DELAY_US,
            laser_off_delay_us=LASER_OFF_DELAY_US,
            velocidad_defecto_mm_s=v_trazado,
            velocidad_viaje_mm_s=v_viaje,
        )
        M, L, info = gen.desde_trayectorias_dxf(
            self.trazos_calibrados,
            velocidad_corte_mm_s=v_trazado,
            velocidad_viaje_mm_s=v_viaje,
        )
        self._matriz_voltajes = M
        self._mascara_laser = L
        self.tiempo_estimado_s = info["tiempo_total_s"]
        self.n_muestras_daq = info["n_muestras"]
        self.max_vx = info["max_vx"]
        self.max_vy = info["max_vy"]

        # Extraer saltos rápidos de viaje entre trazos DXF
        saltos: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        pos_salto = (self.centro_x, self.centro_y)
        for ruta in self.trazos_calibrados:
            if not ruta:
                continue
            p_ini = ruta[0]
            if math.hypot(p_ini[0] - pos_salto[0], p_ini[1] - pos_salto[1]) > 0.01:
                saltos.append((pos_salto, p_ini))
            pos_salto = ruta[-1]
        self.saltos_rapidos = saltos

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

        self.saltos_fisicos_cm = []
        for p1, p2 in saltos:
            p1_cm = (round(cx_base + (p1[0] - self.centro_x) * kx, 3),
                     round(cy_base + (p1[1] - self.centro_y) * ky, 3))
            p2_cm = (round(cx_base + (p2[0] - self.centro_x) * kx, 3),
                     round(cy_base + (p2[1] - self.centro_y) * ky, 3))
            self.saltos_fisicos_cm.append((p1_cm, p2_cm))

        min_x, max_x, min_y, max_y = obtener_limites_dxf(self.trazos_calibrados)
        total_puntos = sum(len(t) for t in self.trazos_calibrados)

        return {
            "archivo": self.nombre_dxf_actual,
            "ruta": self.ruta_dxf_actual,
            "num_trazos": len(self.trazos_calibrados),
            "num_waypoints": total_puntos,
            "ancho_cm": round((max_x - min_x) / 10.0, 2),
            "alto_cm": round((max_y - min_y) / 10.0, 2),
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "tiempo_estimado_s": self.tiempo_estimado_s,
            "n_muestras_daq": self.n_muestras_daq,
            "max_vx": self.max_vx,
            "max_vy": self.max_vy,
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
        """Inicia el hilo de ejecucion asíncrono para el cabezal Thorlabs."""
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
            if self.controlador_hardware and hasattr(self.controlador_hardware, "encender_laser"):
                self.controlador_hardware.encender_laser()
            return False
        else:
            self._esta_pausado = True
            self._evento_pausa.clear()
            if self.controlador_hardware and hasattr(self.controlador_hardware, "apagar_laser"):
                self.controlador_hardware.apagar_laser()
            return True

    def pausar_por_seguridad(self):
        """Pausa inmediata del laser preventivamente de forma no bloqueante."""
        if not self._en_ejecucion:
            return
        self._esta_pausado = True
        self._evento_pausa.clear()

    def detener_ejecucion(self):
        """Detiene la ejecucion activa inmediatamente y aborta en el controlador."""
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
        """Stub de compatibilidad."""
        if self._evento_detener.is_set():
            return "DETENIDO"
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
        Motor de ejecucion cinemática y telemetría de alta fidelidad:
        - Envía el barrido al driver Thorlabs GVS112/M.
        - Mantiene sincronización de telemetría visual con la GUI.
        """
        t_inicio = time.time()
        estado = "COMPLETADO"
        error_msg = ""

        trazos = self.trazos_calibrados
        if not trazos:
            self._en_ejecucion = False
            on_finished("ERROR", "No hay trayectorias calculadas para ejecutar", 0)
            return

        v_trazado = float(params.get("velocidad_trazado", VELOCIDAD_MARCADO_MM_S))
        v_viaje   = float(params.get("velocidad_viaje", VELOCIDAD_SALTO_MM_S))
        dur_min_seg = int(params.get("duracion_min_segmento_ms", 20))
        dur_min_viaje = int(params.get("duracion_min_viaje_ms", 50))

        total_trazos = len(trazos)
        total_puntos = sum(len(t) for t in trazos)

        on_log(f"=== INICIO DE CORTE / TRAZADO: {self.nombre_dxf_actual} ===")
        on_log(f"Hardware: {self.obtener_nombre_hardware()} | Modo: {'HARDWARE ACTIVO (PXI-6229)' if self.esta_conectado_fisico() else 'SIMULACIÓN VIRTUAL'}")
        on_log(f"Trazos: {total_trazos} | Waypoints totales: {total_puntos}")
        on_log(f"Tiempo analitico estimado: {self.tiempo_estimado_s:.4f} s ({self.n_muestras_daq:,} muestras)")
        on_log(f"Velocidad marcado: {v_trazado} mm/s | Salto rápido: {v_viaje} mm/s")

        try:
            # 1. Construir waypoints de telemetría para GUI
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

                # Salto rápido con laser apagado (0)
                waypoints.append({
                    "x": primer_pt[0], "y": primer_pt[1],
                    "p_ini_x": pos_x,  "p_ini_y": pos_y,
                    "dur_ms": dur_viaje_ms, "laser": 0,
                    "trazo_idx": idx_t, "seg_idx": 0,
                    "total_segs_trazo": total_segs_trazo,
                    "pt_idx": 0, "total_pts_trazo": len(ruta),
                    "es_corte": False
                })
                pos_x, pos_y = primer_pt

                # Trazado activo con laser encendido (1)
                for i_pt in range(1, len(ruta)):
                    pt = ruta[i_pt]
                    dx = pt[0] - pos_x
                    dy = pt[1] - pos_y
                    dist_seg = math.hypot(dx, dy)
                    dur_seg_ms = max(dur_min_seg, int((dist_seg / max(0.1, v_trazado)) * 1000))

                    waypoints.append({
                        "x": pt[0], "y": pt[1],
                        "p_ini_x": pos_x, "p_ini_y": pos_y,
                        "dur_ms": dur_seg_ms, "laser": 1,
                        "trazo_idx": idx_t, "seg_idx": i_pt - 1,
                        "total_segs_trazo": total_segs_trazo,
                        "pt_idx": i_pt, "total_pts_trazo": len(ruta),
                        "es_corte": True
                    })
                    pos_x, pos_y = pt

            total_puntos_corte = max(1, sum(1 for wp in waypoints if wp["es_corte"]))
            puntos_corte_acum = 0

            # 2. Hilo de ejecucion física en hardware Thorlabs
            def _hilo_transmision_galvo():
                try:
                    if self._matriz_voltajes is not None and self._mascara_laser is not None:
                        self.controlador_hardware.trazar_matriz(
                            self._matriz_voltajes,
                            self._mascara_laser,
                            fs=FRECUENCIA_MUESTREO_HZ
                        )
                    elif hasattr(self.controlador_hardware, "trazar_trayectorias"):
                        self.controlador_hardware.trazar_trayectorias(
                            trazos,
                            velocidad_marcado=v_trazado,
                            velocidad_salto=v_viaje
                        )
                except Exception as e_drv:
                    on_log(f"[Thorlabs GVS] Excepcion en driver: {e_drv}")

            hilo_tx = threading.Thread(target=_hilo_transmision_galvo, daemon=True)
            hilo_tx.start()

            # 3. Telemetría visual en tiempo real sincronizada a ~35 fps
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

            # 4. Esperar finalización del hilo de hardware
            if hilo_tx and hilo_tx.is_alive():
                timeout_join = 1.0 if self._evento_detener.is_set() else 100.0
                hilo_tx.join(timeout=timeout_join)

            # 5. Manejo de fin o parada de emergencia
            if self._evento_detener.is_set():
                estado = "DETENIDO"
                on_log("[STOP] Parada de emergencia ejecutada.")
                self.apagar_laser()
                if hasattr(self.controlador_hardware, "abortar_inmediato"):
                    self.controlador_hardware.abortar_inmediato()
                on_log("[STOP] Cabezal Thorlabs GVS en reposo seguro.")
            else:
                on_log("¡Ciclo de trabajo completado con éxito!")

        except Exception as e:
            estado = "ERROR"
            error_msg = str(e)
            on_log(f"[ERROR] Excepcion durante ejecucion: {e}")
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
