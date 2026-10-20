# -*- coding: utf-8 -*-
"""
core/config_loader.py - Centralized configuration loader for hardware,
kinematics, and calibration parameters.

Reads settings from 'hardware_config.json' and provides safe fallback defaults
with explicit warnings if the file is absent or malformed.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import warnings
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_HARDWARE_CONFIG: Dict[str, Any] = {
    "daq": {
        "analog_channels": ["Dev1/ao0", "Dev1/ao1"],
        "laser_gate_channel": "Dev1/port0/line0",
        "f_s": 100000.0,
        "sample_rate_hz": 100000.0,
        "sync_clock": "/Dev1/ao/SampleClock",
        # Hardware Feedback Tracking (optional AI readback of GVS position monitor)
        "device_name": "Dev1",
        "ai_terminal_config": "DIFF",   # "DIFF" or "RSE"
        "feedback_sign_x": 1,
        "feedback_sign_y": 1,
        "feedback_offset_x_v": 0.0,
        "feedback_offset_y_v": 0.0,
    },
    "galvo_dynamics": {
        "voltage_limits": {
            "min": -10.0,
            "max": 10.0,
        },
        "volts_per_mm": 0.1,
        "jump_delay_us": 150,
        "mark_delay_us": 50,
        "laser_on_delay_us": 20,
        "laser_off_delay_us": 20,
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
    """Resolve the path to hardware_config.json statically."""
    target = explicit_path if explicit_path else HARDWARE_CONFIG_PATH
    return target if os.path.isfile(target) else None


def load_hardware_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from hardware_config.json or return fallback defaults.
        config_path: Optional explicit path to the JSON configuration file.
    Returns:
        Dict[str, Any]: Complete configuration dictionary with 'daq',
        'galvo_dynamics', and 'cad_cam' sections.
    """
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
        # Deep merge with defaults to ensure all keys exist
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
