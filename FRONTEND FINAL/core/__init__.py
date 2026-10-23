# -*- coding: utf-8 -*-
"""core package for laser vector processing"""

from .config_loader import load_hardware_config, DEFAULT_HARDWARE_CONFIG
from .CADConverter import CADConverter
from .GCodeParser import GCodeParser, TrajectoryBlock, GCodeParseError
from .PathOptimizer import (
    PathOptimizer,
    optimizar_y_unir_trazos,
    simplificar_trayectoria_rdp,
    fusionar_trazos_contiguos,
)
from .GalvoSignalGenerator import GalvoSignalGenerator
from .NIDaqController import NIDaqController, NIDaqError, probe_daq_hardware, probe_feedback_hardware
from .lector_dxf import LectorDXF, obtener_limites_dxf
from .generador_trayectorias import transform_and_scale_dxf

__all__ = [
    "load_hardware_config",
    "DEFAULT_HARDWARE_CONFIG",
    "CADConverter",
    "GCodeParser",
    "TrajectoryBlock",
    "GCodeParseError",
    "PathOptimizer",
    "GalvoSignalGenerator",
    "NIDaqController",
    "NIDaqError",
    "probe_daq_hardware",
    "probe_feedback_hardware",
    "LectorDXF",
    "obtener_limites_dxf",
    "optimizar_y_unir_trazos",
    "simplificar_trayectoria_rdp",
    "transform_and_scale_dxf",
]

