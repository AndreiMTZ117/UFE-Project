# -*- coding: utf-8 -*-
"""hardware package with drivers and simulator for galvo laser"""

from .config_galvo import LIMITES_GALVO, VELOCIDAD_MARCADO_MM_S, VELOCIDAD_SALTO_MM_S
from .controlador_thorlabs import ControladorThorlabsGVS
from .simulador_thorlabs import SimuladorThorlabsGVS

__all__ = [
    "LIMITES_GALVO",
    "VELOCIDAD_MARCADO_MM_S",
    "VELOCIDAD_SALTO_MM_S",
    "ControladorThorlabsGVS",
    "SimuladorThorlabsGVS",
]
