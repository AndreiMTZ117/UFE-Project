"""Temporal discretization and dynamic compensation for galvanometer mirrors.

Converts optimized G0/G1 trajectory blocks into synchronized sample streams
for a Thorlabs GVS112/M two-axis galvanometer driven by a DAC/DAQ card:

* a 2 x n analog voltage matrix (X and Y mirror command, in volts), and
* a 1 x n digital laser-gate vector (0 = laser off, 1 = laser on).

All per-sample computations are fully vectorized with NumPy (no Python loops
over blocks or samples).
"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional, Sequence, Tuple
import numpy as np
from core.GCodeParser import TrajectoryBlock
from core.config_loader import get_volts_per_mm, load_hardware_config

logger = logging.getLogger(__name__)

MICROSECONDS_PER_SECOND: float = 1.0e6


class GalvoSignalGenerator:
    """Generates synchronized analog and digital galvo control signals."""

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
        """Initialize the generator.

        Reads hardware and kinematic dynamics from ``config`` or
        ``hardware_config.json`` if manual arguments are not provided.

        Args:
            trajectories: Optimized blocks (see ``PathOptimizer.optimize``).
            sample_rate_hz: Hardware sample rate f_s in Hz (default from config).
            scale_factor_v_per_mm: Spatial-to-voltage gain in V/mm.
            voltage_limits: Absolute analog saturation ``(v_min, v_max)`` in V.
            jump_delay_us: Settling time after each G0 move (microseconds).
            mark_delay_us: Braking/settling dwell after each G1 contour (microseconds).
            laser_on_delay_us: Laser turn-on delay (microseconds).
            laser_off_delay_us: Laser turn-off delay (microseconds).
            connection_tolerance_mm: Max gap for two consecutive G1 blocks to be treated as one continuous contour (no delays at the joint).
            config: Optional configuration dictionary.
            config_path: Optional explicit path to hardware_config.json.

        Raises:
            ValueError: If any numeric parameter is invalid.
            TypeError: If ``trajectories`` has non-``TrajectoryBlock`` items.
        """
        # Resolve configuration dictionary (explicit dict or from file/fallback)
        cfg = config if config is not None else load_hardware_config(config_path)
        self.config: Dict[str, Any] = cfg

        daq_cfg = cfg.get("daq", {})
        dyn_cfg = cfg.get("galvo_dynamics", {})

        # Resolve sample rate
        if sample_rate_hz is None:
            sample_rate_hz = float(daq_cfg.get("sample_rate_hz", daq_cfg.get("f_s", 100_000.0)))

        # Resolve spatial-to-voltage scale
        if scale_factor_v_per_mm is None:
            scale_factor_v_per_mm = get_volts_per_mm(cfg)

        # Resolve voltage limits
        if voltage_limits is None:
            raw_v_limits = cfg.get("voltage_limits", dyn_cfg.get("voltage_limits", {}))
            if isinstance(raw_v_limits, dict):
                voltage_limits = (float(raw_v_limits.get("min", -10.0)), float(raw_v_limits.get("max", 10.0)))
            elif isinstance(raw_v_limits, (list, tuple)) and len(raw_v_limits) == 2:
                voltage_limits = (float(raw_v_limits[0]), float(raw_v_limits[1]))
            else:
                voltage_limits = (-10.0, 10.0)

        # Resolve dynamic delays
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

        # Convert every delay from microseconds to an integer sample count.
        self.n_jump: int = self._us_to_samples(jump_delay_us)
        self.n_mark: int = self._us_to_samples(mark_delay_us)
        self.n_laser_on: int = self._us_to_samples(laser_on_delay_us)
        self.n_laser_off: int = self._us_to_samples(laser_off_delay_us)

    def _us_to_samples(self, delay_us: float) -> int:
        """Convert a delay in microseconds to a whole number of samples."""
        return int(round(delay_us / MICROSECONDS_PER_SECOND * self.sample_rate_hz))

    def generate_signals(self) -> Tuple[np.ndarray, np.ndarray]:
        """Build the synchronized analog and digital output arrays.

        Algorithm (per block i, all blocks processed simultaneously):

        1. ``d = hypot(x2 - x1, y2 - y1)``, ``T = d / v``,
           ``N = round(T * f_s)`` (at least 1 if ``d > 0``).
        2. Each block emits ``N`` motion samples, linearly interpolated at
           ``dt = 1 / f_s`` so the last one lands exactly on ``(x2, y2)``,
           followed by ``N_dwell`` static samples at the end position
           (``N_jump`` after G0, ``N_mark`` after the end of a G1 contour).
        3. The laser gate is 1 from ``contour_start + N_on`` to
           ``contour_end + N_off`` (clamped to the end dwell), else 0.
        4. Positions are scaled to volts and clipped to the safe limits.

        A single leading sample at the first block's start position is
        prepended so the mirrors begin from a defined position.

        Returns:
            Tuple ``(voltages, laser_gate)`` where ``voltages`` is a float64
            array of shape ``(2, n)`` (row 0 = Vx, row 1 = Vy) and
            ``laser_gate`` is a uint8 array of shape ``(1, n)``.
        """
        blocks = self.trajectories
        if len(blocks) == 0:
            logger.warning("No trajectory blocks supplied; returning empty signals.")
            return np.zeros((2, 0), dtype=np.float64), np.zeros((1, 0), dtype=np.uint8)

        # --- Block parameters as preallocated arrays -----------------------
        n_blocks = len(blocks)
        starts = np.array([b.start for b in blocks], dtype=np.float64).reshape(n_blocks, 2)
        ends = np.array([b.end for b in blocks], dtype=np.float64).reshape(n_blocks, 2)
        speeds = np.array([b.velocity for b in blocks], dtype=np.float64)
        is_mark = np.array([b.motion_type == "G1" for b in blocks], dtype=bool)

        # --- Step 1: number of motion samples N = round(T * f_s) ------------
        distances = np.hypot(*(ends - starts).T)
        motion_samples = np.rint(distances / speeds * self.sample_rate_hz).astype(np.int64)
        motion_samples = np.where((distances > 0) & (motion_samples < 1), 1, motion_samples)

        # --- Contour boundaries: contiguous G1 blocks form one contour ------
        joined_to_previous = np.zeros(n_blocks, dtype=bool)
        if n_blocks > 1:
            gaps = np.hypot(*(starts[1:] - ends[:-1]).T)
            joined_to_previous[1:] = is_mark[1:] & is_mark[:-1] & (gaps <= self.connection_tolerance_mm)
        joined_to_next = np.zeros(n_blocks, dtype=bool)
        joined_to_next[:-1] = joined_to_previous[1:]
        contour_start = is_mark & ~joined_to_previous
        contour_end = is_mark & ~joined_to_next

        # --- Step 2: dwell samples appended after each block ----------------
        dwell_samples = np.where(is_mark, np.where(contour_end, self.n_mark, 0), self.n_jump).astype(np.int64)
        total_samples = motion_samples + dwell_samples
        block_offsets = np.concatenate(([0], np.cumsum(total_samples)[:-1]))
        n_total = int(total_samples.sum())

        # --- Per-sample interpolation (fully vectorized with preallocation) -
        n_samples = n_total + 1
        positions = np.empty((n_samples, 2), dtype=np.float64)
        positions[0] = starts[0]

        if n_total > 0:
            block_index = np.repeat(np.arange(n_blocks), total_samples)
            local_index = np.arange(n_total) - block_offsets[block_index]
            n_motion = motion_samples[block_index]
            # Progress u in (0, 1]: (k+1)/N during motion, held at 1 during dwell.
            safe_n = np.maximum(n_motion, 1)
            progress = np.where(n_motion > 0, np.minimum(local_index + 1, n_motion) / safe_n, 1.0)
            positions[1:] = starts[block_index] + progress[:, None] * (ends[block_index] - starts[block_index])

        block_offsets = block_offsets + 1  # account for the prepended sample

        # --- Step 3: laser gate with turn-on / turn-off offsets -------------
        gate_delta = np.zeros(n_samples + 1, dtype=np.int64)
        first_blocks = np.flatnonzero(contour_start)
        last_blocks = np.flatnonzero(contour_end)
        if first_blocks.size > 0:
            on_index = block_offsets[first_blocks] + self.n_laser_on
            motion_end = block_offsets[last_blocks] + motion_samples[last_blocks]
            dwell_end = block_offsets[last_blocks] + total_samples[last_blocks]
            # The laser may stay on only through the end dwell, never beyond.
            off_index = np.minimum(motion_end + self.n_laser_off, dwell_end)
            on_index = np.minimum(on_index, off_index)
            np.add.at(gate_delta, on_index, 1)
            np.add.at(gate_delta, off_index, -1)
        gate = (np.cumsum(gate_delta[:-1]) > 0).astype(np.uint8)

        # --- Step 4: spatial to voltage mapping with saturation -------------
        voltages = positions.T * self.scale_factor_v_per_mm

        # Strict electrical safety limits: protect Thorlabs GVS112/M servo amplifiers
        v_min = max(-10.0, float(self.voltage_limits[0]))
        v_max = min(10.0, float(self.voltage_limits[1]))
        saturated = (voltages < v_min) | (voltages > v_max)
        if np.any(saturated):
            logger.warning(
                "%d voltage samples exceeded safe limits [%.1f, %.1f] V and were clipped.",
                int(saturated.sum()), v_min, v_max
            )
        # Apply strict clamping to hardware limits [v_min, v_max] within [-10.0, 10.0] V
        voltages = np.clip(voltages, v_min, v_max)

        # Ensure digital laser gate matches exact length of analog output matrix
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
