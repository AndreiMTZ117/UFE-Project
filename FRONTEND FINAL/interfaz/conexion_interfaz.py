# -*- coding: utf-8 -*-
"""
interfaz/conexion_interfaz.py — Puente de Conexion Backend <-> Interfaz Grafica

Gestiona:
  1. Base de datos SQLite3 (GestorRecetas y GestorTrazabilidad)
  2. Procesamiento de archivos DXF (LectorDXF y transformar_y_escalar_dxf)
  3. Conexion al sistema Thorlabs GVS112/M (fisico o simulacion automatica)
  4. Hilo asincrono de ejecucion con telemetria en tiempo real,
     control estricto del laser y parada instantanea no bloqueante.

Hardware soportado:
  - Thorlabs GVS112/M con tarjeta DAQ/DAC fisica
  - Modo Simulacion automatico cuando el hardware no esta disponible
"""

import os
import sys
import glob
import time
import math
import threading
from typing import Callable, Optional, Dict, List, Tuple, Any

import numpy as np

# Asegurar importacion de modulos del proyecto
_DIR_RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _DIR_RAIZ not in sys.path:
    sys.path.insert(0, _DIR_RAIZ)

from core.lector_dxf import LectorDXF, obtener_limites_dxf
from core.generador_trayectorias import transformar_y_escalar_dxf
from core.GCodeParser import GCodeParser, TrajectoryBlock
from core.PathOptimizer import PathOptimizer
from core.GalvoSignalGenerator import GalvoSignalGenerator
from core.NIDaqController import NIDaqController, probe_feedback_hardware
from database.recetas import GestorRecetas
from database.trazabilidad import GestorTrazabilidad
from interfaz.i18n import tr


def cargar_perfil_hardware() -> Dict[str, Any]:
    """Carga el perfil cinematico y geometrico del Thorlabs GVS112/M."""
    try:
        from hardware.config_galvo import (
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
        }
    except Exception as e:
        print(f"[HAL] Error cargando config_galvo: {e}")
        return {
            "clave": "thorlabs_galvo",
            "nombre": "Thorlabs Galvo Scanner (GVS112/M)",
            "x_min": -50.0, "x_max": 50.0,
            "y_min": -50.0, "y_max": 50.0,
            "centro_x": 0.0, "centro_y": 0.0,
            "ancho_base_cm": 10.0, "alto_base_cm": 10.0,
            "marco_ancho_cm": 10.0, "marco_alto_cm": 10.0,
            "escala_dibujo": 0.90, "rotar_90_grados": False,
            "velocidad_trazado": 500.0, "velocidad_viaje": 2000.0,
        }


HARDWARE_CONFIG = {
    "thorlabs_galvo": cargar_perfil_hardware()
}


# =============================================================================
# PRESETS DE MODO DE PROCESO (Cutting, Welding, Marking)
# =============================================================================
PRESETS_MODO_PROCESO: Dict[str, Dict[str, Any]] = {
    "Cutting": {
        "modo_proceso": "Cutting",
        "velocidad_trazado": 2.0,        # Slow cutting speed (mm/s)
        "velocidad_viaje": 5.0,          # Safe repositioning (mm/s)
        "num_pasadas": 2,                # Multi-pass for deep through-cut
        "cooling_delay_s": 2.0,          # Inter-pass thermal cooling dwell (s)
        "duracion_min_segmento_ms": 50,  # High time density per segment (ms)
        "duracion_min_viaje_ms": 200,    # Safe galvo travel settling (ms)
        "laser_on_delay_ms": 25,         # Pierce / lead-in delay (ms)
        "laser_off_delay_ms": 15,        # Trailing cut completion delay (ms)
        "mark_delay_ms": 20,             # Corner deceleration dwell (ms)
        "jump_delay_ms": 80,             # Galvo jump settling dwell (ms)
        "tolerancia_rdp": 0.0,           # 0.0 = zero geometric distortion
        "tolerancia_union": 0.05,        # Tight contour chaining (mm)
    },
    "Welding": {
        "modo_proceso": "Welding",
        "velocidad_trazado": 15.0,       # Moderate speed for uniform thermal melt (mm/s)
        "velocidad_viaje": 40.0,         # Rapid repositioning (mm/s)
        "num_pasadas": 1,                # Single continuous pass
        "cooling_delay_s": 0.0,          # Continuous operation
        "duracion_min_segmento_ms": 20,  # Moderate segment density (ms)
        "duracion_min_viaje_ms": 100,    # Quick repositioning dwell (ms)
        "laser_on_delay_ms": 10,         # Fast pool initiation (ms)
        "laser_off_delay_ms": 5,         # Crater fill delay (ms)
        "mark_delay_ms": 10,             # Moderate galvo settling (ms)
        "jump_delay_ms": 50,             # Standard galvo settling (ms)
        "tolerancia_rdp": 0.002,         # Fine smoothing (mm)
        "tolerancia_union": 0.08,        # Seam chaining tolerance (mm)
    },
    "Marking": {
        "modo_proceso": "Marking",
        "velocidad_trazado": 150.0,      # Fast surface engraving feed (mm/s)
        "velocidad_viaje": 500.0,        # High-speed galvo jump (mm/s)
        "num_pasadas": 1,                # Single fast pass
        "cooling_delay_s": 0.0,          # No cooling delay needed
        "duracion_min_segmento_ms": 2,   # Minimal segment delay for high throughput (ms)
        "duracion_min_viaje_ms": 10,     # Agile repositioning (ms)
        "laser_on_delay_ms": 1,          # Minimal optical latency (ms)
        "laser_off_delay_ms": 1,         # Minimal optical tail (ms)
        "mark_delay_ms": 0,              # Direct vector transitions (ms)
        "jump_delay_ms": 10,             # Fast galvo settling (ms)
        "tolerancia_rdp": 0.005,         # Node reduction for maximum speed
        "tolerancia_union": 0.08,        # Standard contour chaining (mm)
    }
}


def obtener_preset_modo(modo: str) -> Dict[str, Any]:
    """Return recommended process parameters dictionary for Cutting, Welding, or Marking.

    Args:
        modo: 'Cutting', 'Welding', or 'Marking' (case-insensitive).

    Returns:
        Dict with recommended kinematic, timing, and multi-pass settings.
    """
    if not modo:
        return dict(PRESETS_MODO_PROCESO["Marking"])
    m_clean = str(modo).strip().lower()
    for name, preset in PRESETS_MODO_PROCESO.items():
        if name.lower() == m_clean:
            return dict(preset)
    return dict(PRESETS_MODO_PROCESO["Marking"])


class PuenteLaser:
    """Puente integral entre la interfaz de usuario y el motor backend."""

    HAL_ACTUAL = "thorlabs_galvo"

    def __init__(self):
        self.gestor_recetas = GestorRecetas()
        self.gestor_trazabilidad = GestorTrazabilidad()

        self.controlador_hardware: Optional[Any] = None
        self.es_simulacion = True
        self._hw_lock = threading.Lock()

        # Perfil cinematico Thorlabs
        self.hal_actual = self.HAL_ACTUAL
        cfg = HARDWARE_CONFIG["thorlabs_galvo"]
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
        self.escala_voltaje_v_mm = 0.200  # Thorlabs GVS112/M: +/-10V for +/-50mm (0.200 V/mm)

        # Archivo DXF y geometrias
        self.ruta_dxf_actual: Optional[str] = None
        self.nombre_dxf_actual: Optional[str] = None
        self.trazos_originales: List[List[Tuple[float, float]]] = []
        self.trazos_calibrados: List[List[Tuple[float, float]]] = []
        self.trazos_fisicos_cm: List[List[Tuple[float, float]]] = []
        self.bloques_gcode_crudos: List[TrajectoryBlock] = []
        self.bloques_gcode_optimizados: List[TrajectoryBlock] = []
        self.daq_controller: Optional[NIDaqController] = None

        # Control de ejecucion
        self._hilo_ejecucion: Optional[threading.Thread] = None
        self._evento_pausa = threading.Event()
        self._evento_pausa.set()
        self._evento_detener = threading.Event()
        self._en_ejecucion = False
        self._esta_pausado = False

        # Hardware Feedback Tracking (opcional; OFF por defecto)
        self.feedback_habilitado = False
        self.on_feedback_cb: Optional[Callable] = None  # callback(lista_de_puntos_xy_mm)
        self.ultimo_tracking_rms_um: Optional[float] = None
        self.ultimo_tracking_max_um: Optional[float] = None

        # Iniciar hardware o simulador automaticamente
        self._inicializar_hardware()

    def _inicializar_hardware(self):
        """Intenta inicializar el hardware Thorlabs. Si esta en modo simulacion o falla, activa simulador."""
        try:
            from hardware.config_galvo import TIPO_INTERFAZ_DAC
            if TIPO_INTERFAZ_DAC == "SIMULACION":
                self._activar_simulador()
                return

            from hardware.controlador_thorlabs import ControladorThorlabsGVS
            hw = ControladorThorlabsGVS(tipo_interfaz=TIPO_INTERFAZ_DAC)
            self.controlador_hardware = hw
            self.es_simulacion = False
            print("[PuenteLaser] Thorlabs GVS112/M physical hardware detected and ready.")
        except Exception as e:
            print(f"[PuenteLaser] Hardware fisico no disponible ({e}). Activando simulador.")
            self._activar_simulador()

    def _activar_simulador(self):
        """Instancia el simulador Thorlabs como fallback."""
        try:
            from hardware.simulador_thorlabs import SimuladorThorlabsGVS
            self.controlador_hardware = SimuladorThorlabsGVS()
            self.es_simulacion = True
            print("[PuenteLaser] SIMULATION mode active - physical hardware not connected.")
        except Exception as e:
            print(f"[PuenteLaser] Error activating simulator: {e}")
            self.controlador_hardware = None
            self.es_simulacion = True

    def detectar_hardware(self) -> bool:
        """Intenta inicializar o detectar el hardware Thorlabs GVS112/M fisico."""
        self._inicializar_hardware()
        return self.esta_conectado_fisico()

    def set_dimensiones_base(self, ancho_cm: float, alto_cm: float):
        """Define las dimensiones fisicas de la base y recalcula el centro."""
        self.ancho_base_cm = float(ancho_cm)
        self.alto_base_cm = float(alto_cm)
        self.centro_cm_x = round(self.ancho_base_cm / 2.0, 2)
        self.centro_cm_y = round(self.alto_base_cm / 2.0, 2)
        self.centro_x = HARDWARE_CONFIG["thorlabs_galvo"]["centro_x"]
        self.centro_y = HARDWARE_CONFIG["thorlabs_galvo"]["centro_y"]
        print(f"[PuenteLaser] Dimensiones base: {self.ancho_base_cm:.1f} x {self.alto_base_cm:.1f} cm")

    def set_centro_cm(self, x_cm: float, y_cm: float):
        """Define el centro en centimetros (ajuste manual del usuario)."""
        self.centro_cm_x = float(x_cm)
        self.centro_cm_y = float(y_cm)

        cfg = HARDWARE_CONFIG["thorlabs_galvo"]
        cal_ancho = cfg.get("marco_ancho_cm", 10.0)
        cal_alto = cfg.get("marco_alto_cm", 10.0)
        rango_x = self.x_max_limit - self.x_min_limit
        rango_y = self.y_max_limit - self.y_min_limit
        kx = cal_ancho / rango_x if rango_x > 0 else 1.0
        ky = cal_alto / rango_y if rango_y > 0 else 1.0

        dx_cm = self.centro_cm_x - (self.ancho_base_cm / 2.0)
        dy_cm = self.centro_cm_y - (self.alto_base_cm / 2.0)

        hw_cx = cfg["centro_x"]
        hw_cy = cfg["centro_y"]
        self.centro_x = round(hw_cx + (dx_cm / kx), 3)
        self.centro_y = round(hw_cy + (dy_cm / ky), 3)

        self.centro_x = max(self.x_min_limit, min(self.x_max_limit, self.centro_x))
        self.centro_y = max(self.y_min_limit, min(self.y_max_limit, self.centro_y))
        print(f"[PuenteLaser] Centro manual: ({self.centro_cm_x:.2f}, {self.centro_cm_y:.2f}) cm -> HW: ({self.centro_x:.2f}, {self.centro_y:.2f})")

    # =========================================================================
    # GESTION DE BASE DE DATOS (RECETAS)
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
            nom = r.get("nombre", "").lower()
            if "acrylic" in nom or "acrilico" in nom or "standard" in nom or "estandar" in nom:
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

    def obtener_preset_modo(self, modo: str) -> Dict[str, Any]:
        """
        Returns recommended process parameters for Cutting, Welding, or Marking.
        """
        return obtener_preset_modo(modo)

    # =========================================================================
    # ESTADO DEL HARDWARE
    # =========================================================================
    def esta_conectado_fisico(self) -> bool:
        """Informa si hay hardware real listo (no simulacion)."""
        return not self.es_simulacion and self.controlador_hardware is not None

    def feedback_soportado(self) -> Tuple[bool, str]:
        """Informa si el Hardware Feedback Tracking puede activarse.

        Returns:
            (disponible, clave) con clave in {"ok", "simulation", "no_driver", "no_device"}.
            Nunca lanza excepciones.
        """
        try:
            if self.es_simulacion or self.controlador_hardware is None:
                return False, "simulation"
            return probe_feedback_hardware()
        except Exception:
            return False, "no_device"

    def set_feedback(self, habilitar: bool) -> bool:
        """Activa/desactiva el feedback. Solo se activa si no es simulacion. Devuelve el estado final."""
        if habilitar and self.es_simulacion:
            self.feedback_habilitado = False
        else:
            self.feedback_habilitado = bool(habilitar)
        return self.feedback_habilitado

    def obtener_nombre_hardware(self) -> str:
        if self.es_simulacion:
            return "Thorlabs GVS112/M (Simulation)"
        return HARDWARE_CONFIG["thorlabs_galvo"].get("nombre", "Thorlabs GVS112/M")

    def apagar_laser(self):
        """Apaga el laser de forma segura."""
        if self.controlador_hardware:
            try:
                if hasattr(self.controlador_hardware, "apagar_laser"):
                    self.controlador_hardware.apagar_laser()
            except Exception as e:
                print(f"[PuenteLaser] Error apagando laser: {e}")

    def centrar_galvos(self):
        """Posiciona los espejos galvanometricos en reposo Home (0.0 V, 0.0 V) de forma segura."""
        if self.controlador_hardware:
            try:
                if hasattr(self.controlador_hardware, "ir_a_posicion"):
                    self.controlador_hardware.ir_a_posicion(0.0, 0.0)
                elif hasattr(self.controlador_hardware, "enviar_voltajes"):
                    self.controlador_hardware.enviar_voltajes(0.0, 0.0, laser_on=False)
            except Exception as e:
                print(f"[PuenteLaser] Error centrando galvos: {e}")

    # =========================================================================
    # TRANSFORMACION DE COORDENADAS DE HARDWARE
    # =========================================================================
    def transformar_coordenada_hardware(
        self,
        x: float,
        y: float,
        invert_x: bool = False,
        invert_y: bool = False,
        swap_xy: bool = False
    ) -> Tuple[float, float]:
        """
        Transforms a physical coordinate (x, y) with axis swapping,
        workspace center reflections, and hardware saturation clamping.

        Order of operations:
          1. Swap axes: (x, y) -> (y, x)
          2. Reflect X across center of workspace (self.centro_x)
          3. Reflect Y across center of workspace (self.centro_y)
          4. Hardware saturation limits: clamp to [x_min, x_max] and [y_min, y_max]
        """
        if swap_xy:
            x, y = y, x

        if invert_x:
            x = 2.0 * float(self.centro_x) - x

        if invert_y:
            y = 2.0 * float(self.centro_y) - y

        x = max(float(self.x_min_limit), min(float(self.x_max_limit), x))
        y = max(float(self.y_min_limit), min(float(self.y_max_limit), y))

        return (round(x, 4), round(y, 4))

    def aplicar_transformacion_hardware(
        self,
        trazos: List[List[Tuple[float, float]]],
        invert_x: bool = False,
        invert_y: bool = False,
        swap_xy: bool = False
    ) -> List[List[Tuple[float, float]]]:
        """
        Applies coordinate inversion, permutation, and physical clamping to a set of paths.
        """
        if not (invert_x or invert_y or swap_xy):
            return trazos

        trazos_tf: List[List[Tuple[float, float]]] = []
        for ruta in trazos:
            ruta_tf = [
                self.transformar_coordenada_hardware(
                    float(pt[0]), float(pt[1]),
                    invert_x=invert_x,
                    invert_y=invert_y,
                    swap_xy=swap_xy
                )
                for pt in ruta
            ]
            trazos_tf.append(ruta_tf)
        return trazos_tf

    # =========================================================================
    # PROCESAMIENTO DE ARCHIVOS DXF
    # =========================================================================
    def listar_archivos_dxf(self) -> List[str]:
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

    def _generar_gcode_desde_dxf(self, fuente_dxf_o_trazos: Any, ruta_gcode: str):
        """Generates standard ISO 6983 G-code from DXF vector contours or pre-extracted paths."""
        if isinstance(fuente_dxf_o_trazos, list):
            trazos = fuente_dxf_o_trazos
        else:
            lector = LectorDXF(fuente_dxf_o_trazos)
            trazos = lector.extraer_coordenadas()

        lines = [
            "%",
            "(Generated by CADConverter via FreeCAD / UFE Laser)",
            "G21",  # Millimetres
            "G90",  # Absolute positioning
            "G17",  # XY plane
        ]
        for ruta in trazos:
            if not ruta:
                continue
            lines.append("M5")
            lines.append(f"G0 X{ruta[0][0]:.4f} Y{ruta[0][1]:.4f} F100.0")
            lines.append("M3")
            for pt in ruta[1:]:
                lines.append(f"G1 X{pt[0]:.4f} Y{pt[1]:.4f} F20.0")
        lines.append("M5")
        lines.append("M2")
        lines.append("%")
        with open(ruta_gcode, "w", encoding="ascii", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")

    def cargar_dxf(self, ruta_archivo: str, params_receta: Dict) -> Dict:
        """
        Loads DXF with 100% entity preservation via high-performance LectorDXF (ezdxf),
        generates standard ISO 6983 G-code, parses blocks, and optimizes trajectories.
        """
        if not os.path.exists(ruta_archivo):
            raise FileNotFoundError(f"File not found: {ruta_archivo}")

        self.ruta_dxf_actual = ruta_archivo
        self.nombre_dxf_actual = os.path.basename(ruta_archivo)

        # 1. Extracción vectorial de alta fidelidad con LectorDXF (ezdxf)
        # Garantiza el 100% de las entidades (sin caídas de CDxfRead ni pérdida de figuras internas)
        lector = LectorDXF(ruta_archivo)
        trazos_dxf = lector.extraer_coordenadas()
        if not trazos_dxf:
            raise ValueError(f"No vector entities found in {self.nombre_dxf_actual}")
        self.trazos_originales = trazos_dxf

        # 2. Ruta de salida G-code (.gcode en el mismo directorio)
        base_name, _ = os.path.splitext(ruta_archivo)
        output_gcode_path = base_name + ".gcode"

        # 3. Generación directa de G-code ISO 6983 a partir de TODOS los trazos vectoriales (<0.02s)
        self._generar_gcode_desde_dxf(trazos_dxf, output_gcode_path)

        # 4. Parseo con GCodeParser
        v_trazado = float(params_receta.get("velocidad_trazado", 2.0))
        v_viaje = float(params_receta.get("velocidad_viaje", 3.5))
        parser = GCodeParser(output_gcode_path, default_feed_mm_s=v_trazado, rapid_speed_mm_s=v_viaje)
        self.bloques_gcode_crudos = parser.parse()

        # 5. Optimización de trayectorias con PathOptimizer
        tol_rdp = float(params_receta.get("tolerancia_rdp", 0.0))
        tol_union = float(params_receta.get("tolerancia_union", 0.08))
        optimizer = PathOptimizer(
            epsilon=tol_rdp,
            rapid_speed_mm_s=v_viaje,
            connection_tolerance=tol_union
        )
        self.bloques_gcode_optimizados = optimizer.optimize(self.bloques_gcode_crudos)

        return self.recalcular_trayectorias(params_receta)

    def recalcular_trayectorias(self, params_receta: Dict) -> Dict:
        """Aplica escala, rotación y optimización espacial preservando todas las figuras geométricas."""
        if not self.trazos_originales:
            return {}

        tol_rdp = float(params_receta.get("tolerancia_rdp", 0.0))
        tol_union = float(params_receta.get("tolerancia_union", 0.08))
        v_viaje = float(params_receta.get("velocidad_viaje", 3.5))

        # Reoptimizar bloques G-code si existen
        if hasattr(self, "bloques_gcode_crudos") and self.bloques_gcode_crudos:
            optimizer = PathOptimizer(
                epsilon=tol_rdp,
                rapid_speed_mm_s=v_viaje,
                connection_tolerance=tol_union
            )
            self.bloques_gcode_optimizados = optimizer.optimize(self.bloques_gcode_crudos)

        escala = float(params_receta.get("escala_dibujo", 0.90))
        rotar_90 = bool(params_receta.get("rotar_90_grados", 0))
        rotacion_grados = params_receta.get("rotacion_grados", None)
        long_min = float(params_receta.get("longitud_min_trazo", 0.01))

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

        # Inversion y permutacion de coordenadas de hardware
        invert_x = bool(params_receta.get("invert_x", False))
        invert_y = bool(params_receta.get("invert_y", False))
        swap_xy = bool(params_receta.get("swap_xy", False))

        if invert_x or invert_y or swap_xy:
            self.trazos_calibrados = self.aplicar_transformacion_hardware(
                self.trazos_calibrados,
                invert_x=invert_x,
                invert_y=invert_y,
                swap_xy=swap_xy
            )

        # Generar trazos en cm para el Canvas
        self.trazos_fisicos_cm = []
        rango_x = self.x_max_limit - self.x_min_limit
        rango_y = self.y_max_limit - self.y_min_limit
        kx = cal_ancho / rango_x if rango_x > 0 else 1.0
        ky = cal_alto / rango_y if rango_y > 0 else 1.0

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
            "min_x": min_x, "max_x": max_x,
            "min_y": min_y, "max_y": max_y,
            "limites_hardware": {
                "x_min": self.x_min_limit, "x_max": self.x_max_limit,
                "y_min": self.y_min_limit, "y_max": self.y_max_limit
            }
        }

    # =========================================================================
    # MOTOR DE EJECUCION ASINCRONO
    # =========================================================================
    def iniciar_ejecucion(self,
                          params_receta: Dict,
                          on_progress: Callable,
                          on_log: Callable,
                          on_finished: Callable):
        """Lanza el proceso de trazado en un hilo independiente."""
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
        """Alterna entre pausa y reanudacion de forma no bloqueante."""
        if not self._en_ejecucion:
            return False

        if self._esta_pausado:
            self._esta_pausado = False
            self._evento_pausa.set()
            if hasattr(self.controlador_hardware, "encender_laser"):
                try:
                    self.controlador_hardware.encender_laser()
                except Exception:
                    pass
            return False
        else:
            self._esta_pausado = True
            self._evento_pausa.clear()
            self.apagar_laser()
            return True

    def pausar_por_seguridad(self):
        """Pausa inmediata preventiva."""
        if not self._en_ejecucion:
            return
        self._esta_pausado = True
        self._evento_pausa.clear()

    def detener_ejecucion(self):
        """Detiene la ejecucion activa inmediatamente con parada atomica E-STOP."""
        self._evento_detener.set()
        self._evento_pausa.set()
        if hasattr(self, "daq_controller") and self.daq_controller:
            try:
                self.daq_controller.stop_and_clear()
            except Exception as e:
                print(f"[PuenteLaser] Error al detener DAQ en E-STOP: {e}")
        if self.controlador_hardware:
            try:
                if hasattr(self.controlador_hardware, "abortar_inmediato"):
                    self.controlador_hardware.abortar_inmediato()
                else:
                    self.apagar_laser()
            except Exception as e:
                print(f"[PuenteLaser] Error al abortar hardware en E-STOP: {e}")
        self.apagar_laser()
        self.centrar_galvos()

    def ejecutar_enmarcado(
        self,
        params: Optional[Dict[str, Any]] = None,
        on_progress: Optional[Callable] = None,
        on_log: Optional[Callable] = None,
        on_finished: Optional[Callable] = None,
        asincrono: bool = True
    ) -> bool:
        """
        Executes a closed rectangular perimeter tracing (Framing routine) around
        the calibrated bounding box at rapid speed with LASER STRICTLY OFF.

        Args:
            params: Dictionary containing optional configuration:
                    - 'velocidad_viaje': rapid travel feed (default: 2000 mm/s)
                    - 'num_vueltas' / 'vueltas_framing': laps to execute (1 or 2, default: 1)
            on_progress: Optional GUI progress callback.
            on_log: Optional terminal logger callback.
            on_finished: Optional completion callback.
            asincrono: Whether to spawn a background daemon thread (default: True).

        Returns:
            bool: True if framing started successfully, False otherwise.
        """
        if self._en_ejecucion:
            if on_log:
                on_log(tr("log_framing_busy"))
            return False

        if not self.trazos_calibrados:
            msg = "[Framing] No calibrated trajectories available to frame."
            if on_log:
                on_log(msg)
            if on_finished:
                on_finished("ERROR", msg, 0.0)
            return False

        params_dict = params or {}
        v_viaje = float(params_dict.get("velocidad_viaje", 2000.0))
        num_vueltas = int(params_dict.get("num_vueltas", params_dict.get("vueltas_framing", 1)))
        num_vueltas = max(1, min(2, num_vueltas))

        # 1. Calculate Bounding Box of calibrated trajectories
        min_x, max_x, min_y, max_y = obtener_limites_dxf(self.trazos_calibrados)

        # 2. Build closed 4-corner perimeter
        c1 = (float(min_x), float(min_y))
        c2 = (float(max_x), float(min_y))
        c3 = (float(max_x), float(max_y))
        c4 = (float(min_x), float(max_y))
        esquinas = [c1, c2, c3, c4, c1]

        p_home = (float(self.centro_x), float(self.centro_y))

        # 3. Build G0 motion blocks with laser strictly OFF
        blocks: List[TrajectoryBlock] = []
        pos = p_home

        for lap in range(num_vueltas):
            for pt in esquinas:
                dist = math.hypot(pt[0] - pos[0], pt[1] - pos[1])
                if dist > 1e-9:
                    dur_s = max(0.010, dist / max(0.1, v_viaje))
                    blocks.append(TrajectoryBlock("G0", pos, pt, dist / dur_s))
                    pos = pt

        # Return to Home at the end
        dist_home = math.hypot(p_home[0] - pos[0], p_home[1] - pos[1])
        if dist_home > 1e-9:
            dur_s = max(0.010, dist_home / max(0.1, v_viaje))
            blocks.append(TrajectoryBlock("G0", pos, p_home, dist_home / dur_s))

        def _hilo_enmarcado():
            t_inicio = time.time()
            self._en_ejecucion = True
            self._evento_detener.clear()
            self._evento_pausa.set()
            estado = "COMPLETED"
            error_msg = ""

            # Ensure laser is strictly disabled
            self.apagar_laser()

            if on_log:
                s_suf = 's' if num_vueltas > 1 else ''
                on_log(tr("log_framing_routine_start", vueltas=num_vueltas, s=s_suf))
                on_log(tr("log_framing_bbox", min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y))
                on_log(tr("log_framing_speed", speed=v_viaje))

            try:
                fs = 5000.0
                generador = GalvoSignalGenerator(
                    blocks,
                    sample_rate_hz=fs,
                    scale_factor_v_per_mm=self.escala_voltaje_v_mm,
                    voltage_limits=(-10.0, 10.0),
                    jump_delay_us=5000.0,
                    mark_delay_us=0.0,
                    laser_on_delay_us=0.0,
                    laser_off_delay_us=0.0
                )
                voltajes, compuerta = generador.generate_signals()
                # STRICT SAFETY: Laser gate is 0 for all samples
                compuerta.fill(0)

                try:
                    self.daq_controller = NIDaqController(simulate=self.es_simulacion)
                    self.daq_controller.setup_hardware(f_s=fs)
                    self.daq_controller.write_buffers(voltajes, compuerta)
                    self.daq_controller.start_emission()
                except Exception as daq_e:
                    if on_log:
                        on_log(f"[Framing DAQ Notice] {daq_e}")

                # Telemetry loop for visual framing tracking
                n_samples = voltajes.shape[1]
                t0 = time.time()
                while True:
                    if self._evento_detener.is_set():
                        estado = "ABORTED"
                        break

                    # Pausa durante enmarcado: congelar la línea de tiempo sin perder posición
                    if not self._evento_pausa.is_set():
                        t_pausa = time.time()
                        while not self._evento_pausa.is_set():
                            if self._evento_detener.is_set():
                                break
                            time.sleep(0.05)
                        t0 += time.time() - t_pausa
                        continue

                    k = min(n_samples - 1, int((time.time() - t0) * fs))
                    vx = float(voltajes[0, k])
                    vy = float(voltajes[1, k])
                    pct = min(100.0, (k / float(max(1, n_samples - 1))) * 100.0)

                    if on_progress:
                        on_progress(
                            0, 1,
                            k, n_samples,
                            vx / self.escala_voltaje_v_mm, vy / self.escala_voltaje_v_mm,
                            round(pct, 1), round(pct, 1),
                            False,  # laser strictly OFF
                            vx, vy
                        )

                    if k >= n_samples - 1:
                        break
                    time.sleep(0.025)

                if self._evento_detener.is_set():
                    if on_log:
                        on_log(tr("log_framing_stopped_op"))
                else:
                    if on_log:
                        on_log(tr("log_framing_ok"))

            except Exception as e:
                estado = "ERROR"
                error_msg = str(e)
                if on_log:
                    on_log(f"[Framing ERROR] {e}")
            finally:
                self.apagar_laser()
                if hasattr(self, "daq_controller") and self.daq_controller:
                    try:
                        self.daq_controller.stop_and_clear()
                    except Exception:
                        pass
                self._en_ejecucion = False
                dur_s = round(time.time() - t_inicio, 2)
                if on_finished:
                    on_finished(estado, error_msg, dur_s)

        if asincrono:
            self._hilo_ejecucion = threading.Thread(target=_hilo_enmarcado, daemon=True)
            self._hilo_ejecucion.start()
            return True
        else:
            _hilo_enmarcado()
            return True

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
        Motor de ejecucion cinematica con telemetria de alta fidelidad.

        Construye una secuencia determinista de waypoints y:
          - Lanza un hilo de transmision al hardware (o simulador)
          - Ejecuta el bucle de telemetria visual a ~35 fps
          - Garantiza parada instantanea no bloqueante
        """
        t_inicio = time.time()
        estado = "COMPLETED"
        error_msg = ""

        trazos = self.trazos_calibrados
        if not trazos:
            if self.ruta_dxf_actual and os.path.exists(self.ruta_dxf_actual):
                on_log(tr("log_exec_processing"))
                self.cargar_dxf(self.ruta_dxf_actual, params)
                trazos = self.trazos_calibrados
        if not trazos:
            self._en_ejecucion = False
            on_finished("ERROR", "No calculated paths to execute", 0)
            return

        v_trazado = float(params.get("velocidad_trazado", 500.0))
        v_viaje = float(params.get("velocidad_viaje", 2000.0))
        dur_min_seg = int(params.get("duracion_min_segmento_ms", 10))
        dur_min_viaje = int(params.get("duracion_min_viaje_ms", 50))
        jump_delay_ms = float(params.get("jump_delay_ms", 0))
        mark_delay_ms = float(params.get("mark_delay_ms", 0))
        laser_on_delay_ms = float(params.get("laser_on_delay_ms", 0))
        laser_off_delay_ms = float(params.get("laser_off_delay_ms", 0))

        num_pasadas = max(1, int(params.get("num_pasadas", 1)))
        cooling_delay_s = max(0.0, float(params.get("cooling_delay_s", 0.0)))
        modo_proceso = str(params.get("modo_proceso", "Cutting"))

        total_trazos = len(trazos)
        total_puntos = sum(len(t) for t in trazos)

        hw_mode = 'PHYSICAL HARDWARE' if not self.es_simulacion else 'VIRTUAL SIMULATION'
        on_log(tr("log_trace_start", mode=modo_proceso, passes=num_pasadas, file=self.nombre_dxf_actual))
        on_log(tr("log_trace_header", file=self.nombre_dxf_actual))
        on_log(tr("log_trace_hw", hw=self.obtener_nombre_hardware(), mode=hw_mode))
        on_log(tr("log_trace_paths", paths=total_trazos, waypoints=total_puntos, passes=num_pasadas))
        on_log(tr("log_trace_speeds", mark=v_trazado, jump=v_viaje))
        on_log(tr("log_trace_delays", jump=jump_delay_ms, mark=mark_delay_ms, on=laser_on_delay_ms, off=laser_off_delay_ms, cooling=cooling_delay_s))

        fb: Dict[str, Any] = {"on": False, "idx": 0, "sumsq": 0.0, "max": 0.0, "n": 0}
        self.ultimo_tracking_rms_um = None
        self.ultimo_tracking_max_um = None

        try:
            # ---------------------------------------------------------------
            # 1. Build the G0/G1 block sequence with real kinematic durations
            #    (speed + minimum durations from the recipe).
            # ---------------------------------------------------------------
            blocks: List[TrajectoryBlock] = []
            meta: List[Tuple[int, int, int, int]] = []  # (trace, point, points_in_trace, is_mark)
            pos: Tuple[float, float] = (float(self.centro_x), float(self.centro_y))
            t_nominal = 0.0
            n_jumps = 0
            n_contours = 0

            for idx_t, ruta in enumerate(trazos):
                if not ruta:
                    continue
                destino = (float(ruta[0][0]), float(ruta[0][1]))
                dist = math.hypot(destino[0] - pos[0], destino[1] - pos[1])
                if dist > 1e-9:
                    dur_s = max(dur_min_viaje / 1000.0, dist / max(0.1, v_viaje))
                    blocks.append(TrajectoryBlock("G0", pos, destino, dist / dur_s))
                    meta.append((idx_t, 0, len(ruta), 0))
                    t_nominal += dur_s
                    n_jumps += 1
                pos = destino
                n_contours += 1

                for i_pt in range(1, len(ruta)):
                    pt = (float(ruta[i_pt][0]), float(ruta[i_pt][1]))
                    dist = math.hypot(pt[0] - pos[0], pt[1] - pos[1])
                    if dist <= 1e-9:
                        continue
                    dur_s = max(dur_min_seg / 1000.0, dist / max(0.1, v_trazado))
                    blocks.append(TrajectoryBlock("G1", pos, pt, dist / dur_s))
                    meta.append((idx_t, i_pt, len(ruta), 1))
                    t_nominal += dur_s
                    pos = pt

            if not blocks:
                raise ValueError("Calculated paths contain no movable segments.")

            # ---------------------------------------------------------------
            # 2. Signal timeline: GalvoSignalGenerator applies jump / mark /
            #    laser ON / laser OFF delays sample by sample.
            # ---------------------------------------------------------------
            t_total_est = t_nominal + (n_jumps * jump_delay_ms + n_contours * mark_delay_ms) / 1000.0
            fs = min(20000.0, max(1000.0, 1.5e6 / max(t_total_est, 1e-3)))
            escala_v = self.escala_voltaje_v_mm

            generador = GalvoSignalGenerator(
                blocks,
                sample_rate_hz=fs,
                scale_factor_v_per_mm=escala_v,
                voltage_limits=(-10.0, 10.0),
                jump_delay_us=jump_delay_ms * 1000.0,
                mark_delay_us=mark_delay_ms * 1000.0,
                laser_on_delay_us=laser_on_delay_ms * 1000.0,
                laser_off_delay_us=laser_off_delay_ms * 1000.0,
            )
            voltajes, compuerta = generador.generate_signals()
            n_muestras = int(voltajes.shape[1])
            k_ultimo = n_muestras - 1
            on_log(f"Signal timeline: {n_muestras} samples @ {fs:.0f} Hz "
                   f"-> {n_muestras / fs:.2f} s per pass (physical delays included)")

            def _drenar_feedback(final: bool = False) -> None:
                """Lee muestras AI nuevas, acumula el error de seguimiento y emite puntos medidos."""
                if not fb["on"] or not self.daq_controller:
                    return
                intentos = 15 if final else 1
                for _ in range(intentos):
                    chunk = self.daq_controller.read_feedback()
                    if chunk is None:
                        if not self.daq_controller.feedback_active:
                            fb["on"] = False
                            on_log("[Feedback] Hardware feedback became unavailable; continuing without it.")
                            return
                        if final and fb["idx"] < n_muestras:
                            time.sleep(0.02)
                            continue
                        return
                    i0 = fb["idx"]
                    i1 = min(i0 + int(chunk.shape[1]), n_muestras)
                    if i1 > i0:
                        meas = chunk[:, : i1 - i0]
                        cmd = voltajes[:, i0:i1]
                        err_mm = np.hypot(meas[0] - cmd[0], meas[1] - cmd[1]) / escala_v
                        fb["sumsq"] += float(np.sum(err_mm * err_mm))
                        fb["max"] = max(fb["max"], float(np.max(err_mm)))
                        fb["n"] += int(err_mm.size)
                        fb["idx"] = i1
                        if self.on_feedback_cb is not None:
                            paso = max(1, (i1 - i0) // 10)
                            sub = meas[:, ::paso] / escala_v
                            try:
                                self.on_feedback_cb(list(zip(sub[0].tolist(), sub[1].tolist())))
                            except Exception:
                                pass
                    if not final or fb["idx"] >= n_muestras:
                        return

            # Vectorized sample-to-block mapping matching GalvoSignalGenerator timing
            starts = np.array([b.start for b in blocks], dtype=np.float64)
            ends = np.array([b.end for b in blocks], dtype=np.float64)
            speeds = np.array([b.velocity for b in blocks], dtype=np.float64)
            is_mark = np.array([b.motion_type == "G1" for b in blocks], dtype=bool)

            distances = np.hypot(*(ends - starts).T)
            motion_samples = np.rint(distances / speeds * fs).astype(np.int64)
            motion_samples = np.where((distances > 0) & (motion_samples < 1), 1, motion_samples)
            n_jump = generador.n_jump
            n_mark = generador.n_mark
            joined_to_previous = np.zeros(len(blocks), dtype=bool)
            if len(blocks) > 1:
                gaps = np.hypot(*(starts[1:] - ends[:-1]).T)
                joined_to_previous[1:] = is_mark[1:] & is_mark[:-1] & (gaps <= 1e-6)
            joined_to_next = np.zeros(len(blocks), dtype=bool)
            joined_to_next[:-1] = joined_to_previous[1:]
            contour_end = is_mark & ~joined_to_next
            dwell_samples = np.where(is_mark, np.where(contour_end, n_mark, 0), n_jump).astype(np.int64)
            total_samples = motion_samples + dwell_samples
            block_index = np.repeat(np.arange(len(blocks)), total_samples)
            idx_bloque = np.concatenate(([0], block_index))
            offsets = np.concatenate(([1], 1 + np.cumsum(total_samples)[:-1]))
            cuentas = total_samples

            meta_arr = np.array(meta, dtype=np.int64)
            b_trazo, b_pt, b_total, b_mark = meta_arr.T

            # Time-weighted progress: cumulative count of marking samples.
            muestras_corte = b_mark[idx_bloque].astype(np.int64)
            muestras_corte[0] = 0  # prepended start sample is not marking
            acum_corte = np.cumsum(muestras_corte)
            total_corte = max(1, int(acum_corte[-1]))
            acum_antes = acum_corte[offsets - 1]
            acum_despues = acum_corte[offsets + cuentas - 1]
            tramo_por_trazo: Dict[int, List[int]] = {}
            for b in range(len(blocks)):
                if b_mark[b]:
                    t_id = int(b_trazo[b])
                    if t_id not in tramo_por_trazo:
                        tramo_por_trazo[t_id] = [int(acum_antes[b]), int(acum_despues[b])]
                    else:
                        tramo_por_trazo[t_id][1] = int(acum_despues[b])

            # ---------------------------------------------------------------
            # 3. Multi-pass execution loop
            # ---------------------------------------------------------------
            for pass_idx in range(1, num_pasadas + 1):
                if self._evento_detener.is_set():
                    estado = "STOPPED"
                    break

                on_log(tr("log_exec_pass", mode=modo_proceso, pass_idx=pass_idx, passes=num_pasadas))

                # Deterministic hardware/simulation output via NIDaqController for this pass
                try:
                    self.daq_controller = NIDaqController(simulate=self.es_simulacion)
                    self.daq_controller.setup_hardware(f_s=fs)
                    self.daq_controller.write_buffers(voltajes, compuerta)
                    fb["on"] = False
                    fb["idx"] = 0
                    if self.feedback_habilitado:
                        fb["on"] = bool(self.daq_controller.enable_feedback())
                        if fb["on"]:
                            on_log(f"[Feedback] Hardware feedback tracking active (pass {pass_idx}/{num_pasadas}).")
                        else:
                            on_log("[Feedback] Hardware feedback unavailable; running without it.")
                    self.daq_controller.start_emission()
                    on_log(f"[NIDaqController] Pass {pass_idx}/{num_pasadas}: Emission armed and running ({'SIMULATION' if self.es_simulacion else 'HARDWARE'}).")
                except Exception as daq_e:
                    fb["on"] = False
                    on_log(f"[NIDaqController Notice] {daq_e}")

                def _hilo_transmision_galvo():
                    try:
                        if hasattr(self.controlador_hardware, "trazar_trayectorias"):
                            self.controlador_hardware.trazar_trayectorias(
                                trazos,
                                velocidad_marcado=v_trazado,
                                velocidad_salto=v_viaje,
                                check_cancel=lambda: self._evento_detener.is_set()
                            )
                    except Exception as e:
                        on_log(f"[GVS] Galvo tracing driver notice: {e}")

                hilo_tx = threading.Thread(target=_hilo_transmision_galvo, daemon=True)
                hilo_tx.start()

                # Real-time telemetry replay (~35 fps) of the generated signals
                t0 = time.time()
                while True:
                    if self._evento_detener.is_set():
                        estado = "STOPPED"
                        break

                    # Pause: freeze the timeline (laser is already turned off)
                    if not self._evento_pausa.is_set():
                        t_pausa = time.time()
                        while not self._evento_pausa.is_set():
                            if self._evento_detener.is_set():
                                break
                            time.sleep(0.05)
                        t0 += time.time() - t_pausa
                        continue

                    _drenar_feedback()

                    k = min(k_ultimo, int((time.time() - t0) * fs))
                    bi = int(idx_bloque[k])
                    vx = float(voltajes[0, k])
                    vy = float(voltajes[1, k])
                    laser_activo = bool(compuerta[0, k])
                    t_id = int(b_trazo[bi])

                    acum = int(acum_corte[k])
                    tramo = tramo_por_trazo.get(t_id)
                    if tramo and tramo[1] > tramo[0]:
                        pct_trazo = (acum - tramo[0]) / float(tramo[1] - tramo[0]) * 100.0
                    else:
                        pct_trazo = 0.0

                    # Multi-pass global percentage
                    pct_pass_fraction = acum / float(total_corte)
                    pct_total = ((pass_idx - 1) + pct_pass_fraction) / float(num_pasadas) * 100.0

                    on_progress(
                        t_id, total_trazos,
                        int(b_pt[bi]), int(b_total[bi]),
                        vx / escala_v, vy / escala_v,
                        round(min(100.0, max(0.0, pct_trazo)), 1),
                        round(min(100.0, max(0.0, pct_total)), 1),
                        laser_activo,
                        vx, vy
                    )

                    if k >= k_ultimo:
                        break
                    time.sleep(0.028)

                # Wait for hardware transmission thread for this pass
                if hilo_tx and hilo_tx.is_alive():
                    timeout_join = 0.5 if self._evento_detener.is_set() else 120.0
                    hilo_tx.join(timeout=timeout_join)

                # Drain remaining feedback samples before the DAQ is released
                if fb["on"] and not self._evento_detener.is_set():
                    _drenar_feedback(final=True)

                # Turn off laser and clean up DAQ for this pass
                self.apagar_laser()
                if hasattr(self, "daq_controller") and self.daq_controller:
                    try:
                        self.daq_controller.stop_and_clear()
                    except Exception:
                        pass

                if self._evento_detener.is_set():
                    estado = "STOPPED"
                    break

                # Inter-pass thermal cooling delay (with laser strictly off)
                if pass_idx < num_pasadas and cooling_delay_s > 0:
                    self.apagar_laser()
                    on_log(f"[Cooling] Pass {pass_idx}/{num_pasadas} completed. "
                           f"Laser strictly OFF (0 LOW). Thermal cooling delay: {cooling_delay_s:.1f}s...")
                    t_cool_start = time.time()
                    while (time.time() - t_cool_start) < cooling_delay_s:
                        if self._evento_detener.is_set():
                            estado = "STOPPED"
                            break
                        while not self._evento_pausa.is_set():
                            if self._evento_detener.is_set():
                                break
                            time.sleep(0.05)
                        time.sleep(0.05)

                    if self._evento_detener.is_set():
                        estado = "STOPPED"
                        break

            # ---------------------------------------------------------------
            # 4. Shutdown and final log
            # ---------------------------------------------------------------
            if self._evento_detener.is_set():
                estado = "ABORTED"
                on_log(tr("log_stop_executed"))
                self.apagar_laser()
                on_log(tr("log_stop_rest"))
            else:
                on_log(tr("log_work_completed"))

        except Exception as e:
            estado = "ERROR"
            error_msg = str(e)
            on_log(f"[ERROR] Exception during execution: {e}")
            self.apagar_laser()

        finally:
            # Fail-safe hardware guarantee: Laser gate LOW (0) and mirrors parked at (0.0 V, 0.0 V)
            self.apagar_laser()
            if hasattr(self, "daq_controller") and self.daq_controller:
                try:
                    self.daq_controller.stop_and_clear()
                except Exception as e_daq:
                    print(f"[PuenteLaser] DAQ cleanup notice in finally: {e_daq}")
            if hasattr(self, "controlador_hardware") and self.controlador_hardware:
                try:
                    if hasattr(self.controlador_hardware, "abortar_inmediato"):
                        self.controlador_hardware.abortar_inmediato()
                    elif hasattr(self.controlador_hardware, "apagar_laser"):
                        self.controlador_hardware.apagar_laser()
                except Exception as e_hw:
                    print(f"[PuenteLaser] Hardware cleanup notice in finally: {e_hw}")
            duracion_s = round(time.time() - t_inicio, 2)

            # Tracking error metrics (only when hardware feedback produced samples)
            trk_rms_um: Optional[float] = None
            trk_max_um: Optional[float] = None
            if fb["n"] > 0:
                trk_rms_um = round(math.sqrt(fb["sumsq"] / fb["n"]) * 1000.0, 1)
                trk_max_um = round(fb["max"] * 1000.0, 1)
                self.ultimo_tracking_rms_um = trk_rms_um
                self.ultimo_tracking_max_um = trk_max_um
                try:
                    on_log(f"[TELEMETRY] Tracking Error: RMS = {trk_rms_um:.1f} \u00b5m | Max = {trk_max_um:.1f} \u00b5m")
                except Exception:
                    pass
            self._en_ejecucion = False
            self._esta_pausado = False

            try:
                receta_id = params.get("_receta_id")
                receta_nom = params.get("_receta_nombre", "Manual")
                modo_proc = str(params.get("modo_proceso", "Cutting"))
                estado_db = "COMPLETADO" if estado in ("COMPLETED", "COMPLETADO") else ("ABORTADO" if estado in ("ABORTED", "STOPPED", "ABORTADO") else "FALLO_HARDWARE")
                self.gestor_trazabilidad.registrar_ciclo({
                    "operador": "Operator",
                    "archivo_dxf": self.nombre_dxf_actual or "Unknown",
                    "hardware_usado": self.hal_actual,
                    "receta_id": receta_id,
                    "receta_nombre": receta_nom,
                    "modo_proceso": modo_proc,
                    "velocidad_trazado": v_trazado,
                    "velocidad_viaje": v_viaje,
                    "num_pasadas": int(params.get("num_pasadas", 1)),
                    "escala_dibujo": float(params.get("escala_dibujo", 0.9)),
                    "tolerancia_rdp": float(params.get("tolerancia_rdp", 0.005)),
                    "tolerancia_union": float(params.get("tolerancia_union", 0.08)),
                    "trazos_totales": total_trazos,
                    "waypoints_totales": total_puntos,
                    "estado": estado_db,
                    "mensaje_error": error_msg,
                    "duracion_segundos": duracion_s,
                    "tracking_rms_um": trk_rms_um,
                    "tracking_max_um": trk_max_um
                })
                on_log(tr("log_db_recorded", status=estado_db, dur=duracion_s))
            except Exception as e_bd:
                on_log(f"[DB] Warning: Could not record traceability: {e_bd}")

            on_finished(estado, error_msg, duracion_s)
