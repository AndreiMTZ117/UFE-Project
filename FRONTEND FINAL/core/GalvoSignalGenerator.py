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
        pincushion_kx: Optional[float] = None,
        pincushion_ky: Optional[float] = None,
        field_half_width_mm: Optional[float] = None,
        connection_tolerance_mm: float = 1e-6,
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ) -> None:
        """initialize galvo signal generator"""
        cfg = config if config is not None else load_hardware_config(config_path)
        daq_cfg = cfg.get("daq", {})
        dyn_cfg = cfg.get("galvo_dynamics", {})

        if sample_rate_hz is None:
            sample_rate_hz = float(daq_cfg.get("sample_rate_hz", daq_cfg.get("f_s", 100_000.0)))
        if scale_factor_v_per_mm is None:
            scale_factor_v_per_mm = get_volts_per_mm(cfg)

        if voltage_limits is None:
            raw_v_limits = cfg.get("voltage_limits", dyn_cfg.get("voltage_limits", {}))
            if isinstance(raw_v_limits, dict):
                voltage_limits = (float(raw_v_limits.get("min", -10.0)), float(raw_v_limits.get("max", 10.0)))
            elif isinstance(raw_v_limits, (list, tuple)) and len(raw_v_limits) == 2:
                voltage_limits = (float(raw_v_limits[0]), float(raw_v_limits[1]))
            else:
                voltage_limits = (-10.0, 10.0)

        if jump_delay_us is None:
            jump_delay_us = float(dyn_cfg.get("jump_delay_us", 150.0))
        if mark_delay_us is None:
            mark_delay_us = float(dyn_cfg.get("mark_delay_us", 50.0))
        if laser_on_delay_us is None:
            laser_on_delay_us = float(dyn_cfg.get("laser_on_delay_us", 20.0))
        if laser_off_delay_us is None:
            laser_off_delay_us = float(dyn_cfg.get("laser_off_delay_us", 20.0))

        dist_cfg = cfg.get("distortion_correction", {})
        correction_enabled = bool(dist_cfg.get("enabled", True))
        if pincushion_kx is None:
            pincushion_kx = float(dist_cfg.get("pincushion_kx", 0.0)) if correction_enabled else 0.0
        if pincushion_ky is None:
            pincushion_ky = float(dist_cfg.get("pincushion_ky", 0.0)) if correction_enabled else 0.0
        if field_half_width_mm is None:
            field_half_width_mm = float(dist_cfg.get("field_half_width_mm", 193.5))

        self.trajectories: Sequence[TrajectoryBlock] = trajectories
        self.sample_rate_hz: float = float(sample_rate_hz)
        self.scale_factor_v_per_mm: float = float(scale_factor_v_per_mm)
        self.voltage_limits: Tuple[float, float] = (float(voltage_limits[0]), float(voltage_limits[1]))
        self.connection_tolerance_mm: float = connection_tolerance_mm
        self.pincushion_kx: float = float(pincushion_kx)
        self.pincushion_ky: float = float(pincushion_ky)
        self.field_half_width_mm: float = float(field_half_width_mm)

        lens_cfg = cfg["lens_model"]
        self.lens_kx: float = float(lens_cfg["pincushion_kx"])
        self.lens_ky: float = float(lens_cfg["pincushion_ky"])
        self.lens_w: float = float(lens_cfg["field_half_width_mm"])
        self.positions: np.ndarray = np.zeros((0, 2), dtype=np.float64)

        self.n_jump: int = self._us_to_samples(jump_delay_us)
        self.n_mark: int = self._us_to_samples(mark_delay_us)
        self.n_laser_on: int = self._us_to_samples(laser_on_delay_us)
        self.n_laser_off: int = self._us_to_samples(laser_off_delay_us)

    def _us_to_samples(self, delay_us: float) -> int:
        """convert delay in microseconds to sample count"""
        return int(round(delay_us / MICROSECONDS_PER_SECOND * self.sample_rate_hz))

    def _apply_pincushion_correction(self, positions: np.ndarray) -> np.ndarray:
        """apply cross-axis pincushion pre-distortion"""
        if self.pincushion_kx == 0.0 and self.pincushion_ky == 0.0:
            return positions

        w = self.field_half_width_mm
        x = positions[:, 0]
        y = positions[:, 1]

        x_corr = x * (1.0 - self.pincushion_kx * (y / w) ** 2)
        y_corr = y * (1.0 - self.pincushion_ky * (x / w) ** 2)
        return np.column_stack((x_corr, y_corr))

    @staticmethod
    def _invert_pincushion(positions: np.ndarray, kx: float, ky: float, w: float) -> np.ndarray:
        """invert pincushion model by fixed-point iteration"""
        pts = np.asarray(positions, dtype=np.float64)
        if (kx == 0.0 and ky == 0.0) or pts.size == 0:
            return pts

        xc, yc = pts[:, 0], pts[:, 1]
        x, y = xc.copy(), yc.copy()
        inv_w2 = 1.0 / (w * w)
        for _ in range(25):
            x_new = xc / (1.0 - kx * y * y * inv_w2)
            y_new = yc / (1.0 - ky * x * x * inv_w2)
            if np.max(np.abs(x_new - x)) < 1e-9 and np.max(np.abs(y_new - y)) < 1e-9:
                x, y = x_new, y_new
                break
            x, y = x_new, y_new

        return np.column_stack((x, y))

    def view_positions(self, positions: np.ndarray, through_lens: bool) -> np.ndarray:
        """canvas coordinates of nominal positions, optionally seen through the lens model"""
        commanded = self._apply_pincushion_correction(positions)
        if through_lens:
            return self._invert_pincushion(commanded, self.lens_kx, self.lens_ky, self.lens_w)
        return commanded

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

        #apply optical pincushion distortion correction
        self.positions = positions
        positions_corr = self._apply_pincushion_correction(positions)

        #spatial to voltage mapping with saturation
        voltages = positions_corr.T * self.scale_factor_v_per_mm

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

        gate_out = gate.reshape(1, -1)

        logger.info(
            "Generated %d samples (%.3f ms at %.0f Hz).",
            voltages.shape[1], voltages.shape[1] / self.sample_rate_hz * 1e3, self.sample_rate_hz,
        )
        return np.ascontiguousarray(voltages, dtype=np.float64), gate_out
