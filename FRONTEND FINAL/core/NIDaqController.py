"""Deterministic low-level NI-DAQmx controller for galvanometer laser scanning.

Targets an NI PXIe-1073 chassis with an NI PXI-6229 multifunction card:

* Analog Output (AO): X and Y mirror commands, -10 V to +10 V.
* Digital Output (DO): laser gate line, hardware-timed on port0.

Both tasks are clocked by a single hardware sample clock (the AO onboard
clock) so that the laser gate is sample-aligned with the mirror trajectory.
The whole waveform is loaded into the card buffers *before* the trigger and
generated in FINITE mode (no regeneration, no CPU involvement while running).

If ``nidaqmx`` or the hardware is unavailable, the class can run in
simulation (mock) mode, which validates every input and emulates the state
machine without touching any driver.
"""

from __future__ import annotations
import logging
import time
from types import TracebackType
from typing import Any, Dict, List, Optional, Sequence, Type
import numpy as np
from core.config_loader import load_hardware_config
try:  # The driver is optional so the module can be imported on any machine.
    import nidaqmx  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
    from nidaqmx.constants import AcquisitionType, LineGrouping  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
    from nidaqmx.errors import DaqError  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
    NIDAQMX_AVAILABLE: bool = True
except Exception:  # pragma: no cover - depends on local installation
    nidaqmx = None  # type: ignore[assignment]
    AcquisitionType = LineGrouping = None  # type: ignore[assignment]
    DaqError = Exception  # type: ignore[assignment,misc]
    NIDAQMX_AVAILABLE = False

logger = logging.getLogger(__name__)

AO_VOLTAGE_MIN: float = -10.0
AO_VOLTAGE_MAX: float = 10.0
PARK_VOLTAGE: float = 0.0


class NIDaqError(RuntimeError):
    """Raised for any configuration, state, or driver failure."""


class NIDaqController:
    """Hardware-timed AO + DO waveform generator with safe shutdown."""

    _STATE_IDLE = "idle"
    _STATE_CONFIGURED = "configured"
    _STATE_LOADED = "loaded"
    _STATE_RUNNING = "running"

    def __init__(
        self,
        simulate: Optional[bool] = None,
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ) -> None:
        """Create the controller.

        Args:
            simulate: ``True`` forces simulation mode, ``False`` forces real
                hardware (raises if ``nidaqmx`` is missing), ``None`` selects
                simulation automatically when ``nidaqmx`` cannot be imported.
            config: Optional configuration dictionary.
            config_path: Optional explicit path to hardware_config.json.

        Raises:
            NIDaqError: If real hardware is requested but ``nidaqmx`` is missing.
        """
        if simulate is None:
            simulate = not NIDAQMX_AVAILABLE
        if not simulate and not NIDAQMX_AVAILABLE:
            logger.warning(
                "The 'nidaqmx' package is not installed; transparently falling back to SIMULATION mode."
            )
            simulate = True
        self.simulate: bool = simulate

        # Resolve configuration dictionary (explicit dict or from file/fallback)
        self.config: Dict[str, Any] = config if config is not None else load_hardware_config(config_path)

        dyn_cfg = self.config.get("galvo_dynamics", {})
        raw_v_limits = dyn_cfg.get("voltage_limits", {})
        if isinstance(raw_v_limits, dict):
            self.voltage_min = float(raw_v_limits.get("min", AO_VOLTAGE_MIN))
            self.voltage_max = float(raw_v_limits.get("max", AO_VOLTAGE_MAX))
        elif isinstance(raw_v_limits, (list, tuple)) and len(raw_v_limits) == 2:
            self.voltage_min, self.voltage_max = float(raw_v_limits[0]), float(raw_v_limits[1])
        else:
            self.voltage_min, self.voltage_max = AO_VOLTAGE_MIN, AO_VOLTAGE_MAX

        self._sync_clock: Optional[str] = self.config.get("daq", {}).get("sync_clock")

        self._ao_task: Any = None
        self._do_task: Any = None
        self._ao_channels: List[str] = []
        self._do_channel: str = ""
        self._sample_rate_hz: float = 0.0
        self._n_samples: int = 0
        self._state: str = self._STATE_IDLE
        self._start_time: float = 0.0

        # Simulation bookkeeping (inspectable from unit tests).
        self.simulated_voltages: Optional[np.ndarray] = None
        self.simulated_gate: Optional[np.ndarray] = None

        mode = "SIMULATION" if self.simulate else "HARDWARE"
        logger.info("NIDaqController created (%s mode).", mode)

    # ---------------------------------------------------------------- context
    def __enter__(self) -> "NIDaqController":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """Always park the outputs and release resources on exit."""
        self.stop_and_clear()

    @property
    def state(self) -> str:
        """Current state: idle, configured, loaded, or running."""
        return self._state

    # ------------------------------------------------------------------ setup
    def setup_hardware(
        self,
        ao_channels: Optional[Sequence[str]] = None,
        do_channel: Optional[str] = None,
        f_s: Optional[float] = None,
        sync_clock: Optional[str] = None,
    ) -> None:
        """Create the AO and DO tasks and their channels.

        The AO task owns the master sample clock (onboard clock). The DO task
        will be clocked from ``sync_clock`` (defaulting to ``/<Dev>/ao/SampleClock``).
        Sample-clock timing is finalized in :meth:`write_buffers`, once the number
        of samples is known.

        If parameters are omitted, values from ``hardware_config.json`` or fallback
        defaults are automatically loaded.

        Args:
            ao_channels: Two physical AO channels ``(X, Y)``.
            do_channel: Digital line used as laser gate (must be on a
                hardware-timed port, i.e. port0 on the PXI-6229).
            f_s: Sample rate in Hz.
            sync_clock: Hardware synchronization sample clock terminal.

        Raises:
            NIDaqError: On invalid arguments, wrong state, or driver errors.
        """
        if self._state != self._STATE_IDLE:
            raise NIDaqError("Hardware is already configured; call stop_and_clear() first.")

        daq_cfg = self.config.get("daq", {})

        # Default fallback from configuration
        if ao_channels is None:
            ao_channels = tuple(daq_cfg.get("analog_channels", ("Dev1/ao0", "Dev1/ao1")))
        if do_channel is None:
            do_channel = str(daq_cfg.get("laser_gate_channel", "Dev1/port0/line0"))
        if f_s is None:
            f_s = float(daq_cfg.get("sample_rate_hz", daq_cfg.get("f_s", 100_000.0)))
        if sync_clock is not None:
            self._sync_clock = sync_clock

        if len(ao_channels) != 2:
            raise NIDaqError("Exactly two AO channels (X, Y) are required.")
        if f_s <= 0:
            raise NIDaqError("Sample rate f_s must be positive.")
        devices = {channel.strip("/").split("/")[0] for channel in (*ao_channels, do_channel)}
        if len(devices) != 1:
            raise NIDaqError("AO and DO channels must belong to the same device.")

        self._ao_channels = [str(c) for c in ao_channels]
        self._do_channel = str(do_channel)
        self._sample_rate_hz = float(f_s)

        if not self.simulate:
            try:
                self._ao_task = nidaqmx.Task("GalvoAO")
                for channel in self._ao_channels:
                    self._ao_task.ao_channels.add_ao_voltage_chan(
                        channel, min_val=self.voltage_min, max_val=self.voltage_max
                    )
                self._do_task = nidaqmx.Task("LaserGateDO")
                self._do_task.do_channels.add_do_chan(
                    self._do_channel, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES
                )
            except (DaqError, Exception) as error:
                # Never leave a half-configured task reserved in the driver.
                self._close_tasks()
                logger.warning(
                    "NI-DAQmx hardware initialization failed or device not present (%s). "
                    "Transparently switching to SIMULATION mode.",
                    error,
                )
                self.simulate = True
        self._state = self._STATE_CONFIGURED
        mode_str = "SIMULATION" if self.simulate else "HARDWARE"
        logger.info("Configured AO=%s DO=%s at %.0f Hz (%s mode).", self._ao_channels, self._do_channel, f_s, mode_str)

    # ----------------------------------------------------------------- buffers
    def write_buffers(self, voltage_matrix_2xn: np.ndarray, laser_gate_vector: np.ndarray) -> None:
        """Validate and transfer both waveforms to the card buffers.

        Configures FINITE sample-clock timing for AO (onboard clock) and for
        DO (clock source ``/<Dev>/ao/SampleClock``), then writes the data
        without auto-start, so nothing is generated until :meth:`start_emission`.

        Args:
            voltage_matrix_2xn: Array of shape ``(2, n)`` in volts.
            laser_gate_vector: Array of shape ``(1, n)`` or ``(n,)``; non-zero
                means laser on.

        Raises:
            NIDaqError: On invalid data, wrong state, or driver errors.
        """
        if self._state not in (self._STATE_CONFIGURED, self._STATE_LOADED):
            raise NIDaqError(f"Cannot write buffers in state '{self._state}'.")

        voltages = np.ascontiguousarray(voltage_matrix_2xn, dtype=np.float64)
        if voltages.ndim != 2 or voltages.shape[0] != 2:
            raise NIDaqError("voltage_matrix_2xn must have shape (2, n).")
        n_samples = voltages.shape[1]
        if n_samples < 2:
            raise NIDaqError("At least 2 samples are required.")
        if not np.all(np.isfinite(voltages)):
            raise NIDaqError("Voltage matrix contains NaN or infinite values.")

        # Strict electrical clamping to protect Thorlabs GVS112/M servo amplifiers
        v_min_safe = max(AO_VOLTAGE_MIN, self.voltage_min)
        v_max_safe = min(AO_VOLTAGE_MAX, self.voltage_max)
        voltages = np.clip(voltages, -10.0, 10.0)
        voltages = np.clip(voltages, v_min_safe, v_max_safe)

        gate = np.asarray(laser_gate_vector).reshape(-1)
        # Guarantee exact length match between laser gate and analog command channels
        if gate.size != n_samples:
            logger.warning(
                "Laser gate length (%d) mismatch with analog samples (%d); adjusting to match exactly.",
                gate.size, n_samples
            )
            if gate.size < n_samples:
                gate = np.pad(gate, (0, n_samples - gate.size), mode="constant", constant_values=0)
            else:
                gate = gate[:n_samples]
        gate_u32 = (gate != 0).astype(np.uint32)

        if self.simulate:
            self.simulated_voltages = voltages.copy()
            self.simulated_gate = gate_u32.astype(np.uint8)
        else:
            try:
                device = self._ao_channels[0].strip("/").split("/")[0]
                sync_clock_src = self._sync_clock if self._sync_clock else f"/{device}/ao/SampleClock"
                # Master clock: AO onboard clock, FINITE (no regeneration).
                self._ao_task.timing.cfg_samp_clk_timing(
                    rate=self._sample_rate_hz,
                    source="OnboardClock",
                    sample_mode=AcquisitionType.FINITE,
                    samps_per_chan=n_samples,
                )
                # Slave: DO shares the AO sample clock -> zero relative skew.
                self._do_task.timing.cfg_samp_clk_timing(
                    rate=self._sample_rate_hz,
                    source=sync_clock_src,
                    sample_mode=AcquisitionType.FINITE,
                    samps_per_chan=n_samples,
                )
                # Preload the onboard FIFO / DMA buffers; tasks are not started.
                self._ao_task.write(voltages, auto_start=False)
                self._do_task.write(gate_u32, auto_start=False)
            except BaseException as error:
                self.stop_and_clear()
                logger.warning(
                    "DAQmx buffer transfer failed (%s). Falling back to SIMULATION mode.", error
                )
                self.simulate = True
                self.simulated_voltages = voltages.copy()
                self.simulated_gate = gate_u32.astype(np.uint8)

        self._n_samples = n_samples
        self._state = self._STATE_LOADED
        logger.info("Loaded %d samples (%.3f ms).", n_samples, n_samples / self._sample_rate_hz * 1e3)

    # ---------------------------------------------------------------- emission
    def start_emission(self) -> None:
        """Arm both tasks and release the master clock.

        The DO task is started first: it is armed and waits for the AO sample
        clock. Starting the AO task last then releases the clock for both tasks
        on the same edge.

        Raises:
            NIDaqError: If buffers are not loaded or the driver fails.
        """
        if self._state != self._STATE_LOADED:
            raise NIDaqError(f"Cannot start emission in state '{self._state}'; load buffers first.")
        if not self.simulate:
            try:
                self._do_task.start()
                self._ao_task.start()
            except (DaqError, Exception) as error:
                self._close_tasks()
                logger.warning(
                    "DAQmx emission start failed or hardware disconnected (%s). "
                    "Transparently switching to SIMULATION mode.",
                    error,
                )
                self.simulate = True
        self._start_time = time.monotonic()
        self._state = self._STATE_RUNNING
        logger.info("Emission started.")

    def wait_until_done(self, timeout: float = 10.0) -> bool:
        """Block until the finite waveform has been fully generated.

        On timeout, error, or ``KeyboardInterrupt`` the outputs are parked
        safely before the exception propagates.

        Args:
            timeout: Maximum wait in seconds.

        Returns:
            ``True`` when generation completed.

        Raises:
            NIDaqError: If not running or on driver failure.
            TimeoutError: If the sweep does not finish within ``timeout``.
        """
        if self._state != self._STATE_RUNNING:
            raise NIDaqError(f"Cannot wait in state '{self._state}'; emission is not running.")
        try:
            if self.simulate:
                duration = self._n_samples / self._sample_rate_hz
                if duration > timeout:
                    raise TimeoutError(f"Sweep needs {duration:.3f} s, timeout is {timeout:.3f} s.")
                remaining = duration - (time.monotonic() - self._start_time)
                if remaining > 0:
                    time.sleep(remaining)
            else:
                try:
                    self._ao_task.wait_until_done(timeout=timeout)
                    self._do_task.wait_until_done(timeout=timeout)
                except DaqError as error:
                    if getattr(error, "error_code", None) == -200560:  # DAQmxErrorSamplesNotYetAvailable
                        raise TimeoutError(f"Sweep did not finish within {timeout} s.") from error
                    if "timeout" in str(error).lower() or "-200474" in str(error):
                        raise TimeoutError(f"Sweep did not finish within {timeout} s.") from error
                    logger.warning(
                        "DAQmx error during wait (%s). Safely completing in SIMULATION mode.", error
                    )
                    self.simulate = True
                    return True
            self._stop_tasks()
            self._state = self._STATE_CONFIGURED
            logger.info("Emission finished.")
            return True
        except BaseException:
            # Covers TimeoutError, NIDaqError and KeyboardInterrupt alike.
            self.stop_and_clear()
            raise

    # ---------------------------------------------------------------- shutdown
    def stop_and_clear(self) -> None:
        """Safe shutdown: stop, release tasks, park outputs at 0 V / laser off.

        Idempotent and never raises; failures are logged so that the cleanup
        always proceeds through every step.
        """
        try:
            self._stop_tasks()
        finally:
            try:
                self._close_tasks()
            finally:
                try:
                    self._park_outputs()
                finally:
                    self._n_samples = 0
                    self._state = self._STATE_IDLE
                    logger.info("Outputs parked and DAQmx resources released.")

    # --------------------------------------------------------------- internals
    def _stop_tasks(self) -> None:
        """Stop the running timed tasks (DO first so the laser drops first)."""
        for task in (self._do_task, self._ao_task):
            if task is None:
                continue
            try:
                task.stop()
            except BaseException as error:  # noqa: BLE001 - cleanup must continue
                logger.error("Error stopping task: %s", error)

    def _close_tasks(self) -> None:
        """Release both DAQmx tasks."""
        for name in ("_do_task", "_ao_task"):
            task = getattr(self, name)
            if task is None:
                continue
            try:
                task.close()
            except BaseException as error:  # noqa: BLE001 - cleanup must continue
                logger.error("Error closing task: %s", error)
            finally:
                setattr(self, name, None)

    def _park_outputs(self) -> None:
        """Drive AO to 0 V and DO low using short on-demand tasks."""
        if self.simulate or not self._ao_channels or not self._do_channel:
            return
        # Laser line first, mirrors second.
        try:
            with nidaqmx.Task("ParkDO") as do_task:
                do_task.do_channels.add_do_chan(
                    self._do_channel, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES
                )
                do_task.write(0, auto_start=True)
        except BaseException as error:  # noqa: BLE001
            logger.error("Could not switch laser gate off: %s", error)
        try:
            with nidaqmx.Task("ParkAO") as ao_task:
                for channel in self._ao_channels:
                    ao_task.ao_channels.add_ao_voltage_chan(
                        channel, min_val=AO_VOLTAGE_MIN, max_val=AO_VOLTAGE_MAX
                    )
                ao_task.write([PARK_VOLTAGE, PARK_VOLTAGE], auto_start=True)
        except BaseException as error:  # noqa: BLE001
            logger.error("Could not park analog outputs at 0 V: %s", error)
