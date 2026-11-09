# -*- coding: utf-8 -*-
"""hardware package with drivers and simulator for galvo laser"""

from .galvo_config import LIMITES_GALVO, VELOCIDAD_MARCADO_MM_S, VELOCIDAD_SALTO_MM_S
from .thorlabs_controller import ControladorThorlabsGVS
from .thorlabs_simulator import SimuladorThorlabsGVS

__all__ = [
    "LIMITES_GALVO",
    "VELOCIDAD_MARCADO_MM_S",
    "VELOCIDAD_SALTO_MM_S",
    "ControladorThorlabsGVS",
    "SimuladorThorlabsGVS",
]
