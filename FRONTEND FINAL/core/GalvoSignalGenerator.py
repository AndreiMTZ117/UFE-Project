"""temporal discretization and dynamic compensation for galvo mirrors"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional, Sequence, Tuple
import numpy as np
from core.GCodeParser import TrajectoryBlock
from core.config_loader import get_volts_per_mm, load_hardware_config

logger = logging.getLogger(__name__)

MICROSECONDS_PER_SECOND: float = 1.0e6


class GalvoSignalGenerator:
    """generate synchronized analog and digital galvo control signals"""

    def __init__(
        self,
        trajectories: Sequence[TrajectoryBlock],
        sample_rate_hz: Optional[float] = None,
        scale_factor_v_per_mm: Optional[float] = None,
        voltage_limits: Optional[Tuple[float, float]] = None,
        jump_delay_us: Optional[float] = None,
        mark_delay_us: Optional[float] = None,
        laser_on_delay_us: Optional[float] = None,
        laser_off_delay_us: Optional[float] = None,
        connection_tolerance_mm: float = 1e-6,
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ) -> None:
        """initialize galvo signal generator"""
        #resolve configuration dictionary
        cfg = config if config is not None else load_hardware_config(config_path)
        self.config: Dict[str, Any] = cfg

        daq_cfg = cfg.get("daq", {})
        dyn_cfg = cfg.get("galvo_dynamics", {})

        #resolve sample rate
        if sample_rate_hz is None:
            sample_rate_hz = float(daq_cfg.get("sample_rate_hz", daq_cfg.get("f_s", 100_000.0)))

        #resolve spatial to voltage scale
        if scale_factor_v_per_mm is None:
            scale_factor_v_per_mm = get_volts_per_mm(cfg)

        #resolve voltage limits
        if voltage_limits is None:
            raw_v_limits = cfg.get("voltage_limits", dyn_cfg.get("voltage_limits", {}))
            if isinstance(raw_v_limits, dict):
                voltage_limits = (float(raw_v_limits.get("min", -10.0)), float(raw_v_limits.get("max", 10.0)))
            elif isinstance(raw_v_limits, (list, tuple)) and len(raw_v_limits) == 2:
                voltage_limits = (float(raw_v_limits[0]), float(raw_v_limits[1]))
            else:
                voltage_limits = (-10.0, 10.0)

        #resolve dynamic delays
        if jump_delay_us is None:
            jump_delay_us = float(dyn_cfg.get("jump_delay_us", 150.0))
        if mark_delay_us is None:
            mark_delay_us = float(dyn_cfg.get("mark_delay_us", 50.0))
        if laser_on_delay_us is None:
            laser_on_delay_us = float(dyn_cfg.get("laser_on_delay_us", 20.0))
        if laser_off_delay_us is None:
            laser_off_delay_us = float(dyn_cfg.get("laser_off_delay_us", 20.0))

        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive.")
        if scale_factor_v_per_mm <= 0:
            raise ValueError("scale_factor_v_per_mm must be positive.")
        if len(voltage_limits) != 2 or voltage_limits[0] >= voltage_limits[1]:
            raise ValueError("voltage_limits must be (v_min, v_max) with v_min < v_max.")
        delays = (jump_delay_us, mark_delay_us, laser_on_delay_us, laser_off_delay_us)
        if any(delay < 0 for delay in delays):
            raise ValueError("Delays must be non-negative.")
        if connection_tolerance_mm < 0:
            raise ValueError("connection_tolerance_mm must be non-negative.")
        for block in trajectories:
            if not isinstance(block, TrajectoryBlock):
                raise TypeError("trajectories must contain TrajectoryBlock instances.")
            if block.motion_type not in ("G0", "G1"):
                raise ValueError(f"Unsupported motion type: {block.motion_type}")
            if block.velocity <= 0:
                raise ValueError("Block velocity must be strictly positive.")

        self.trajectories: Sequence[TrajectoryBlock] = trajectories
        self.sample_rate_hz: float = float(sample_rate_hz)
        self.scale_factor_v_per_mm: float = float(scale_factor_v_per_mm)
        self.voltage_limits: Tuple[float, float] = (float(voltage_limits[0]), float(voltage_limits[1]))
        self.connection_tolerance_mm: float = connection_tolerance_mm

        #convert delays from microseconds to sample counts
        self.n_jump: int = self._us_to_samples(jump_delay_us)
        self.n_mark: int = self._us_to_samples(mark_delay_us)
        self.n_laser_on: int = self._us_to_samples(laser_on_delay_us)
        self.n_laser_off: int = self._us_to_samples(laser_off_delay_us)

    def _us_to_samples(self, delay_us: float) -> int:
        """convert delay in microseconds to sample count"""
        return int(round(delay_us / MICROSECONDS_PER_SECOND * self.sample_rate_hz))

    def generate_signals(self) -> Tuple[np.ndarray, np.ndarray]:
        """build synchronized analog and digital output arrays"""
        blocks = self.trajectories
        if len(blocks) == 0:
            logger.warning("No trajectory blocks supplied; returning empty signals.")
            return np.zeros((2, 0), dtype=np.float64), np.zeros((1, 0), dtype=np.uint8)

        #block parameters as preallocated arrays
        n_blocks = len(blocks)
        starts = np.array([b.start for b in blocks], dtype=np.float64).reshape(n_blocks, 2)
        ends = np.array([b.end for b in blocks], dtype=np.float64).reshape(n_blocks, 2)
        speeds = np.array([b.velocity for b in blocks], dtype=np.float64)
        is_mark = np.array([b.motion_type == "G1" for b in blocks], dtype=bool)

        #motion sample counts
        distances = np.hypot(*(ends - starts).T)
        motion_samples = np.rint(distances / speeds * self.sample_rate_hz).astype(np.int64)
        motion_samples = np.where((distances > 0) & (motion_samples < 1), 1, motion_samples)

        #contour boundaries
        joined_to_previous = np.zeros(n_blocks, dtype=bool)
        if n_blocks > 1:
            gaps = np.hypot(*(starts[1:] - ends[:-1]).T)
            joined_to_previous[1:] = is_mark[1:] & is_mark[:-1] & (gaps <= self.connection_tolerance_mm)
        joined_to_next = np.zeros(n_blocks, dtype=bool)
        joined_to_next[:-1] = joined_to_previous[1:]
        contour_start = is_mark & ~joined_to_previous
        contour_end = is_mark & ~joined_to_next

        #dwell samples
        dwell_samples = np.where(is_mark, np.where(contour_end, self.n_mark, 0), self.n_jump).astype(np.int64)
        total_samples = motion_samples + dwell_samples
        block_offsets = np.concatenate(([0], np.cumsum(total_samples)[:-1]))
        n_total = int(total_samples.sum())

        #per sample interpolation
        n_samples = n_total + 1
        positions = np.empty((n_samples, 2), dtype=np.float64)
        positions[0] = starts[0]

        if n_total > 0:
            block_index = np.repeat(np.arange(n_blocks), total_samples)
            local_index = np.arange(n_total) - block_offsets[block_index]
            n_motion = motion_samples[block_index]
            #progress during motion and dwell
            safe_n = np.maximum(n_motion, 1)
            progress = np.where(n_motion > 0, np.minimum(local_index + 1, n_motion) / safe_n, 1.0)
            positions[1:] = starts[block_index] + progress[:, None] * (ends[block_index] - starts[block_index])

        block_offsets = block_offsets + 1  #account for prepended sample

        #laser gate with turn on and off offsets
        gate_delta = np.zeros(n_samples + 1, dtype=np.int64)
        first_blocks = np.flatnonzero(contour_start)
        last_blocks = np.flatnonzero(contour_end)
        if first_blocks.size > 0:
            on_index = block_offsets[first_blocks] + self.n_laser_on
            motion_end = block_offsets[last_blocks] + motion_samples[last_blocks]
            dwell_end = block_offsets[last_blocks] + total_samples[last_blocks]
            #laser stays on through end dwell
            off_index = np.minimum(motion_end + self.n_laser_off, dwell_end)
            on_index = np.minimum(on_index, off_index)
            np.add.at(gate_delta, on_index, 1)
            np.add.at(gate_delta, off_index, -1)
        gate = (np.cumsum(gate_delta[:-1]) > 0).astype(np.uint8)

        #spatial to voltage mapping with saturation
        voltages = positions.T * self.scale_factor_v_per_mm

        #electrical safety limits
        v_min = max(-10.0, float(self.voltage_limits[0]))
        v_max = min(10.0, float(self.voltage_limits[1]))
        saturated = (voltages < v_min) | (voltages > v_max)
        if np.any(saturated):
            logger.warning(
                "%d voltage samples exceeded safe limits [%.1f, %.1f] V and were clipped.",
                int(saturated.sum()), v_min, v_max
            )
        #clamp voltages to safe limits
        voltages = np.clip(voltages, v_min, v_max)

        #match gate length with voltage matrix
        gate_out = gate.reshape(1, -1)
        if gate_out.shape[1] != voltages.shape[1]:
            if gate_out.shape[1] < voltages.shape[1]:
                diff = voltages.shape[1] - gate_out.shape[1]
                gate_out = np.pad(gate_out, ((0, 0), (0, diff)), mode="constant", constant_values=0)
            else:
                gate_out = gate_out[:, :voltages.shape[1]]

        logger.info(
            "Generated %d samples (%.3f ms at %.0f Hz).",
            voltages.shape[1], voltages.shape[1] / self.sample_rate_hz * 1e3, self.sample_rate_hz,
        )
        return np.ascontiguousarray(voltages, dtype=np.float64), gate_out
