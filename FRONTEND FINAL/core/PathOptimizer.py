"""Spatial optimization of laser trajectories.

Provides contour simplification (Ramer-Douglas-Peucker) and travel-distance
minimization (nearest neighbour + 2-opt) to reduce the scanner cycle time and
mirror stress.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from core.GCodeParser import TrajectoryBlock
from core.config_loader import load_hardware_config

logger = logging.getLogger(__name__)

Point = Tuple[float, float]


class PathOptimizer:
    """Simplifies cutting contours and reorders them to minimize G0 travel."""

    def __init__(
        self,
        epsilon: Optional[float] = None,
        rapid_speed_mm_s: float = 100.0,
        connection_tolerance: float = 1e-6,
        max_2opt_passes: int = 1000,
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ) -> None:
        """Initialize the optimizer.

        Args:
            epsilon: RDP geometric tolerance in millimetres (default from config).
            rapid_speed_mm_s: Speed assigned to generated G0 blocks.
            connection_tolerance: Max gap (mm) to consider two G1 blocks chained.
            max_2opt_passes: Upper bound on full 2-opt sweeps.
            config: Optional configuration dictionary.
            config_path: Optional explicit path to hardware_config.json.

        Raises:
            ValueError: If any parameter is out of range.
        """
        if epsilon is None:
            cfg = config if config is not None else load_hardware_config(config_path)
            cad_cam_cfg = cfg.get("cad_cam", {})
            epsilon = float(cad_cam_cfg.get("rdp_tolerance", 0.0))

        if epsilon < 0:
            raise ValueError("epsilon must be non-negative.")
        if rapid_speed_mm_s <= 0:
            raise ValueError("rapid_speed_mm_s must be positive.")
        if connection_tolerance < 0:
            raise ValueError("connection_tolerance must be non-negative.")
        if max_2opt_passes < 1:
            raise ValueError("max_2opt_passes must be at least 1.")
        self.epsilon: float = epsilon
        self.rapid_speed_mm_s: float = rapid_speed_mm_s
        self.connection_tolerance: float = connection_tolerance
        self.max_2opt_passes: int = max_2opt_passes

    # ------------------------------------------------------------------ RDP
    @staticmethod
    def rdp(points: np.ndarray, epsilon: float) -> np.ndarray:
        """Ramer-Douglas-Peucker polyline simplification (NumPy vectorized).

        The perpendicular distance of all points of a sub-polyline is computed
        in a single vectorized operation; recursion is replaced by an explicit
        stack to avoid recursion limits.

        Args:
            points: Array of shape ``(N, 2)``.
            epsilon: Maximum allowed deviation in millimetres.

        Returns:
            Simplified array of shape ``(M, 2)`` with ``M <= N``; first and last
            points are always preserved.

        Raises:
            ValueError: If ``points`` has an invalid shape or ``epsilon`` < 0.
        """
        array = np.asarray(points, dtype=float)
        if array.ndim != 2 or array.shape[1] != 2:
            raise ValueError("points must have shape (N, 2).")
        if epsilon < 0:
            raise ValueError("epsilon must be non-negative.")
        count = array.shape[0]
        if count < 3:
            return array.copy()

        keep = np.zeros(count, dtype=bool)
        keep[0] = keep[-1] = True
        stack: List[Tuple[int, int]] = [(0, count - 1)]
        while stack:
            first, last = stack.pop()
            if last - first < 2:
                continue
            segment = array[last] - array[first]
            offsets = array[first + 1:last] - array[first]
            seg_length = float(np.hypot(segment[0], segment[1]))
            if seg_length < 1e-12:
                distances = np.hypot(offsets[:, 0], offsets[:, 1])
            else:
                distances = np.abs(segment[0] * offsets[:, 1] - segment[1] * offsets[:, 0]) / seg_length
            farthest = int(np.argmax(distances))
            if distances[farthest] > epsilon:
                split = first + 1 + farthest
                keep[split] = True
                stack.append((first, split))
                stack.append((split, last))
        return array[keep]

    # ------------------------------------------------------------------ TSP
    def tsp_2opt(
        self, contours: Sequence[np.ndarray], start_point: Optional[Point] = None
    ) -> List[np.ndarray]:
        """Reorder (and possibly reverse) contours to minimize rapid travel.

        Uses a nearest-neighbour construction followed by 2-opt improvement.
        Each contour may be traversed in either direction.

        Args:
            contours: Sequence of ``(N_i, 2)`` arrays.
            start_point: Initial scanner position; defaults to the first
                point of the first contour.

        Returns:
            New list of contours in the optimized visiting order.

        Raises:
            ValueError: If any contour has an invalid shape.
        """
        order, flips = self._solve_order(contours, start_point)
        result: List[np.ndarray] = []
        for index, flipped in zip(order, flips):
            contour = np.asarray(contours[index], dtype=float)
            result.append(contour[::-1].copy() if flipped else contour.copy())
        return result

    def _solve_order(
        self, contours: Sequence[np.ndarray], start_point: Optional[Point]
    ) -> Tuple[List[int], List[bool]]:
        """Compute visiting order and reversal flags for the contours."""
        arrays = [np.asarray(c, dtype=float) for c in contours]
        for array in arrays:
            if array.ndim != 2 or array.shape[1] != 2 or array.shape[0] < 1:
                raise ValueError("Every contour must have shape (N, 2) with N >= 1.")
        count = len(arrays)
        if count == 0:
            return [], []

        firsts = np.array([a[0] for a in arrays], dtype=float)
        lasts = np.array([a[-1] for a in arrays], dtype=float)
        origin = firsts[0] if start_point is None else np.asarray(start_point, dtype=float)

        # Nearest-neighbour construction (orientation-aware).
        remaining = np.ones(count, dtype=bool)
        order: List[int] = []
        flips: List[bool] = []
        position = origin
        for _ in range(count):
            idx = np.flatnonzero(remaining)
            d_first = np.hypot(*(firsts[idx] - position).T)
            d_last = np.hypot(*(lasts[idx] - position).T)
            best_first = int(np.argmin(d_first))
            best_last = int(np.argmin(d_last))
            if d_first[best_first] <= d_last[best_last]:
                chosen, flipped = int(idx[best_first]), False
            else:
                chosen, flipped = int(idx[best_last]), True
            remaining[chosen] = False
            order.append(chosen)
            flips.append(flipped)
            position = firsts[chosen] if flipped else lasts[chosen]

        # Heuristic Pruning safeguard (O(N^2) quadratic prevention):
        # If N > 100 contours: bypass 2-Opt to avoid quadratic stalls on dense geometries
        # and retain the Greedy Nearest-Neighbor order (sub-second computation).
        # If N <= 100 contours: execute 2-Opt with a strict iteration cap.
        if count > 100:
            logger.info("Contour count N=%d > 100: utilizing Greedy Nearest-Neighbor (skipping 2-Opt).", count)
            return order, flips

        max_passes = min(self.max_2opt_passes, 20 if count > 50 else 30)

        # 2-opt with reversal (segment reversal also flips contour orientation).
        def entry(pos: int) -> np.ndarray:
            return lasts[order[pos]] if flips[pos] else firsts[order[pos]]

        def exit_(pos: int) -> np.ndarray:
            return firsts[order[pos]] if flips[pos] else lasts[order[pos]]

        def dist(a: np.ndarray, b: np.ndarray) -> float:
            return math.hypot(float(a[0] - b[0]), float(a[1] - b[1]))

        for _ in range(max_passes):
            improved = False
            for i in range(count):
                for j in range(i, count):
                    prev_exit = origin if i == 0 else exit_(i - 1)
                    old_cost = dist(prev_exit, entry(i))
                    new_cost = dist(prev_exit, exit_(j))
                    if j < count - 1:
                        next_entry = entry(j + 1)
                        old_cost += dist(exit_(j), next_entry)
                        new_cost += dist(entry(i), next_entry)
                    if new_cost < old_cost - 1e-9:
                        order[i:j + 1] = order[i:j + 1][::-1]
                        flips[i:j + 1] = [not f for f in flips[i:j + 1][::-1]]
                        improved = True
            if not improved:
                break
        return order, flips

    # --------------------------------------------------------- orchestration
    def optimize(self, trajectories: Sequence[TrajectoryBlock]) -> List[TrajectoryBlock]:
        """Simplify G1 contours and reorder them to minimize rapid travel.

        Original G0 blocks are discarded and regenerated between the
        reordered contours. Consecutive connected G1 blocks with equal speed
        form a contour.

        Args:
            trajectories: Blocks produced by :class:`core.GCodeParser.GCodeParser`.

        Returns:
            Optimized list of G0/G1 blocks.

        Raises:
            TypeError: If an element is not a ``TrajectoryBlock``.
        """
        for block in trajectories:
            if not isinstance(block, TrajectoryBlock):
                raise TypeError("trajectories must contain TrajectoryBlock instances.")
        if not trajectories:
            return []

        origin: Point = trajectories[0].start
        contours, speeds = self._extract_contours(trajectories)
        if not contours:
            logger.warning("No G1 blocks found; nothing to optimize.")
            return []

        simplified = [self.rdp(contour, self.epsilon) for contour in contours]
        nodes_before = sum(len(c) for c in contours)
        nodes_after = sum(len(c) for c in simplified)

        before_travel = self._travel_length(contours, origin)
        order, flips = self._solve_order(simplified, origin)

        result: List[TrajectoryBlock] = []
        position: Point = origin
        ordered_contours: List[np.ndarray] = []
        for index, flipped in zip(order, flips):
            contour = simplified[index][::-1] if flipped else simplified[index]
            ordered_contours.append(contour)
            entry: Point = (float(contour[0][0]), float(contour[0][1]))
            if np.hypot(entry[0] - position[0], entry[1] - position[1]) > self.connection_tolerance:
                result.append(TrajectoryBlock("G0", position, entry, self.rapid_speed_mm_s))
            for a, b in zip(contour[:-1], contour[1:]):
                start = (float(a[0]), float(a[1]))
                end = (float(b[0]), float(b[1]))
                if start != end:
                    result.append(TrajectoryBlock("G1", start, end, speeds[index]))
            position = (float(contour[-1][0]), float(contour[-1][1]))

        after_travel = self._travel_length(ordered_contours, origin)
        logger.info(
            "Optimized: %d -> %d nodes, rapid travel %.3f -> %.3f mm",
            nodes_before, nodes_after, before_travel, after_travel,
        )
        return result

    def _extract_contours(
        self, trajectories: Sequence[TrajectoryBlock]
    ) -> Tuple[List[np.ndarray], List[float]]:
        """Group consecutive connected, equal-speed G1 blocks into contours."""
        contours: List[np.ndarray] = []
        speeds: List[float] = []
        current: List[Point] = []
        current_speed = 0.0

        def flush() -> None:
            if len(current) >= 2:
                contours.append(np.array(current, dtype=float))
                speeds.append(current_speed)
            current.clear()

        for block in trajectories:
            if block.motion_type != "G1":
                flush()
                continue
            connected = (
                bool(current)
                and abs(block.velocity - current_speed) < 1e-9
                and np.hypot(block.start[0] - current[-1][0], block.start[1] - current[-1][1])
                <= self.connection_tolerance
            )
            if not connected:
                flush()
                current.append(block.start)
                current_speed = block.velocity
            current.append(block.end)
        flush()
        return contours, speeds

    @staticmethod
    def _travel_length(contours: Sequence[np.ndarray], origin: Point) -> float:
        """Total rapid distance when visiting contours in the given order."""
        total = 0.0
        position = np.asarray(origin, dtype=float)
        for contour in contours:
            total += float(np.hypot(*(contour[0] - position)))
            position = contour[-1]
        return total


# ==============================================================================
# Helper & Compatibility Functions (Vectorized Trajectory & Polyline Optimization)
# ==============================================================================

def simplificar_trayectoria_rdp(
    puntos: Sequence[Point],
    epsilon: float = 0.01,
) -> List[Point]:
    """Simplificación vectorial RDP de alto rendimiento basada en NumPy."""
    if len(puntos) < 3 or epsilon <= 0:
        return list(puntos)
    arr = PathOptimizer.rdp(np.asarray(puntos, dtype=float), float(epsilon))
    return [(float(x), float(y)) for x, y in arr]


def fusionar_trazos_contiguos(
    trazos: Sequence[Sequence[Point]],
    tol_union: float = 0.02,
) -> List[List[Point]]:
    """Fusiona trazos continuos contiguos y cierra bucles casi cerrados."""
    if not trazos:
        return []

    fusionados: List[List[Point]] = []
    for trazo in trazos:
        trazo_list = [tuple(p) for p in trazo]
        if fusionados and math.hypot(trazo_list[0][0] - fusionados[-1][-1][0],
                                     trazo_list[0][1] - fusionados[-1][-1][1]) <= tol_union:
            fusionados[-1].extend(trazo_list[1:])
        else:
            fusionados.append(trazo_list)

    for trazo in fusionados:
        if len(trazo) >= 3:
            dist_cierre = math.hypot(trazo[-1][0] - trazo[0][0], trazo[-1][1] - trazo[0][1])
            if 0.0001 < dist_cierre <= (tol_union * 1.5):
                trazo.append(trazo[0])

    return fusionados


def optimizar_y_unir_trazos(
    trayectorias: Sequence[Sequence[Point]],
    tol_union: float = 0.02,
    pos_inicial: Point = (0.0, 0.0),
) -> List[List[Point]]:
    """Optimiza el orden de dibujo vectorial (TSP / 2-Opt) y une segmentos contiguos."""
    valid = [np.asarray(r, dtype=float) for r in trayectorias if len(r) >= 2]
    if not valid:
        return []

    optimizer = PathOptimizer()
    ordered = optimizer.tsp_2opt(valid, start_point=pos_inicial)
    tuple_paths: List[List[Point]] = [
        [(float(x), float(y)) for x, y in contour] for contour in ordered
    ]
    return fusionar_trazos_contiguos(tuple_paths, tol_union=tol_union)

