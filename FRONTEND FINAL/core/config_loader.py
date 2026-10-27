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

#device identity (device_name, channels) has no default on purpose: a wrong
#fallback could drive voltages on a different card, so it must come from the json
DEFAULT_HARDWARE_CONFIG: Dict[str, Any] = {
    "volts_per_mm": 0.200,
    "voltage_limits": {
        "min": -10.0,
        "max": 10.0,
    },
    "daq": {
        "ai_terminal_config": "DIFF",   #terminal configuration mode
        "sample_rate_hz": 100000.0,
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
    "distortion_correction": {
        "enabled": True,
        "pincushion_kx": 0.0,
        "pincushion_ky": 0.0,
        "field_half_width_mm": 50.0,
    },
}

REQUIRED_DAQ_KEYS = ("device_name", "analog_channels", "laser_gate_channel", "ai_channels")


class ConfigError(ValueError):
    """raised when a required hardware setting is missing from the config"""


def get_daq_identity(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """return validated daq device and channel names, fail loudly if missing"""
    cfg = config if config is not None else load_hardware_config()
    daq_cfg = cfg.get("daq", {})
    missing = [k for k in REQUIRED_DAQ_KEYS if not daq_cfg.get(k)]
    if missing:
        raise ConfigError(
            f"hardware_config.json is missing required 'daq' keys: {', '.join(missing)} "
            f"(file: {HARDWARE_CONFIG_PATH})"
        )
    device = str(daq_cfg["device_name"]).strip().strip("/")
    return {
        "device": device,
        "analog_channels": [str(c) for c in daq_cfg["analog_channels"]],
        "laser_gate_channel": str(daq_cfg["laser_gate_channel"]),
        "ai_channels": [str(c) for c in daq_cfg["ai_channels"]],
        "sync_clock": daq_cfg.get("sync_clock") or f"/{device}/ao/SampleClock",
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
