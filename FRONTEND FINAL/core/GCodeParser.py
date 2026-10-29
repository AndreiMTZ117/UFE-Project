"""parse gcode files into discrete trajectory blocks"""

from __future__ import annotations

import logging
import math
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

MM_PER_INCH: float = 25.4
SECONDS_PER_MINUTE: float = 60.0

_WORD_PATTERN = re.compile(r"([A-Za-z])\s*([+-]?(?:\d+\.?\d*|\.\d+))")
_PAREN_COMMENT_PATTERN = re.compile(r"\([^)]*\)")
_VALID_LINE_PATTERN = re.compile(r"^(?:[A-Za-z]\s*[+-]?(?:\d+\.?\d*|\.\d+)\s*)+$")


class GCodeParseError(ValueError):
    """raised when gcode syntax is invalid"""


@dataclass(frozen=True)
class TrajectoryBlock:
    """single discrete motion segment"""

    motion_type: str
    start: Tuple[float, float]
    end: Tuple[float, float]
    velocity: float

    @property
    def length(self) -> float:
        """euclidean length of segment in mm"""
        return math.hypot(self.end[0] - self.start[0], self.end[1] - self.start[1])


class GCodeParser:
    """parse gcode into trajectory blocks"""

    def __init__(
        self,
        file_path: str,
        default_feed_mm_s: float = 10.0,
        rapid_speed_mm_s: float = 100.0,
        arc_tolerance_mm: float = 0.01,
    ) -> None:
        """initialize gcode parser"""
        if default_feed_mm_s <= 0 or rapid_speed_mm_s <= 0 or arc_tolerance_mm <= 0:
            raise ValueError("Speeds and arc tolerance must be strictly positive.")

        self.file_path: str = os.fspath(file_path)
        self.default_feed_mm_s: float = default_feed_mm_s
        self.rapid_speed_mm_s: float = rapid_speed_mm_s
        self.arc_tolerance_mm: float = arc_tolerance_mm

        self._x: float = 0.0
        self._y: float = 0.0
        self._feed: float = default_feed_mm_s
        self._motion: Optional[str] = None
        self._absolute: bool = True
        self._unit_scale: float = 1.0

    def parse(self) -> List[TrajectoryBlock]:
        """read and parse gcode file into trajectory blocks"""
        if not os.path.isfile(self.file_path):
            logger.error("G-code file not found: %s", self.file_path)
            raise FileNotFoundError(f"G-code file not found: {self.file_path}")

        self._reset_state()
        blocks: List[TrajectoryBlock] = []
        try:
            with open(self.file_path, "r", encoding="utf-8") as handle:
                for line_number, raw_line in enumerate(handle, start=1):
                    try:
                        blocks.extend(self._parse_line(raw_line))
                    except GCodeParseError as error:
                        raise GCodeParseError(f"Line {line_number}: {error}") from error
        except UnicodeDecodeError as error:
            logger.error("File is not valid UTF-8 text: %s", self.file_path)
            raise GCodeParseError(f"File is not a valid text G-code file: {error}") from error
        except OSError as error:
            logger.error("Cannot read file %s: %s", self.file_path, error)
            raise

        logger.info("Parsed %d trajectory blocks from %s", len(blocks), self.file_path)
        return blocks

    def _reset_state(self) -> None:
        """reset modal machine state before parsing"""
        self._x = 0.0
        self._y = 0.0
        self._feed = self.default_feed_mm_s
        self._motion = None
        self._absolute = True
        self._unit_scale = 1.0

    @staticmethod
    def _clean_line(raw_line: str) -> str:
        """strip comments block delete markers and whitespace"""
        line = _PAREN_COMMENT_PATTERN.sub("", raw_line)
        line = line.split(";", 1)[0].strip()
        if line.startswith("/"):
            line = line[1:].strip()
        if line.startswith("%"):
            return ""
        return line

    def _parse_line(self, raw_line: str) -> List[TrajectoryBlock]:
        """parse single gcode line"""
        line = self._clean_line(raw_line)
        if not line:
            return []
        if not _VALID_LINE_PATTERN.match(line):
            raise GCodeParseError(f"Invalid G-code syntax: '{line}'")

        words: List[Tuple[str, float]] = [
            (letter.upper(), float(value)) for letter, value in _WORD_PATTERN.findall(line)
        ]
        axes: dict = {}
        for letter, value in words:
            if letter == "G":
                self._handle_g_code(int(round(value)) if value == int(value) else value)
            elif letter == "F":
                if value < 0:
                    raise GCodeParseError("Negative feed rate.")
                if value > 0:
                    self._feed = value * self._unit_scale / SECONDS_PER_MINUTE
            elif letter in "XYIJ":
                axes[letter] = value * self._unit_scale

        if not any(axis in axes for axis in "XY"):
            return []
        if self._motion is None:
            raise GCodeParseError("Motion command without active G0/G1/G2/G3.")

        target_x, target_y = self._resolve_target(axes)
        start = (self._x, self._y)
        end = (target_x, target_y)

        if self._motion in ("G0", "G1"):
            blocks = self._linear_block(self._motion, start, end)
        else:
            blocks = self._arc_blocks(self._motion, start, end, axes)

        self._x, self._y = target_x, target_y
        return blocks

    def _handle_g_code(self, code: float) -> None:
        """update modal state from g word"""
        if code in (0, 1, 2, 3):
            self._motion = f"G{int(code)}"
        elif code == 20:
            self._unit_scale = MM_PER_INCH
        elif code == 21:
            self._unit_scale = 1.0
        elif code == 90:
            self._absolute = True
        elif code == 91:
            self._absolute = False
        else:
            logger.debug("Ignoring unsupported G%s", code)

    def _resolve_target(self, axes: dict) -> Tuple[float, float]:
        """compute absolute target coordinates from axis words"""
        if self._absolute:
            return axes.get("X", self._x), axes.get("Y", self._y)
        return self._x + axes.get("X", 0.0), self._y + axes.get("Y", 0.0)

    def _linear_block(
        self, motion: str, start: Tuple[float, float], end: Tuple[float, float]
    ) -> List[TrajectoryBlock]:
        """create linear block ignoring zero length moves"""
        if start == end:
            return []
        speed = self.rapid_speed_mm_s if motion == "G0" else self._feed
        return [TrajectoryBlock(motion, start, end, speed)]

    def _arc_blocks(
        self,
        motion: str,
        start: Tuple[float, float],
        end: Tuple[float, float],
        axes: dict,
    ) -> List[TrajectoryBlock]:
        """linearize g2 and g3 arcs into g1 blocks"""
        if "I" not in axes and "J" not in axes:
            raise GCodeParseError("Arc without I/J center offsets is not supported.")
        center_x = start[0] + axes.get("I", 0.0)
        center_y = start[1] + axes.get("J", 0.0)
        radius = math.hypot(start[0] - center_x, start[1] - center_y)
        if radius < 1e-12:
            raise GCodeParseError("Arc with zero radius.")

        start_angle = math.atan2(start[1] - center_y, start[0] - center_x)
        end_angle = math.atan2(end[1] - center_y, end[0] - center_x)
        clockwise = motion == "G2"
        sweep = end_angle - start_angle
        if clockwise and sweep >= 0:
            sweep -= 2.0 * math.pi
        elif not clockwise and sweep <= 0:
            sweep += 2.0 * math.pi

        max_step = 2.0 * math.acos(max(0.0, 1.0 - min(self.arc_tolerance_mm / radius, 1.0)))
        max_step = max(max_step, 1e-3)
        steps = max(1, int(math.ceil(abs(sweep) / max_step)))

        blocks: List[TrajectoryBlock] = []
        previous = start
        for index in range(1, steps + 1):
            if index == steps:
                point = end
            else:
                angle = start_angle + sweep * index / steps
                point = (center_x + radius * math.cos(angle), center_y + radius * math.sin(angle))
            blocks.extend(self._linear_block("G1", previous, point))
            previous = point
        return blocks
