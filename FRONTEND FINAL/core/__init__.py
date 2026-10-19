# -*- coding: utf-8 -*-
"""
Paquete Core del Sistema de Trazado Láser Vectorial

Arquitectura modular activa de procesamiento CAD/CAM y control cinemático:
  - CADConverter: Conversor Headless DXF a Código G estándar (ISO 6983).
  - GCodeParser: Parser de código G ISO 6983 para bloques discretos de trayectoria (G0/G1).
  - PathOptimizer: Optimización espacial TSP (2-Opt) y simplificación geométrica RDP.
  - GalvoSignalGenerator: Discretización temporal y compensación dinámica galvo (AO/DO).
  - NIDaqController: Controlador determinista de hardware NI-DAQmx (AO espejos + DO láser).
  - lector_dxf: Extracción de geometría vectorial desde archivos DXF.
  - generador_trayectorias: Escalado uniforme, rotación y mapeo geométrico al FOV.
"""

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
from .NIDaqController import NIDaqController, NIDaqError
from .lector_dxf import LectorDXF, obtener_limites_dxf
from .generador_trayectorias import transformar_y_escalar_dxf

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
    "LectorDXF",
    "obtener_limites_dxf",
    "optimizar_y_unir_trazos",
    "simplificar_trayectoria_rdp",
    "transformar_y_escalar_dxf",
]

