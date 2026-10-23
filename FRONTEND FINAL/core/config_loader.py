# -*- coding: utf-8 -*-
"""load hardware config from json with safe defaults"""

from __future__ import annotations

import copy
import json
import logging
import os
import warnings
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_HARDWARE_CONFIG: Dict[str, Any] = {
    "volts_per_mm": 0.200,
    "voltage_limits": {
        "min": -10.0,
        "max": 10.0,
    },
    "daq": {
        "device_name": "Dev1",
        "analog_channels": ["Dev1/ao0", "Dev1/ao1"],
        "laser_gate_channel": "Dev1/port0/line0",
        "ai_channels": ["Dev1/ai0", "Dev1/ai1"],
        "ai_terminal_config": "DIFF",   #terminal configuration mode
        "f_s": 100000.0,
        "sample_rate_hz": 100000.0,
        "sync_clock": "/Dev1/ao/SampleClock",
        "feedback_sign_x": 1,
        "feedback_sign_y": 1,
        "feedback_offset_x_v": 0.0,
        "feedback_offset_y_v": 0.0,
    },
    "cad_cam": {
        "freecad_cmd": "FreeCADcmd",
        "timeout_seconds": 30,
        "rdp_tolerance": 0.0,
    },
}


HARDWARE_CONFIG_PATH: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "hardware", "hardware_config.json")
)


def find_hardware_config_path(explicit_path: Optional[str] = None) -> Optional[str]:
    """resolve path to hardware config"""
    target = explicit_path if explicit_path else HARDWARE_CONFIG_PATH
    return target if os.path.isfile(target) else None


def load_hardware_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """load hardware config from json or fallback defaults"""
    resolved_path = find_hardware_config_path(config_path)

    if not resolved_path:
        target_name = config_path or "hardware_config.json"
        msg = f"Hardware configuration file '{target_name}' not found. Loading safe fallback defaults."
        logger.warning(msg)
        warnings.warn(msg, UserWarning, stacklevel=2)
        return copy.deepcopy(DEFAULT_HARDWARE_CONFIG)

    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        if not isinstance(user_config, dict):
            raise ValueError(f"Root of configuration file '{resolved_path}' must be a JSON object.")
        #deep merge with defaults
        merged_config = copy.deepcopy(DEFAULT_HARDWARE_CONFIG)
        for section, values in user_config.items():
            if isinstance(values, dict) and section in merged_config:
                merged_config[section].update(values)
            else:
                merged_config[section] = values
        return merged_config

    except Exception as exc:
        msg = f"Failed to load hardware configuration from '{resolved_path}': {exc}. Loading safe fallback defaults."
        logger.warning(msg)
        warnings.warn(msg, UserWarning, stacklevel=2)
        return copy.deepcopy(DEFAULT_HARDWARE_CONFIG)


def get_volts_per_mm(config: Optional[Dict[str, Any]] = None) -> float:
    """get spatial to voltage scale factor in v per mm"""
    cfg = config if config is not None else load_hardware_config()
    if "volts_per_mm" in cfg:
        return float(cfg["volts_per_mm"])
    if "galvo_dynamics" in cfg and "volts_per_mm" in cfg["galvo_dynamics"]:
        return float(cfg["galvo_dynamics"]["volts_per_mm"])
    return 0.200
