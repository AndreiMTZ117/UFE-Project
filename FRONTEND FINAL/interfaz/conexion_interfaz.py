# -*- coding: utf-8 -*-
"""backend interface bridge between gui and core engine"""

import os
import sys
import glob
import time
import math
import threading
from typing import Callable, Optional, Dict, List, Tuple, Any

import numpy as np

#project imports
_DIR_RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _DIR_RAIZ not in sys.path:
    sys.path.insert(0, _DIR_RAIZ)

from core.lector_dxf import LectorDXF, obtener_limites_dxf
from core.generador_trayectorias import transform_and_scale_dxf
from core.GCodeParser import GCodeParser, TrajectoryBlock
from core.PathOptimizer import PathOptimizer
from core.GalvoSignalGenerator import GalvoSignalGenerator
from core.NIDaqController import NIDaqController, probe_feedback_hardware
from core.config_loader import ConfigError, get_daq_identity, get_volts_per_mm, load_hardware_config
from database.recetas import GestorRecetas
from database.trazabilidad import GestorTrazabilidad
from interfaz.i18n import tr

try:
    from scipy import signal as scipy_signal
except ImportError:
    scipy_signal = None


def calc_inertial_lag_ms(
    meas: np.ndarray,
    cmd: np.ndarray,
    sample_rate_hz: float,
    max_lag_ms: float = 50.0,
    min_lag_ms: float = -5.0,
) -> float:
    """calc physical inertial lag in ms using cross correlation"""
    if meas.ndim == 1:
        meas = meas.reshape(1, -1)
    if cmd.ndim == 1:
        cmd = cmd.reshape(1, -1)

    n = min(meas.shape[1], cmd.shape[1])
    if n < 10 or sample_rate_hz <= 0:
        return 0.0

    meas = meas[:, :n]
    cmd = cmd[:, :n]

    #downsample if signal is too long
    step = max(1, n // 100000)
    if step > 1:
        meas = meas[:, ::step]
        cmd = cmd[:, ::step]
        effective_fs = sample_rate_hz / step
        n = meas.shape[1]
    else:
        effective_fs = sample_rate_hz

    #remove dc component
    meas_0 = meas[0] - np.mean(meas[0])
    meas_1 = meas[1] - np.mean(meas[1])
    cmd_0 = cmd[0] - np.mean(cmd[0])
    cmd_1 = cmd[1] - np.mean(cmd[1])

    std_m = np.std(meas_0) + np.std(meas_1)
    std_c = np.std(cmd_0) + np.std(cmd_1)
    if std_m < 1e-6 or std_c < 1e-6:
        return 0.0

    if scipy_signal is not None:
        corr0 = scipy_signal.correlate(meas_0, cmd_0, mode="full", method="fft")
        corr1 = scipy_signal.correlate(meas_1, cmd_1, mode="full", method="fft")
        corr_total = corr0 + corr1
        lags = scipy_signal.correlation_lags(n, n)
    else:
        n_fft = 2 ** int(np.ceil(np.log2(2 * n - 1)))
        fft_c0 = np.fft.rfft(cmd_0, n_fft)
        fft_m0 = np.fft.rfft(meas_0, n_fft)
        corr0 = np.fft.irfft(fft_m0 * np.conj(fft_c0), n_fft)
        fft_c1 = np.fft.rfft(cmd_1, n_fft)
        fft_m1 = np.fft.rfft(meas_1, n_fft)
        corr1 = np.fft.irfft(fft_m1 * np.conj(fft_c1), n_fft)
        corr_total = np.concatenate([corr0[-(n - 1):], corr0[:n]]) + np.concatenate([corr1[-(n - 1):], corr1[:n]])
        lags = np.arange(-(n - 1), n)

    k_min = int(round((min_lag_ms / 1000.0) * effective_fs))
    k_max = int(round((max_lag_ms / 1000.0) * effective_fs))
    mask = (lags >= k_min) & (lags <= k_max)

    if not np.any(mask):
        best_lag_samples = lags[np.argmax(corr_total)]
    else:
        masked_lags = lags[mask]
        masked_corr = corr_total[mask]
        best_lag_samples = masked_lags[np.argmax(masked_corr)]

    lag_ms = (best_lag_samples / effective_fs) * 1000.0
    return float(round(lag_ms, 2))


def load_hardware_profile() -> Dict[str, Any]:
    """load kinematic and geometric profile for thorlabs galvo"""
    try:
        from hardware.config_galvo import (
            CAMPO_X_MIN_MM, CAMPO_X_MAX_MM,
            CAMPO_Y_MIN_MM, CAMPO_Y_MAX_MM,
            ESCALA_DIBUJO, ROTAR_90_GRADOS,
            VELOCIDAD_MARCADO_MM_S, VELOCIDAD_SALTO_MM_S
        )
        field_w_cm = round((CAMPO_X_MAX_MM - CAMPO_X_MIN_MM) / 10.0, 2)
        field_h_cm = round((CAMPO_Y_MAX_MM - CAMPO_Y_MIN_MM) / 10.0, 2)
        return {
            "clave": "thorlabs_galvo",
            "nombre": "Thorlabs Galvo Scanner (GVS112/M)",
            "x_min": CAMPO_X_MIN_MM,
            "x_max": CAMPO_X_MAX_MM,
            "y_min": CAMPO_Y_MIN_MM,
            "y_max": CAMPO_Y_MAX_MM,
            "centro_x": 0.0,
            "centro_y": 0.0,
            "ancho_base_cm": field_w_cm,
            "alto_base_cm": field_h_cm,
            "marco_ancho_cm": field_w_cm,
            "marco_alto_cm": field_h_cm,
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
    "thorlabs_galvo": load_hardware_profile()
}


#process mode presets
PRESETS_MODO_PROCESO: Dict[str, Dict[str, Any]] = {
    "Cutting": {
        "modo_proceso": "Cutting",
        "velocidad_trazado": 2.0,  #slow cut speed
        "velocidad_viaje": 5.0,  #safe move speed
        "num_pasadas": 2,  #multi pass
        "cooling_delay_s": 2.0,  #cooling between passes
        "duracion_min_segmento_ms": 50,  #min segment time
        "duracion_min_viaje_ms": 200,  #min travel time
        "laser_on_delay_ms": 25,  #pierce delay
        "laser_off_delay_ms": 15,  #trailing delay
        "mark_delay_ms": 20,  #corner dwell
        "jump_delay_ms": 80,  #jump settling
        "tolerancia_rdp": 0.0,  #no distortion
        "tolerancia_union": 0.05,  #tight chaining
    },
    "Welding": {
        "modo_proceso": "Welding",
        "velocidad_trazado": 15.0,  #slow cut speed
        "velocidad_viaje": 40.0,  #safe move speed
        "num_pasadas": 1,  #multi pass
        "cooling_delay_s": 0.0,  #cooling between passes
        "duracion_min_segmento_ms": 20,  #min segment time
        "duracion_min_viaje_ms": 100,  #min travel time
        "laser_on_delay_ms": 10,  #pierce delay
        "laser_off_delay_ms": 5,  #trailing delay
        "mark_delay_ms": 10,  #corner dwell
        "jump_delay_ms": 50,  #jump settling
        "tolerancia_rdp": 0.002,  #no distortion
        "tolerancia_union": 0.08,  #tight chaining
    },
    "Marking": {
        "modo_proceso": "Marking",
        "velocidad_trazado": 150.0,  #slow cut speed
        "velocidad_viaje": 500.0,  #safe move speed
        "num_pasadas": 1,  #multi pass
        "cooling_delay_s": 0.0,  #cooling between passes
        "duracion_min_segmento_ms": 2,  #min segment time
        "duracion_min_viaje_ms": 10,  #min travel time
        "laser_on_delay_ms": 1,  #pierce delay
        "laser_off_delay_ms": 1,  #trailing delay
        "mark_delay_ms": 0,  #corner dwell
        "jump_delay_ms": 10,  #jump settling
        "tolerancia_rdp": 0.005,  #no distortion
        "tolerancia_union": 0.08,  #tight chaining
    }
}


def get_mode_preset(modo: str) -> Dict[str, Any]:
    """get recommended process parameters for cutting welding or marking"""
    if not modo:
        return dict(PRESETS_MODO_PROCESO["Marking"])
    m_clean = str(modo).strip().lower()
    for name, preset in PRESETS_MODO_PROCESO.items():
        if name.lower() == m_clean:
            return dict(preset)
    return dict(PRESETS_MODO_PROCESO["Marking"])


class PuenteLaser:
    """bridge between user interface and backend engine"""

    HAL_ACTUAL = "thorlabs_galvo"

    def __init__(self):
        self.gestor_recetas = GestorRecetas()
        self.gestor_trazabilidad = GestorTrazabilidad()

        self.controlador_hardware: Optional[Any] = None
        self.es_simulacion = True
        self.motivo_simulacion = ""  #why simulation is active (shown after a hardware scan)
        self._hw_lock = threading.Lock()

        #thorlabs profile
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
        self.hardware_cfg = load_hardware_config()
        self.escala_voltaje_v_mm = get_volts_per_mm(self.hardware_cfg)

        #dxf and geometry
        self.ruta_dxf_actual: Optional[str] = None
        self.nombre_dxf_actual: Optional[str] = None
        self.trazos_originales: List[List[Tuple[float, float]]] = []
        self.trazos_calibrados: List[List[Tuple[float, float]]] = []
        self.trazos_fisicos_cm: List[List[Tuple[float, float]]] = []
        self.bloques_gcode_crudos: List[TrajectoryBlock] = []
        self.bloques_gcode_optimizados: List[TrajectoryBlock] = []
        self.daq_controller: Optional[NIDaqController] = None

        #execution control
        self._hilo_ejecucion: Optional[threading.Thread] = None
        self._evento_pausa = threading.Event()
        self._evento_pausa.set()
        self._evento_detener = threading.Event()
        self._en_ejecucion = False
        self._esta_pausado = False

        #feedback tracking, off by default
        self.feedback_habilitado = False
        self.on_feedback_cb: Optional[Callable] = None  #callback(xy points list)
        #callback(msg, critico) for hardware write failures; may be called from worker threads
        self.on_alerta_hw_cb: Optional[Callable[[str, bool], None]] = None
        self.ultimo_tracking_rms_um: Optional[float] = None
        self.ultimo_tracking_max_um: Optional[float] = None
        self.ultimo_tracking_lag_ms: Optional[float] = None

        #start hardware or simulator
        self._init_hardware()

    def _init_hardware(self):
        """probe physical hardware or switch to simulation"""
        try:
            from core.NIDaqController import probe_daq_hardware
            #the configured card must be present, not just any ni device in the chassis
            try:
                required = get_daq_identity(self.hardware_cfg)["device"]
            except ConfigError as e:
                self._enable_simulator(razon=str(e))
                return
            daq_probe = probe_daq_hardware(required_device=required)
            if daq_probe["available"]:
                from hardware.controlador_thorlabs import ControladorThorlabsGVS
                self.controlador_hardware = ControladorThorlabsGVS(tipo_interfaz="NI_DAQ")
                self.controlador_hardware.on_alerta = self._emitir_alerta_hw
                self.es_simulacion = False
                self.motivo_simulacion = ""
                print(f"[PuenteLaser] Thorlabs GVS112/M físico activo ({daq_probe['description']}).")
            else:
                self._enable_simulator(razon=daq_probe["description"])
        except Exception as e:
            self._enable_simulator(razon=str(e))

    def _emitir_alerta_hw(self, mensaje: str, critico: bool = False):
        """forward hardware failure from controller to the gui"""
        if self.on_alerta_hw_cb is not None:
            self.on_alerta_hw_cb(mensaje, critico)

    def _enable_simulator(self, razon: str = ""):
        """start virtual simulation environment"""
        self.motivo_simulacion = razon
        try:
            from hardware.simulador_thorlabs import SimuladorThorlabsGVS
            self.controlador_hardware = SimuladorThorlabsGVS()
            self.es_simulacion = True
            msg = f" ({razon})" if razon else ""
            print(f"[PuenteLaser] Modo SIMULACIÓN activo - Hardware físico no conectado{msg}.")
        except Exception as e:
            print(f"[PuenteLaser] Error activando simulador: {e}")
            self.controlador_hardware = None
            self.es_simulacion = True

    def detect_hardware(self) -> bool:
        """try initializing physical thorlabs hardware"""
        self._init_hardware()
        return self.is_physically_connected()

    def forzar_simulacion(self) -> bool:
        """switch to virtual simulation on purpose, even if the daq card is present"""
        if self.is_running:
            return False
        if not self.es_simulacion:
            self.laser_off()  #park the real laser line before dropping the controller
        self._enable_simulator(razon="selected manually")
        return True

    def set_base_dimensions(self, ancho_cm: float, alto_cm: float):
        """set physical base dimensions and recalculate center"""
        self.ancho_base_cm = float(ancho_cm)
        self.alto_base_cm = float(alto_cm)
        self.centro_cm_x = round(self.ancho_base_cm / 2.0, 2)
        self.centro_cm_y = round(self.alto_base_cm / 2.0, 2)
        self.centro_x = HARDWARE_CONFIG["thorlabs_galvo"]["centro_x"]
        self.centro_y = HARDWARE_CONFIG["thorlabs_galvo"]["centro_y"]
        print(f"[PuenteLaser] Dimensiones base: {self.ancho_base_cm:.1f} x {self.alto_base_cm:.1f} cm")

    def set_center_cm(self, x_cm: float, y_cm: float):
        """set center in cm for manual user adjustment"""
        self.centro_cm_x = float(x_cm)
        self.centro_cm_y = float(y_cm)

        cfg = HARDWARE_CONFIG["thorlabs_galvo"]
        cal_width = cfg.get("marco_ancho_cm", 10.0)
        cal_height = cfg.get("marco_alto_cm", 10.0)
        range_x = self.x_max_limit - self.x_min_limit
        range_y = self.y_max_limit - self.y_min_limit
        kx = cal_width / range_x if range_x > 0 else 1.0
        ky = cal_height / range_y if range_y > 0 else 1.0

        dx_cm = self.centro_cm_x - (self.ancho_base_cm / 2.0)
        dy_cm = self.centro_cm_y - (self.alto_base_cm / 2.0)

        hw_cx = cfg["centro_x"]
        hw_cy = cfg["centro_y"]
        self.centro_x = round(hw_cx + (dx_cm / kx), 3)
        self.centro_y = round(hw_cy + (dy_cm / ky), 3)

        self.centro_x = max(self.x_min_limit, min(self.x_max_limit, self.centro_x))
        self.centro_y = max(self.y_min_limit, min(self.y_max_limit, self.centro_y))
        print(f"[PuenteLaser] Centro manual: ({self.centro_cm_x:.2f}, {self.centro_cm_y:.2f}) cm -> HW: ({self.centro_x:.2f}, {self.centro_y:.2f})")

    #recipes db
    def get_recipes(self) -> List[Dict]:
        try:
            return self.gestor_recetas.listar_recetas()
        except Exception as e:
            print(f"[Conexion] Error al listar recetas: {e}")
            return []

    def get_recipe_by_id(self, receta_id: int) -> Dict:
        try:
            return self.gestor_recetas.obtener_receta(receta_id)
        except Exception as e:
            print(f"[Conexion] Error al obtener receta {receta_id}: {e}")
            return {}

    def get_default_recipe(self) -> Dict:
        recipes = self.get_recipes()
        for r in recipes:
            name = r.get("nombre", "").lower()
            if "acrylic" in name or "acrilico" in name or "standard" in name or "estandar" in name:
                return r
        return recipes[0] if recipes else {}

    def save_or_update_recipe(self, datos: Dict, receta_id: Optional[int] = None) -> int:
        if receta_id is not None:
            self.gestor_recetas.actualizar_receta(receta_id, datos)
            return receta_id
        else:
            return self.gestor_recetas.crear_receta(datos)

    def delete_recipe(self, receta_id: int) -> bool:
        try:
            return self.gestor_recetas.eliminar_receta(receta_id)
        except Exception as e:
            print(f"[Conexion] Error al eliminar receta {receta_id}: {e}")
            return False

    def get_mode_preset(self, modo: str) -> Dict[str, Any]:
        """get recommended process parameters for cutting welding or marking"""
        return get_mode_preset(modo)

    #hardware state
    def is_physically_connected(self) -> bool:
        """check if physical hardware is ready"""
        return not self.es_simulacion and self.controlador_hardware is not None

    def is_feedback_supported(self) -> Tuple[bool, str]:
        """check if hardware feedback tracking is available"""
        try:
            if self.es_simulacion or self.controlador_hardware is None:
                return False, "simulation"
            return probe_feedback_hardware()
        except Exception:
            return False, "no_device"

    def set_feedback(self, habilitar: bool) -> bool:
        """enable or disable feedback tracking"""
        if habilitar and self.es_simulacion:
            self.feedback_habilitado = False
        else:
            self.feedback_habilitado = bool(habilitar)
        return self.feedback_habilitado

    def get_hardware_name(self) -> str:
        if self.es_simulacion:
            return "Thorlabs GVS112/M (Simulation)"
        return HARDWARE_CONFIG["thorlabs_galvo"].get("nombre", "Thorlabs GVS112/M")

    def laser_off(self):
        """safely turn laser off"""
        if hasattr(self, "daq_controller") and self.daq_controller and not self.daq_controller.simulate:
            if getattr(self.daq_controller, "_do_task", None) is not None:
                return
        if self.controlador_hardware:
            try:
                if hasattr(self.controlador_hardware, "apagar_laser"):
                    self.controlador_hardware.apagar_laser()
            except Exception as e:
                print(f"[PuenteLaser] Error apagando laser: {e}")

    def center_galvos(self):
        """park mirrors at home position"""
        if hasattr(self, "daq_controller") and self.daq_controller and not self.daq_controller.simulate:
            if getattr(self.daq_controller, "_ao_task", None) is not None:
                return
            try:
                self.daq_controller._park_outputs()
                return
            except Exception:
                pass
        if self.controlador_hardware:
            try:
                if hasattr(self.controlador_hardware, "center"):
                    self.controlador_hardware.center()
                elif hasattr(self.controlador_hardware, "ir_a_posicion"):
                    self.controlador_hardware.ir_a_posicion(0.0, 0.0)
            except Exception as e:
                print(f"[PuenteLaser] Error centrando galvos: {e}")

    #hardware coordinate transform
    def transform_hardware_coordinate(
        self,
        x: float,
        y: float,
        invert_x: bool = False,
        invert_y: bool = False,
        swap_xy: bool = False
    ) -> Tuple[float, float]:
        """transform coordinate with axis swapping reflections and clamping"""
        if swap_xy:
            x, y = y, x

        if invert_x:
            x = 2.0 * float(self.centro_x) - x

        if invert_y:
            y = 2.0 * float(self.centro_y) - y

        x = max(float(self.x_min_limit), min(float(self.x_max_limit), x))
        y = max(float(self.y_min_limit), min(float(self.y_max_limit), y))

        return (round(x, 4), round(y, 4))

    def apply_hardware_transform(
        self,
        trazos: List[List[Tuple[float, float]]],
        invert_x: bool = False,
        invert_y: bool = False,
        swap_xy: bool = False
    ) -> List[List[Tuple[float, float]]]:
        """apply coordinate inversion and physical clamping to paths"""
        if not (invert_x or invert_y or swap_xy):
            return trazos

        paths_tf: List[List[Tuple[float, float]]] = []
        for route in trazos:
            route_tf = [
                self.transform_hardware_coordinate(
                    float(pt[0]), float(pt[1]),
                    invert_x=invert_x,
                    invert_y=invert_y,
                    swap_xy=swap_xy
                )
                for pt in route
            ]
            paths_tf.append(route_tf)
        return paths_tf

    #dxf files
    def list_dxf_files(self) -> List[str]:
        patterns = [
            os.path.join(_DIR_RAIZ, "dxf", "*.dxf"),
            os.path.join(_DIR_RAIZ, "*.dxf")
        ]
        files = []
        for p in patterns:
            files.extend(glob.glob(p))
        seen = set()
        result = []
        for f in files:
            name = os.path.basename(f)
            if name not in seen:
                seen.add(name)
                result.append(f)
        return result

    def _generate_gcode_from_dxf(self, fuente_dxf_o_trazos: Any, ruta_gcode: str):
        """generate standard gcode from dxf vector contours"""
        if isinstance(fuente_dxf_o_trazos, list):
            paths = fuente_dxf_o_trazos
        else:
            reader = LectorDXF(fuente_dxf_o_trazos)
            paths = reader.extraer_coordenadas()

        lines = [
            "%",
            "(Generated by CADConverter via FreeCAD / UFE Laser)",
            "G21",  #mm
            "G90",  #absolute
            "G17",  #xy plane
        ]
        for route in paths:
            if not route:
                continue
            lines.append("M5")
            lines.append(f"G0 X{route[0][0]:.4f} Y{route[0][1]:.4f} F100.0")
            lines.append("M3")
            for pt in route[1:]:
                lines.append(f"G1 X{pt[0]:.4f} Y{pt[1]:.4f} F20.0")
        lines.append("M5")
        lines.append("M2")
        lines.append("%")
        with open(ruta_gcode, "w", encoding="ascii", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")

    def load_dxf(self, ruta_archivo: str, params_receta: Dict) -> Dict:
        """load dxf and generate gcode and optimize trajectories"""
        if not os.path.exists(ruta_archivo):
            raise FileNotFoundError(f"File not found: {ruta_archivo}")

        self.ruta_dxf_actual = ruta_archivo
        self.nombre_dxf_actual = os.path.basename(ruta_archivo)

        #read dxf vectors
        reader = LectorDXF(ruta_archivo)
        dxf_paths = reader.extraer_coordenadas()
        if not dxf_paths:
            raise ValueError(f"No vector entities found in {self.nombre_dxf_actual}")
        self.trazos_originales = dxf_paths

        #gcode output path
        base_name, _ = os.path.splitext(ruta_archivo)
        output_gcode_path = base_name + ".gcode"

        #generate gcode from all paths
        self._generate_gcode_from_dxf(dxf_paths, output_gcode_path)

        #parse gcode
        v_mark = float(params_receta.get("velocidad_trazado", 2.0))
        v_jump = float(params_receta.get("velocidad_viaje", 3.5))
        parser = GCodeParser(output_gcode_path, default_feed_mm_s=v_mark, rapid_speed_mm_s=v_jump)
        self.bloques_gcode_crudos = parser.parse()

        #optimize paths
        tol_rdp = float(params_receta.get("tolerancia_rdp", 0.0))
        tol_union = float(params_receta.get("tolerancia_union", 0.08))
        optimizer = PathOptimizer(
            epsilon=tol_rdp,
            rapid_speed_mm_s=v_jump,
            connection_tolerance=tol_union
        )
        self.bloques_gcode_optimizados = optimizer.optimize(self.bloques_gcode_crudos)

        return self.recalculate_paths(params_receta)

    def recalculate_paths(self, params_receta: Dict) -> Dict:
        """apply scale rotation and spatial optimization to paths"""
        if not self.trazos_originales:
            return {}

        tol_rdp = float(params_receta.get("tolerancia_rdp", 0.0))
        tol_union = float(params_receta.get("tolerancia_union", 0.08))
        v_jump = float(params_receta.get("velocidad_viaje", 3.5))

        #reoptimize gcode blocks
        if hasattr(self, "bloques_gcode_crudos") and self.bloques_gcode_crudos:
            optimizer = PathOptimizer(
                epsilon=tol_rdp,
                rapid_speed_mm_s=v_jump,
                connection_tolerance=tol_union
            )
            self.bloques_gcode_optimizados = optimizer.optimize(self.bloques_gcode_crudos)

        scale = float(params_receta.get("escala_dibujo", 0.90))
        rotate_90 = bool(params_receta.get("rotar_90_grados", 0))
        rotation_deg = params_receta.get("rotacion_grados", None)
        min_len = float(params_receta.get("longitud_min_trazo", 0.01))

        cfg = HARDWARE_CONFIG["thorlabs_galvo"]
        cal_width = cfg.get("marco_ancho_cm", 10.0)
        cal_height = cfg.get("marco_alto_cm", 10.0)

        self.trazos_calibrados = transform_and_scale_dxf(
            self.trazos_originales,
            x_min_limit=self.x_min_limit,
            x_max_limit=self.x_max_limit,
            y_min_limit=self.y_min_limit,
            y_max_limit=self.y_max_limit,
            escala=scale,
            rotar_90_grados=rotate_90,
            rotacion_grados=rotation_deg,
            marco_ancho_cm=cal_width,
            marco_alto_cm=cal_height,
            base_ancho_cm=self.ancho_base_cm,
            base_alto_cm=self.alto_base_cm,
            tolerancia_rdp=tol_rdp,
            tolerancia_union=tol_union,
            longitud_min_trazo=min_len,
            optimizar_recorrido=True,
            centro_x=self.centro_x,
            centro_y=self.centro_y
        )

        #invert and swap axes
        invert_x = bool(params_receta.get("invert_x", False))
        invert_y = bool(params_receta.get("invert_y", False))
        swap_xy = bool(params_receta.get("swap_xy", False))

        if invert_x or invert_y or swap_xy:
            self.trazos_calibrados = self.apply_hardware_transform(
                self.trazos_calibrados,
                invert_x=invert_x,
                invert_y=invert_y,
                swap_xy=swap_xy
            )

        #paths in cm for canvas
        self.trazos_fisicos_cm = []
        range_x = self.x_max_limit - self.x_min_limit
        range_y = self.y_max_limit - self.y_min_limit
        kx = cal_width / range_x if range_x > 0 else 1.0
        ky = cal_height / range_y if range_y > 0 else 1.0

        base_cx = self.ancho_base_cm / 2.0
        base_cy = self.alto_base_cm / 2.0

        for route in self.trazos_calibrados:
            route_cm = []
            for xs, ys in route:
                x_cm = base_cx + (xs - self.centro_x) * kx
                y_cm = base_cy + (ys - self.centro_y) * ky
                route_cm.append((round(x_cm, 3), round(y_cm, 3)))
            self.trazos_fisicos_cm.append(route_cm)

        min_x, max_x, min_y, max_y = obtener_limites_dxf(self.trazos_calibrados)
        total_points = sum(len(t) for t in self.trazos_calibrados)

        return {
            "archivo": self.nombre_dxf_actual,
            "ruta": self.ruta_dxf_actual,
            "num_trazos": len(self.trazos_calibrados),
            "num_waypoints": total_points,
            "ancho_cm": round(max_x - min_x, 2),
            "alto_cm": round(max_y - min_y, 2),
            "min_x": min_x, "max_x": max_x,
            "min_y": min_y, "max_y": max_y,
            "limites_hardware": {
                "x_min": self.x_min_limit, "x_max": self.x_max_limit,
                "y_min": self.y_min_limit, "y_max": self.y_max_limit
            }
        }

    #async execution
    def start_execution(self,
                          params_receta: Dict,
                          on_progress: Callable,
                          on_log: Callable,
                          on_finished: Callable,
                          on_pass_change: Optional[Callable[[int, int], None]] = None):
        """start tracing process in background thread"""
        if self._en_ejecucion:
            return

        self._evento_detener.clear()
        self._evento_pausa.set()
        self._en_ejecucion = True
        self._esta_pausado = False

        self._hilo_ejecucion = threading.Thread(
            target=self._worker_thread,
            args=(params_receta, on_progress, on_log, on_finished, on_pass_change),
            daemon=True
        )
        self._hilo_ejecucion.start()

    def toggle_pause(self) -> bool:
        """toggle pause and resume non-blocking"""
        if not self._en_ejecucion:
            return False

        if self._esta_pausado:
            self._esta_pausado = False
            self._evento_pausa.set()
            return False
        else:
            self._esta_pausado = True
            self._evento_pausa.clear()
            self.laser_off()
            return True

    def pause_for_safety(self):
        """preventive immediate pause"""
        if not self._en_ejecucion:
            return
        self._esta_pausado = True
        self._evento_pausa.clear()

    def stop_execution(self):
        """stop active execution immediately with atomic e-stop"""
        self._evento_detener.set()
        self._evento_pausa.set()
        if hasattr(self, "daq_controller") and self.daq_controller:
            try:
                self.daq_controller.stop_and_clear()
            except Exception as e:
                print(f"[PuenteLaser] Error al detener DAQ en E-STOP: {e}")
        self.laser_off()
        self.center_galvos()

    def run_framing(
        self,
        params: Optional[Dict[str, Any]] = None,
        on_progress: Optional[Callable] = None,
        on_log: Optional[Callable] = None,
        on_finished: Optional[Callable] = None,
        asincrono: bool = True
    ) -> bool:
        """run closed rectangular framing routine around bounding box with laser off"""
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
        v_jump = float(params_dict.get("velocidad_viaje", 2000.0))
        num_laps = int(params_dict.get("num_vueltas", params_dict.get("vueltas_framing", 1)))
        num_laps = max(1, min(2, num_laps))

        #bounding box
        min_x, max_x, min_y, max_y = obtener_limites_dxf(self.trazos_calibrados)

        #closed perimeter
        c1 = (float(min_x), float(min_y))
        c2 = (float(max_x), float(min_y))
        c3 = (float(max_x), float(max_y))
        c4 = (float(min_x), float(max_y))
        corners = [c1, c2, c3, c4, c1]

        p_home = (float(self.centro_x), float(self.centro_y))

        #g0 blocks, laser off
        blocks: List[TrajectoryBlock] = []
        pos = p_home

        for lap in range(num_laps):
            for pt in corners:
                dist = math.hypot(pt[0] - pos[0], pt[1] - pos[1])
                if dist > 1e-9:
                    dur_s = max(0.010, dist / max(0.1, v_jump))
                    blocks.append(TrajectoryBlock("G0", pos, pt, dist / dur_s))
                    pos = pt

        #return home
        dist_home = math.hypot(p_home[0] - pos[0], p_home[1] - pos[1])
        if dist_home > 1e-9:
            dur_s = max(0.010, dist_home / max(0.1, v_jump))
            blocks.append(TrajectoryBlock("G0", pos, p_home, dist_home / dur_s))

        def _framing_thread():
            t_start = time.time()
            self._en_ejecucion = True
            self._evento_detener.clear()
            self._evento_pausa.set()
            state = "COMPLETED"
            error_msg = ""

            #make sure laser is off
            self.laser_off()

            if on_log:
                s_suf = 's' if num_laps > 1 else ''
                on_log(tr("log_framing_routine_start", vueltas=num_laps, s=s_suf))
                on_log(tr("log_framing_bbox", min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y))
                on_log(tr("log_framing_speed", speed=v_jump))

            try:
                fs = 5000.0
                generator = GalvoSignalGenerator(
                    blocks,
                    sample_rate_hz=fs,
                    scale_factor_v_per_mm=self.escala_voltaje_v_mm,
                    voltage_limits=(-10.0, 10.0),
                    jump_delay_us=5000.0,
                    mark_delay_us=0.0,
                    laser_on_delay_us=0.0,
                    laser_off_delay_us=0.0
                )
                voltages, gate = generator.generate_signals()
                #laser gate always 0
                gate.fill(0)

                try:
                    self.daq_controller = NIDaqController(simulate=self.es_simulacion)
                    self.daq_controller.setup_hardware(f_s=fs)
                    self.daq_controller.write_buffers(voltages, gate)
                    self.daq_controller.start_emission()
                except Exception as daq_e:
                    if on_log:
                        on_log(f"[Framing DAQ Notice] {daq_e}")

                #telemetry loop
                n_samples = voltages.shape[1]
                t0 = time.time()
                while True:
                    if self._evento_detener.is_set():
                        state = "ABORTED"
                        break

                    #pause, freeze timeline
                    if not self._evento_pausa.is_set():
                        t_pausa = time.time()
                        while not self._evento_pausa.is_set():
                            if self._evento_detener.is_set():
                                break
                            time.sleep(0.05)
                        t0 += time.time() - t_pausa
                        continue

                    k = min(n_samples - 1, int((time.time() - t0) * fs))
                    vx = float(voltages[0, k])
                    vy = float(voltages[1, k])
                    pct = min(100.0, (k / float(max(1, n_samples - 1))) * 100.0)

                    if on_progress:
                        on_progress(
                            0, 1,
                            k, n_samples,
                            vx / self.escala_voltaje_v_mm, vy / self.escala_voltaje_v_mm,
                            round(pct, 1), round(pct, 1),
                            False,  #laser off
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
                state = "ERROR"
                error_msg = str(e)
                if on_log:
                    on_log(f"[Framing ERROR] {e}")
            finally:
                if hasattr(self, "daq_controller") and self.daq_controller:
                    try:
                        self.daq_controller.stop_and_clear()
                    except Exception:
                        pass
                self.laser_off()
                self._en_ejecucion = False
                dur_s = round(time.time() - t_start, 2)
                if on_finished:
                    on_finished(state, error_msg, dur_s)

        if asincrono:
            self._hilo_ejecucion = threading.Thread(target=_framing_thread, daemon=True)
            self._hilo_ejecucion.start()
            return True
        else:
            _framing_thread()
            return True

    @property
    def is_running(self) -> bool:
        return self._en_ejecucion

    @property
    def is_paused(self) -> bool:
        return self._esta_pausado

    def _worker_thread(self,
                      params: Dict,
                      on_progress: Callable,
                      on_log: Callable,
                      on_finished: Callable,
                      on_pass_change: Optional[Callable[[int, int], None]] = None):
        """kinematic execution engine with high fidelity telemetry"""
        t_start = time.time()
        state = "COMPLETED"
        error_msg = ""

        paths = self.trazos_calibrados
        if not paths:
            if self.ruta_dxf_actual and os.path.exists(self.ruta_dxf_actual):
                on_log(tr("log_exec_processing"))
                self.load_dxf(self.ruta_dxf_actual, params)
                paths = self.trazos_calibrados
        if not paths:
            self._en_ejecucion = False
            on_finished("ERROR", "No calculated paths to execute", 0)
            return

        v_mark = float(params.get("velocidad_trazado", 500.0))
        v_jump = float(params.get("velocidad_viaje", 2000.0))
        min_dur_seg = int(params.get("duracion_min_segmento_ms", 10))
        min_dur_jump = int(params.get("duracion_min_viaje_ms", 50))
        jump_delay_ms = float(params.get("jump_delay_ms", 0))
        mark_delay_ms = float(params.get("mark_delay_ms", 0))
        laser_on_delay_ms = float(params.get("laser_on_delay_ms", 0))
        laser_off_delay_ms = float(params.get("laser_off_delay_ms", 0))

        num_passes = max(1, int(params.get("num_pasadas", 1)))
        cooling_delay_s = max(0.0, float(params.get("cooling_delay_s", 0.0)))
        process_mode = str(params.get("modo_proceso", "Cutting"))

        total_paths = len(paths)
        total_points = sum(len(t) for t in paths)

        hw_mode = 'PHYSICAL HARDWARE' if not self.es_simulacion else 'VIRTUAL SIMULATION'
        on_log(tr("log_trace_start", mode=process_mode, passes=num_passes, file=self.nombre_dxf_actual))
        on_log(tr("log_trace_header", file=self.nombre_dxf_actual))
        on_log(tr("log_trace_hw", hw=self.get_hardware_name(), mode=hw_mode))
        on_log(tr("log_trace_paths", paths=total_paths, waypoints=total_points, passes=num_passes))
        on_log(tr("log_trace_speeds", mark=v_mark, jump=v_jump))
        on_log(tr("log_trace_delays", jump=jump_delay_ms, mark=mark_delay_ms, on=laser_on_delay_ms, off=laser_off_delay_ms, cooling=cooling_delay_s))

        fb: Dict[str, Any] = {
            "on": False,
            "idx": 0,
            "sumsq": 0.0,
            "max": 0.0,
            "n": 0,
            "chunks_meas": [],
            "chunks_cmd": [],
        }
        self.ultimo_tracking_rms_um = None
        self.ultimo_tracking_max_um = None
        self.ultimo_tracking_lag_ms = None

        try:
            #1. build g0/g1 blocks
            blocks: List[TrajectoryBlock] = []
            meta: List[Tuple[int, int, int, int]] = []  #(path, point, points in path, is_mark)
            pos: Tuple[float, float] = (float(self.centro_x), float(self.centro_y))
            t_nominal = 0.0
            n_jumps = 0
            n_contours = 0

            for path_idx, route in enumerate(paths):
                if not route:
                    continue
                target = (float(route[0][0]), float(route[0][1]))
                dist = math.hypot(target[0] - pos[0], target[1] - pos[1])
                if dist > 1e-9:
                    dur_s = max(min_dur_jump / 1000.0, dist / max(0.1, v_jump))
                    blocks.append(TrajectoryBlock("G0", pos, target, dist / dur_s))
                    meta.append((path_idx, 0, len(route), 0))
                    t_nominal += dur_s
                    n_jumps += 1
                pos = target
                n_contours += 1

                for i_pt in range(1, len(route)):
                    pt = (float(route[i_pt][0]), float(route[i_pt][1]))
                    dist = math.hypot(pt[0] - pos[0], pt[1] - pos[1])
                    if dist <= 1e-9:
                        continue
                    dur_s = max(min_dur_seg / 1000.0, dist / max(0.1, v_mark))
                    blocks.append(TrajectoryBlock("G1", pos, pt, dist / dur_s))
                    meta.append((path_idx, i_pt, len(route), 1))
                    t_nominal += dur_s
                    pos = pt

            #return to home
            p_home = (float(self.centro_x), float(self.centro_y))
            dist_home = math.hypot(p_home[0] - pos[0], p_home[1] - pos[1])
            if dist_home > 1e-9:
                dur_home_s = max(min_dur_jump / 1000.0, dist_home / max(0.1, v_jump))
                blocks.append(TrajectoryBlock("G0", pos, p_home, dist_home / dur_home_s))
                last_path_idx = max(0, len(paths) - 1)
                pts_last = len(paths[last_path_idx]) if paths and paths[last_path_idx] else 0
                meta.append((last_path_idx, pts_last, pts_last, 0))
                t_nominal += dur_home_s
                n_jumps += 1
                pos = p_home

            if not blocks:
                raise ValueError("Calculated paths contain no movable segments.")

            #2. build signal
            t_total_est = t_nominal + (n_jumps * jump_delay_ms + n_contours * mark_delay_ms) / 1000.0
            fs = min(20000.0, max(1000.0, 1.5e6 / max(t_total_est, 1e-3)))
            scale_v = self.escala_voltaje_v_mm

            generator = GalvoSignalGenerator(
                blocks,
                sample_rate_hz=fs,
                scale_factor_v_per_mm=scale_v,
                voltage_limits=(-10.0, 10.0),
                jump_delay_us=jump_delay_ms * 1000.0,
                mark_delay_us=mark_delay_ms * 1000.0,
                laser_on_delay_us=laser_on_delay_ms * 1000.0,
                laser_off_delay_us=laser_off_delay_ms * 1000.0,
            )
            voltages, gate = generator.generate_signals()
            n_samples = int(voltages.shape[1])
            k_last = n_samples - 1
            on_log(f"Signal timeline: {n_samples} samples @ {fs:.0f} Hz "
                   f"-> {n_samples / fs:.2f} s per pass (physical delays included)")

            def _drain_feedback(final: bool = False) -> None:
                """read new ai samples accumulate tracking error and emit measured points"""
                if not fb["on"] or not self.daq_controller:
                    return
                attempts = 15 if final else 1
                for _ in range(attempts):
                    chunk = self.daq_controller.read_feedback()
                    if chunk is None:
                        if not self.daq_controller.feedback_active:
                            fb["on"] = False
                            on_log("[Feedback] Hardware feedback became unavailable; continuing without it.")
                            return
                        if final and fb["idx"] < n_samples:
                            time.sleep(0.02)
                            continue
                        return
                    i0 = fb["idx"]
                    i1 = min(i0 + int(chunk.shape[1]), n_samples)
                    if i1 > i0:
                        meas = chunk[:, : i1 - i0]
                        cmd = voltages[:, i0:i1]
                        err_mm = np.hypot(meas[0] - cmd[0], meas[1] - cmd[1]) / scale_v
                        fb["sumsq"] += float(np.sum(err_mm * err_mm))
                        fb["max"] = max(fb["max"], float(np.max(err_mm)))
                        fb["n"] += int(err_mm.size)
                        fb["chunks_meas"].append(meas)
                        fb["chunks_cmd"].append(cmd)
                        fb["idx"] = i1
                        if self.on_feedback_cb is not None:
                            step = max(1, (i1 - i0) // 10)
                            sub = meas[:, ::step] / scale_v
                            try:
                                self.on_feedback_cb(list(zip(sub[0].tolist(), sub[1].tolist())))
                            except Exception:
                                pass
                    if not final or fb["idx"] >= n_samples:
                        return

            #map samples to blocks
            starts = np.array([b.start for b in blocks], dtype=np.float64)
            ends = np.array([b.end for b in blocks], dtype=np.float64)
            speeds = np.array([b.velocity for b in blocks], dtype=np.float64)
            is_mark = np.array([b.motion_type == "G1" for b in blocks], dtype=bool)

            distances = np.hypot(*(ends - starts).T)
            motion_samples = np.rint(distances / speeds * fs).astype(np.int64)
            motion_samples = np.where((distances > 0) & (motion_samples < 1), 1, motion_samples)
            n_jump = generator.n_jump
            n_mark = generator.n_mark
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
            block_idx = np.concatenate(([0], block_index))
            offsets = np.concatenate(([1], 1 + np.cumsum(total_samples)[:-1]))

            meta_arr = np.array(meta, dtype=np.int64)
            b_path, b_point, b_points_total, b_mark = meta_arr.T

            #progress by marking samples
            marking_samples = b_mark[block_idx].astype(np.int64)
            marking_samples[0] = 0  #first sample is not marking
            acc_marking = np.cumsum(marking_samples)
            total_marking = max(1, int(acc_marking[-1]))
            acc_before = acc_marking[offsets - 1]
            acc_after = acc_marking[offsets + total_samples - 1]
            span_by_path: Dict[int, List[int]] = {}
            for b in range(len(blocks)):
                if b_mark[b]:
                    path_id = int(b_path[b])
                    if path_id not in span_by_path:
                        span_by_path[path_id] = [int(acc_before[b]), int(acc_after[b])]
                    else:
                        span_by_path[path_id][1] = int(acc_after[b])

            #3. pass loop
            for pass_idx in range(1, num_passes + 1):
                if self._evento_detener.is_set():
                    state = "STOPPED"
                    break

                self.pass_actual = pass_idx
                if on_pass_change:
                    try:
                        on_pass_change(pass_idx, num_passes)
                    except Exception:
                        pass

                on_log(tr("log_exec_pass", mode=process_mode, pass_idx=pass_idx, passes=num_passes))

                #send signal to daq
                try:
                    self.daq_controller = NIDaqController(simulate=self.es_simulacion)
                    self.daq_controller.setup_hardware(f_s=fs)
                    self.daq_controller.write_buffers(voltages, gate)
                    fb["on"] = False
                    fb["idx"] = 0
                    if self.feedback_habilitado:
                        fb["on"] = bool(self.daq_controller.enable_feedback())
                        if fb["on"]:
                            on_log(f"[Feedback] Hardware feedback tracking active (pass {pass_idx}/{num_passes}).")
                        else:
                            on_log("[Feedback] Hardware feedback unavailable; running without it.")
                    self.daq_controller.start_emission()
                    on_log(f"[NIDaqController] Pass {pass_idx}/{num_passes}: Emission armed and running ({'SIMULATION' if self.es_simulacion else 'HARDWARE'}).")
                except Exception as daq_e:
                    fb["on"] = False
                    on_log(f"[NIDaqController Notice] {daq_e}")

                #telemetry replay ~35fps
                t0 = time.time()
                while True:
                    if self._evento_detener.is_set():
                        state = "STOPPED"
                        break

                    #pause, freeze timeline (in simulation mode; in hardware mode, current pass finishes cleanly)
                    if self.es_simulacion and not self._evento_pausa.is_set():
                        t_pausa = time.time()
                        while not self._evento_pausa.is_set():
                            if self._evento_detener.is_set():
                                break
                            time.sleep(0.05)
                        t0 += time.time() - t_pausa
                        continue

                    _drain_feedback()

                    k = min(k_last, int((time.time() - t0) * fs))
                    block_i = int(block_idx[k])
                    vx = float(voltages[0, k])
                    vy = float(voltages[1, k])
                    laser_active = bool(gate[0, k])
                    path_id = int(b_path[block_i])

                    acc = int(acc_marking[k])
                    span = span_by_path.get(path_id)
                    if span and span[1] > span[0]:
                        pct_path = (acc - span[0]) / float(span[1] - span[0]) * 100.0
                    else:
                        pct_path = 0.0

                    #total percentage
                    pct_pass_fraction = acc / float(total_marking)
                    pct_total = ((pass_idx - 1) + pct_pass_fraction) / float(num_passes) * 100.0

                    on_progress(
                        path_id, total_paths,
                        int(b_point[block_i]), int(b_points_total[block_i]),
                        vx / scale_v, vy / scale_v,
                        round(min(100.0, max(0.0, pct_path)), 1),
                        round(min(100.0, max(0.0, pct_total)), 1),
                        laser_active,
                        vx, vy
                    )

                    if k >= k_last:
                        break
                    time.sleep(0.028)

                #read remaining feedback
                if fb["on"] and not self._evento_detener.is_set():
                    _drain_feedback(final=True)

                #clear daq, laser off
                if hasattr(self, "daq_controller") and self.daq_controller:
                    try:
                        self.daq_controller.stop_and_clear()
                    except Exception:
                        pass
                self.laser_off()

                if self._evento_detener.is_set():
                    state = "STOPPED"
                    break

                #inter-pass pause handling (Clean pause between passes)
                if not self._evento_pausa.is_set() and pass_idx < num_passes:
                    if on_log:
                        on_log(
                            f"[Pausa] Pasada {pass_idx}/{num_passes} completada limpiamente. "
                            f"Sistema en reposo seguro (Láser apagado a 0V, espejos centrados). "
                            f"Presione Reanudar para continuar con la pasada {pass_idx + 1}/{num_passes}."
                        )
                    while not self._evento_pausa.is_set():
                        if self._evento_detener.is_set():
                            state = "STOPPED"
                            break
                        time.sleep(0.05)

                    if self._evento_detener.is_set():
                        state = "STOPPED"
                        break

                    if on_log:
                        on_log(f"[Reanudación] Reanudando ejecución para pasada {pass_idx + 1}/{num_passes}...")

                #cooling between passes
                if pass_idx < num_passes and cooling_delay_s > 0:
                    on_log(f"[Cooling] Pass {pass_idx}/{num_passes} completed. "
                           f"Laser strictly OFF (0 LOW). Thermal cooling delay: {cooling_delay_s:.1f}s...")
                    t_cool_start = time.time()
                    while (time.time() - t_cool_start) < cooling_delay_s:
                        if self._evento_detener.is_set():
                            state = "STOPPED"
                            break
                        while not self._evento_pausa.is_set():
                            if self._evento_detener.is_set():
                                break
                            time.sleep(0.05)
                        time.sleep(0.05)

                    if self._evento_detener.is_set():
                        state = "STOPPED"
                        break

            #4. shutdown
            if self._evento_detener.is_set():
                state = "ABORTED"
                on_log(tr("log_stop_executed"))
                self.laser_off()
                on_log(tr("log_stop_rest"))
            else:
                on_log(tr("log_work_completed"))

        except Exception as e:
            state = "ERROR"
            error_msg = str(e)
            on_log(f"[ERROR] Exception during execution: {e}")

        finally:
            #failsafe: stop DAQ controller first, then laser off, mirrors home
            if hasattr(self, "daq_controller") and self.daq_controller:
                try:
                    self.daq_controller.stop_and_clear()
                except Exception as e_daq:
                    print(f"[PuenteLaser] DAQ cleanup notice in finally: {e_daq}")
            self.laser_off()
            self.center_galvos()
            duration_s = round(time.time() - t_start, 2)

            #tracking error metrics
            trk_rms_um: Optional[float] = None
            trk_max_um: Optional[float] = None
            trk_lag_ms: Optional[float] = None
            if fb["n"] > 0:
                trk_rms_um = round(math.sqrt(fb["sumsq"] / fb["n"]) * 1000.0, 1)
                trk_max_um = round(fb["max"] * 1000.0, 1)
                if fb["chunks_meas"] and fb["chunks_cmd"]:
                    try:
                        meas_full = np.hstack(fb["chunks_meas"])
                        cmd_full = np.hstack(fb["chunks_cmd"])
                        trk_lag_ms = calc_inertial_lag_ms(meas_full, cmd_full, fs)
                    except Exception as e_lag:
                        print(f"[PuenteLaser] Lag estimation notice: {e_lag}")
                        trk_lag_ms = 0.0
                else:
                    trk_lag_ms = 0.0

                self.ultimo_tracking_rms_um = trk_rms_um
                self.ultimo_tracking_max_um = trk_max_um
                self.ultimo_tracking_lag_ms = trk_lag_ms
                telemetry_msg = (
                    f"[TELEMETRY] Tracking Error: RMS = {trk_rms_um:.1f} \u00b5m | "
                    f"Max = {trk_max_um:.1f} \u00b5m | Lag = {trk_lag_ms:.2f} ms"
                )
                print(telemetry_msg)
                try:
                    on_log(telemetry_msg)
                except Exception:
                    pass
            self._en_ejecucion = False
            self._esta_pausado = False

            try:
                recipe_id = params.get("_receta_id")
                recipe_name = params.get("_receta_nombre", "Manual")
                mode_db = str(params.get("modo_proceso", "Cutting"))
                state_db = "COMPLETADO" if state in ("COMPLETED", "COMPLETADO") else ("ABORTADO" if state in ("ABORTED", "STOPPED", "ABORTADO") else "FALLO_HARDWARE")
                self.gestor_trazabilidad.registrar_ciclo({
                    "operador": "Operator",
                    "archivo_dxf": self.nombre_dxf_actual or "Unknown",
                    "hardware_usado": self.hal_actual,
                    "receta_id": recipe_id,
                    "receta_nombre": recipe_name,
                    "modo_proceso": mode_db,
                    "velocidad_trazado": v_mark,
                    "velocidad_viaje": v_jump,
                    "num_pasadas": int(params.get("num_pasadas", 1)),
                    "escala_dibujo": float(params.get("escala_dibujo", 0.9)),
                    "tolerancia_rdp": float(params.get("tolerancia_rdp", 0.005)),
                    "tolerancia_union": float(params.get("tolerancia_union", 0.08)),
                    "trazos_totales": total_paths,
                    "waypoints_totales": total_points,
                    "estado": state_db,
                    "mensaje_error": error_msg,
                    "duracion_segundos": duration_s,
                    "tracking_rms_um": trk_rms_um,
                    "tracking_max_um": trk_max_um,
                    "tracking_lag_ms": trk_lag_ms
                })
                on_log(tr("log_db_recorded", status=state_db, dur=duration_s))
            except Exception as e_bd:
                on_log(f"[DB] Warning: Could not record traceability: {e_bd}")

            on_finished(state, error_msg, duration_s)
