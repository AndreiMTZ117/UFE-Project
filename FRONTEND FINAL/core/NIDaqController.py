"""deterministic ni-daqmx controller for galvo laser scanning"""

from __future__ import annotations
import logging
import time
from types import TracebackType
from typing import Any, Dict, List, Optional, Sequence, Type
import numpy as np
from core.config_loader import ConfigError, get_daq_identity, get_volts_per_mm, load_hardware_config
try:  #optional driver import
    import nidaqmx  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
    from nidaqmx.constants import AcquisitionType, LineGrouping  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
    from nidaqmx.errors import DaqError  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
    NIDAQMX_AVAILABLE: bool = True
except Exception:  # pragma: no cover - depends on local installation
    nidaqmx = None  # type: ignore[assignment]
    AcquisitionType = LineGrouping = None  # type: ignore[assignment]
    DaqError = Exception  # type: ignore[assignment,misc]
    NIDAQMX_AVAILABLE = False

try:  #optional feedback imports
    from nidaqmx.constants import TerminalConfiguration, READ_ALL_AVAILABLE  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
except Exception:  # pragma: no cover - depends on local installation
    TerminalConfiguration = None  # type: ignore[assignment]
    READ_ALL_AVAILABLE = -1  # type: ignore[assignment]

logger = logging.getLogger(__name__)

AO_VOLTAGE_MIN: float = -10.0
AO_VOLTAGE_MAX: float = 10.0
PARK_VOLTAGE: float = 0.0


class NIDaqError(RuntimeError):
    """raised for configuration or driver failure"""


class NIDaqController:
    """hardware-timed ao and do waveform generator"""

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
        """create controller instance"""
        if simulate is None:
            daq_probe = probe_daq_hardware()
            simulate = not daq_probe["available"]
            if simulate:
                logger.info(
                    "Physical NI-DAQmx hardware not detected (%s); operating in SIMULATION mode.",
                    daq_probe["description"],
                )
        elif not simulate:
            daq_probe = probe_daq_hardware()
            if not daq_probe["available"]:
                logger.warning(
                    "Physical hardware requested but unavailable (%s); falling back to SIMULATION mode.",
                    daq_probe["description"],
                )
                simulate = True
        self.simulate: bool = simulate

        #resolve configuration dictionary
        self.config: Dict[str, Any] = config if config is not None else load_hardware_config(config_path)

        raw_v_limits = self.config.get("voltage_limits") or self.config.get("galvo_dynamics", {}).get("voltage_limits", {})
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

        #simulation state
        self.simulated_voltages: Optional[np.ndarray] = None
        self.simulated_gate: Optional[np.ndarray] = None

        #optional hardware feedback tracking
        self._ai_task: Any = None
        self.feedback_active: bool = False
        self._ai_channels: List[str] = []

        mode = "SIMULATION" if self.simulate else "HARDWARE"
        logger.info("NIDaqController created (%s mode).", mode)

    #context
    def __enter__(self) -> "NIDaqController":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """park outputs and release resources on exit"""
        self.stop_and_clear()

    @property
    def state(self) -> str:
        """current state of controller"""
        return self._state

    #setup
    def setup_hardware(
        self,
        ao_channels: Optional[Sequence[str]] = None,
        do_channel: Optional[str] = None,
        f_s: Optional[float] = None,
        sync_clock: Optional[str] = None,
    ) -> None:
        """create ao and do tasks and channels"""
        if self._state != self._STATE_IDLE:
            raise NIDaqError("Hardware is already configured; call stop_and_clear() first.")

        daq_cfg = self.config.get("daq", {})

        #fallback from configuration (device identity must come from hardware_config.json)
        if ao_channels is None or do_channel is None:
            try:
                identity = get_daq_identity(self.config)
            except ConfigError as error:
                raise NIDaqError(str(error)) from error
            if ao_channels is None:
                ao_channels = tuple(identity["analog_channels"])
            if do_channel is None:
                do_channel = identity["laser_gate_channel"]
        if f_s is None:
            f_s = float(daq_cfg["sample_rate_hz"])
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
                #cleanup partial tasks on error
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

    #buffers
    def write_buffers(self, voltage_matrix_2xn: np.ndarray, laser_gate_vector: np.ndarray) -> None:
        """validate and transfer waveforms to card buffers"""
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

        #clamp voltages to protect servo amplifiers
        v_min_safe = max(AO_VOLTAGE_MIN, self.voltage_min)
        v_max_safe = min(AO_VOLTAGE_MAX, self.voltage_max)
        voltages = np.clip(voltages, -10.0, 10.0)
        voltages = np.clip(voltages, v_min_safe, v_max_safe)

        gate = np.asarray(laser_gate_vector).reshape(-1)
        #ensure exact length match between gate and analog channels
        if gate.size != n_samples:
            logger.warning(
                "Laser gate length (%d) mismatch with analog samples (%d); adjusting to match exactly.",
                gate.size, n_samples
            )
            if gate.size < n_samples:
                gate = np.pad(gate, (0, n_samples - gate.size), mode="constant", constant_values=0)
            else:
                gate = gate[:n_samples]
        gate_bool = (gate != 0).astype(bool)

        if self.simulate:
            self.simulated_voltages = voltages.copy()
            self.simulated_gate = gate_bool.astype(np.uint8)
        else:
            try:
                device = self._ao_channels[0].strip("/").split("/")[0]
                sync_clock_src = self._sync_clock if self._sync_clock else f"/{device}/ao/SampleClock"
                #master clock ao onboard clock
                self._ao_task.timing.cfg_samp_clk_timing(
                    rate=self._sample_rate_hz,
                    source="OnboardClock",
                    sample_mode=AcquisitionType.FINITE,
                    samps_per_chan=n_samples,
                )
                #slave do shares ao sample clock
                self._do_task.timing.cfg_samp_clk_timing(
                    rate=self._sample_rate_hz,
                    source=sync_clock_src,
                    sample_mode=AcquisitionType.FINITE,
                    samps_per_chan=n_samples,
                )
                #preload fifo and dma buffers
                self._ao_task.write(voltages, auto_start=False)
                self._do_task.write(gate_bool, auto_start=False)
            except BaseException as error:
                self.stop_and_clear()
                logger.warning(
                    "DAQmx buffer transfer failed (%s). Falling back to SIMULATION mode.", error
                )
                self.simulate = True
                self.simulated_voltages = voltages.copy()
                self.simulated_gate = gate_bool.astype(np.uint8)

        self._n_samples = n_samples
        self._state = self._STATE_LOADED
        logger.info("Loaded %d samples (%.3f ms).", n_samples, n_samples / self._sample_rate_hz * 1e3)

    #hardware feedback
    def _feedback_cfg(self) -> Dict[str, Any]:
        """resolve feedback settings from daq config section"""
        daq_cfg = self.config.get("daq", {})
        identity = get_daq_identity(self.config)
        return {
            "device": identity["device"],
            "channels": identity["ai_channels"][:2],
            "terminal": str(daq_cfg["ai_terminal_config"]).strip().upper(),
            "sign_x": -1.0 if float(daq_cfg["feedback_sign_x"]) < 0 else 1.0,
            "sign_y": -1.0 if float(daq_cfg["feedback_sign_y"]) < 0 else 1.0,
            "offset_x": float(daq_cfg["feedback_offset_x_v"]),
            "offset_y": float(daq_cfg["feedback_offset_y_v"]),
            "volts_per_mm": get_volts_per_mm(self.config),
        }

    #hardware feedback
    def enable_feedback(self) -> bool:
        """create optional ai task to read position monitor"""
        self.feedback_active = False
        if self.simulate or not NIDAQMX_AVAILABLE or TerminalConfiguration is None:
            return False
        if self._state != self._STATE_LOADED or self._n_samples < 2:
            return False
        cfg = self._feedback_cfg()
        if len(cfg["channels"]) != 2:
            return False
        try:
            term = TerminalConfiguration.RSE if cfg["terminal"] == "RSE" else TerminalConfiguration.DIFF
            task = nidaqmx.Task("GalvoFeedbackAI")
            self._ai_task = task
            for channel in cfg["channels"]:
                task.ai_channels.add_ai_voltage_chan(
                    channel, terminal_config=term, min_val=AO_VOLTAGE_MIN, max_val=AO_VOLTAGE_MAX
                )
            sync_clock_src = self._sync_clock if self._sync_clock else f"/{cfg['device']}/ao/SampleClock"
            task.timing.cfg_samp_clk_timing(
                rate=self._sample_rate_hz,
                source=sync_clock_src,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=self._n_samples,
            )
            self._ai_channels = list(cfg["channels"])
            self.feedback_active = True
            logger.info("Hardware feedback armed on %s (%s).", self._ai_channels, cfg["terminal"])
            return True
        except BaseException as error:  #feedback is optional
            logger.warning("Hardware feedback unavailable (%s). Continuing without feedback.", error)
            self.disable_feedback()
            return False

    def read_feedback(self) -> Optional[np.ndarray]:
        """non-blocking read of feedback samples"""
        if not self.feedback_active or self._ai_task is None:
            return None
        try:
            data = self._ai_task.read(number_of_samples_per_channel=READ_ALL_AVAILABLE, timeout=0.0)
            arr = np.asarray(data, dtype=np.float64)
            if arr.ndim != 2 or arr.shape[0] != 2 or arr.shape[1] == 0:
                return None
            cfg = self._feedback_cfg()
            arr[0] = cfg["sign_x"] * (arr[0] - cfg["offset_x"])
            arr[1] = cfg["sign_y"] * (arr[1] - cfg["offset_y"])
            return arr
        except BaseException as error:  #never interrupt scan
            if "-200284" in str(error) or "-200278" in str(error) or "timeout" in str(error).lower():
                return None  #samples not yet available
            logger.warning("Hardware feedback read failed (%s). Disabling feedback.", error)
            self.disable_feedback()
            return None

    def disable_feedback(self) -> None:
        """release ai feedback task"""
        self.feedback_active = False
        task, self._ai_task = self._ai_task, None
        if task is None:
            return
        for action in (task.stop, task.close):
            try:
                action()
            except BaseException:
                pass

    #emission
    def start_emission(self) -> None:
        """arm tasks and release master clock"""
        if self._state != self._STATE_LOADED:
            raise NIDaqError(f"Cannot start emission in state '{self._state}'; load buffers first.")
        #arm feedback task first
        if self._ai_task is not None:
            try:
                self._ai_task.start()
            except BaseException as error:
                logger.warning("Feedback AI task could not start (%s). Continuing without feedback.", error)
                self.disable_feedback()
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
        """block until waveform is fully generated"""
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
                    if getattr(error, "error_code", None) == -200560:  #samples not yet available
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
            #clean up on exception
            self.stop_and_clear()
            raise

    #shutdown
    def stop_and_clear(self) -> None:
        """safe shutdown outputs at 0v and laser off"""
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

    #internals
    def _stop_tasks(self) -> None:
        """stop running timed tasks"""
        for task in (self._do_task, self._ao_task, self._ai_task):
            if task is None:
                continue
            try:
                task.stop()
            except BaseException as error:
                logger.error("Error stopping task: %s", error)

    def _close_tasks(self) -> None:
        """release daqmx tasks"""
        self.disable_feedback()
        for name in ("_do_task", "_ao_task"):
            task = getattr(self, name)
            if task is None:
                continue
            try:
                task.close()
            except BaseException as error:
                logger.error("Error closing task: %s", error)
            finally:
                setattr(self, name, None)

    def _park_outputs(self) -> None:
        """drive ao to 0v and do low"""
        if self.simulate or not self._ao_channels or not self._do_channel:
            return
        #laser line first mirrors second
        try:
            with nidaqmx.Task("ParkDO") as do_task:
                do_task.do_channels.add_do_chan(
                    self._do_channel, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES
                )
                do_task.write(False, auto_start=True)
        except BaseException as error:
            logger.error("Could not switch laser gate off: %s", error)
        try:
            with nidaqmx.Task("ParkAO") as ao_task:
                for channel in self._ao_channels:
                    ao_task.ao_channels.add_ao_voltage_chan(
                        channel, min_val=AO_VOLTAGE_MIN, max_val=AO_VOLTAGE_MAX
                    )
                ao_task.write([PARK_VOLTAGE, PARK_VOLTAGE], auto_start=True)
        except BaseException as error:
            logger.error("Could not park analog outputs at 0 V: %s", error)


def probe_daq_hardware(required_device: Optional[str] = None) -> Dict[str, Any]:
    """probe if physical daq hardware is present and operational

    if required_device is given, the configured card must be among the detected devices
    """
    info: Dict[str, Any] = {
        "available": False,
        "driver_loaded": False,
        "devices": [],
        "description": "nidaqmx Python package not installed"
    }
    if not NIDAQMX_AVAILABLE or nidaqmx is None:
        return info

    try:
        system = nidaqmx.system.System.local()
        info["driver_loaded"] = True
        devs = [d.name for d in system.devices]
        info["devices"] = devs
        if devs and required_device and required_device not in devs:
            info["description"] = (
                f"Configured DAQ device '{required_device}' not found (detected: {', '.join(devs)})"
            )
        elif devs:
            info["available"] = True
            info["description"] = f"Physical DAQ hardware detected ({', '.join(devs)})"
        else:
            info["description"] = "Driver present, 0 physical devices detected (Simulation Mode)"
    except Exception as exc:
        err_msg = str(exc).strip().splitlines()[0] if str(exc) else "driver not found"
        if "Could not find an installation of NI-DAQmx" in err_msg:
            err_msg = "nicaiu.dll missing"
        info["description"] = f"Python pkg present, NI-DAQmx C-Runtime missing ({err_msg})"

    info["is_physical"] = info["available"]
    info["label"] = info["description"]
    info["installed"] = bool(NIDAQMX_AVAILABLE and nidaqmx is not None)
    return info


def probe_feedback_hardware(config: Optional[Dict[str, Any]] = None) -> tuple:
    """probe if ai feedback channels can be opened"""
    if not NIDAQMX_AVAILABLE or TerminalConfiguration is None:
        return False, "no_driver"
    try:
        cfg = config if config is not None else load_hardware_config()
        daq_cfg = cfg.get("daq", {})
        channels = get_daq_identity(cfg)["ai_channels"][:2]
        term = (
            TerminalConfiguration.RSE
            if str(daq_cfg["ai_terminal_config"]).strip().upper() == "RSE"
            else TerminalConfiguration.DIFF
        )
        with nidaqmx.Task("ProbeFeedbackAI") as task:
            for channel in channels:
                task.ai_channels.add_ai_voltage_chan(
                    channel, terminal_config=term, min_val=AO_VOLTAGE_MIN, max_val=AO_VOLTAGE_MAX
                )
            task.read(number_of_samples_per_channel=1, timeout=1.0)
        return True, "ok"
    except BaseException as error:
        logger.info("Feedback probe failed: %s", error)
        return False, "no_device"

