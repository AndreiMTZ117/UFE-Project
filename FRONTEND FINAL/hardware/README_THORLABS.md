# THORLABS GVS112/M & NI PXI-6229 INTEGRATION MANUAL
**Project:** Fiber Laser Control Software for Polymer Processing  
**Host Institution:** Institute of Photonics and Electronics (ÚFE AV ČR), Czech Academy of Sciences, Prague  
**Author / Developer:** Andrei Martínez Bahena (Residente Profesional TecNM / ÚFE AV ČR)  
**Revision:** 1.0.0 (Production Release)  
**Target Hardware:** NI PXIe-1073 Chassis, NI PXI-6229 DAQ, Thorlabs GVS112/M Dual-Axis Galvo  
**Optics:** F-Theta Scan Lens (f = 163 mm, Working Area: 100 × 100 mm, 1940–2050 nm Thulium Fiber Laser)

---

## 1. System Overview & Package Architecture

The laser steering application is structured as a modular Python package adhering to strict separation between the graphical human-machine interface (HMI), computer-aided manufacturing (CAM) trajectory planning, relational data persistence, and deterministic hardware abstraction layers (HAL).

```text
FRONTEND FINAL/
│
├── iniciar_interfaz.py            # Primary application entry point (Cyber-Brutalist CustomTkinter HMI)
├── test_system_full.py            # 8-phase end-to-end integration test harness
├── setup_environment.ps1          # Automated PowerShell deployment & dependency setup
├── requirements.txt               # Pinned Python package dependencies
├── visualizar_comparativa.py      # CAD vs. CAM comparative visualization tool
│
├── core/
│   ├── CADConverter.py            # Automated DXF-to-Gcode conversion engine (FreeCAD CLI wrapper)
│   ├── GCodeParser.py             # ISO 6983 G-code parser & TrajectoryBlock builder
│   ├── PathOptimizer.py           # Path optimizer with RDP pruning & 2-Opt TSP solver
│   ├── GalvoSignalGenerator.py    # Deterministic waveform generation (100 kS/s) & optical delays
│   ├── NIDaqController.py         # Hardware-timed NI-DAQmx streaming engine & mock loopback
│   ├── config_loader.py           # Centralized hardware configuration loader & fallback validator
│   ├── generador_trayectorias.py  # Geometric trajectory generation utilities
│   └── lector_dxf.py              # Recursive DXF entity extraction via ezdxf
│
├── hardware/
│   ├── hardware_config.json       # Canonical DAQ channels, calibration (0.200 V/mm), and timing limits
│   ├── config_galvo.py            # Galvo kinematic limits, scan field, and default delays
│   ├── controlador_thorlabs.py    # Hardware driver abstraction for Thorlabs GVS112/M
│   ├── simulador_thorlabs.py      # High-fidelity virtual kinematic simulation engine
│   ├── README_THORLABS.md         # Hardware deployment manual (English)
│   └── README_THORLABS_CS.md      # Hardware deployment manual (Czech)
│
├── database/
│   ├── gestor_db.py               # SQLite3 engine with Write-Ahead Logging (WAL) & schema migrations
│   ├── recetas.py                 # Polymer recipe persistence (PMMA, PC, Nylon, PEEK)
│   ├── trazabilidad.py            # Production audit trail & cycle logging (historial_produccion)
│   └── laser_system.db            # Persistent SQLite3 database file
│
├── interfaz/
│   ├── interfaz_app.py            # Main CustomTkinter UI frame & lifecycle coordinator
│   ├── barra_superior.py          # Status bar, mode selector, and system clock
│   ├── panel_general.py           # Left control panel (execution controls, manual jogs)
│   ├── panel_configuracion.py     # Kinematics, optical delay & laser parameter tuning panel
│   ├── panel_derecho.py           # Right panel with tabbed recipe management & audit log
│   ├── renderizado_dual.py        # Vector preview canvas (CAD original vs. Galvo output space)
│   ├── terminal_flotante.py       # Draggable floating diagnostic & logging console
│   ├── conexion_interfaz.py       # Asynchronous threading bridge (PuenteLaser) between GUI and HAL
│   ├── constantes.py              # UI color palette, font styles & layout constants
│   ├── i18n.py                    # Multi-language internationalization (Spanish, English, Czech)
│   └── fonts/                     # Embedded typography (BrunoAce-Regular, Teachers-Regular)
│
├── dxf/                           # Production DXF vector designs (test geometries)
└── gcode/                         # Pre-compiled ISO 6983 G-code test trajectories
```

---

## 2. Automated Environment Setup & Dependencies

The host workstation inside the ÚFE laser bay requires a 64-bit Windows environment (Windows 10/11) with NI-DAQmx Runtime 21.0 or higher installed.

### 2.1 Automated Deployment (PowerShell)
Open an elevated PowerShell terminal (Run as Administrator), navigate to the project root directory, and execute:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\setup_environment.ps1
```

The script performs the following four-stage validation pipeline:
1. **FreeCAD CLI Verification:** Detects `FreeCADcmd.exe` in the system `PATH`. If missing, it scans standard installation paths (`%LOCALAPPDATA%`, `%ProgramFiles%`, `%ProgramFiles(x86)%`) and persistently registers the binary directory into the User `PATH`.
2. **Python Runtime Check:** Verifies that Python 3.10+ (64-bit) is installed and available.
3. **Dependency Installation:** Automatically upgrades `pip` and installs all pinned packages from `requirements.txt`.
4. **System Health Self-Check:** Validates FreeCAD CLI header output and executes an automated multi-module diagnostic import test (`ezdxf`, `numpy`, `scipy`, `nidaqmx`, `customtkinter`).

### 2.2 Dependency Manifest (`requirements.txt`)
```text
# Graphical User Interface (Cyber-Brutalist HMI)
customtkinter>=5.2.0

# Numerical Computing & Spatial CAM Discretization
numpy>=1.24.0
scipy>=1.10.0

# CAD Geometric Vector Processing (DXF)
ezdxf>=1.1.0

# Instrumentation & Hardware-Timed DAQ Control (National Instruments)
nidaqmx>=0.9.0
```

> [!NOTE]
> Legacy packages (`matplotlib`, `pyqtgraph`, `PyQt5`, `pyserial`, `Pillow`) have been completely superseded. Vector rendering runs directly on native CustomTkinter canvases, and DAQ streaming executes directly via the low-level NI-DAQmx C driver (`nicaiu.dll`).

---

## 3. Hardware Interconnection & DAQ Pinout Mapping

The system utilizes an **NI PXI-6229** Multifunction I/O module housed within an **NI PXIe-1073** chassis. Signals are routed through an **NI SHC68-68-EPM** double-shielded cable to an **SCB-68A** noise-rejecting connector block.

```text
+-------------------+      NI SHC68-68-EPM      +------------------+
|    NI PXI-6229    | =======================> |    NI SCB-68A    |
| (Slot 2, PXIe-10) |   Shielded 68-Pin Cable   | Breakout Block   |
+-------------------+                           +--------+---------+
                                                         |
         +-----------------------------------------------+
         |
         |--> Pin 22 (Dev1/ao0) --------> Thorlabs Driver X: Command Input (+) [Pin 1]
         |--> Pin 55 (AO GND) ----------> Thorlabs Driver X: Command Input (-) [Pin 2]
         |
         |--> Pin 21 (Dev1/ao1) --------> Thorlabs Driver Y: Command Input (+) [Pin 1]
         |--> Pin 54 (AO GND) ----------> Thorlabs Driver Y: Command Input (-) [Pin 2]
         |
         |--> Pin 52 (Dev1/port0/line0) -> High-Speed Gate Buffer / Optocoupler (+)
         |--> Pin 53 (DGND) ------------> Laser Modulation Common Return (-)
         |
         | [Optional Closed-Loop Hardware Feedback Tracking via Differential AI]
         |--> Pin 68 (Dev1/ai0+) -------> Thorlabs Driver X: Position Output (+) [Pin 3]
         |--> Pin 34 (Dev1/ai8 / ai0-) -> Thorlabs Driver X: Position Output (-) [Pin 4]
         |--> Pin 33 (Dev1/ai1+) -------> Thorlabs Driver Y: Position Output (+) [Pin 3]
         +--> Pin 66 (Dev1/ai9 / ai1-) -> Thorlabs Driver Y: Position Output (-) [Pin 4]
```

### 3.1 SCB-68A Terminal Connections Table

| SCB-68A Terminal | Signal Name | Description | Thorlabs GVS112/M / Laser Connection |
| :--- | :--- | :--- | :--- |
| **Pin 22** | `Dev1/ao0` | Analog Output 0 (X-Axis deflection command) | Driver X, J4 Pin 1: Command Input (+) |
| **Pin 55** | `AO GND` | Analog Ground (Reference for AO0) | Driver X, J4 Pin 2: Command Input (-) |
| **Pin 21** | `Dev1/ao1` | Analog Output 1 (Y-Axis deflection command) | Driver Y, J4 Pin 1: Command Input (+) |
| **Pin 54** | `AO GND` | Analog Ground (Reference for AO1) | Driver Y, J4 Pin 2: Command Input (-) |
| **Pin 52** | `Dev1/port0/line0` | Digital Output (Hardware-timed Laser Gate) | Laser Gate Driver Input (TTL 5V = ON, 0V = OFF) |
| **Pin 53** | `DGND` | Digital Ground | Laser Modulation Common Return (-) |
| **Pin 68** | `Dev1/ai0` (+) | Analog Input 0 Positive (X Position Monitor) | Driver X, J4 Pin 3: Position Output (+) |
| **Pin 34** | `Dev1/ai8` / `ai0` (-) | Analog Input 0 Negative (Differential return) | Driver X, J4 Pin 4: Position Output (-) |
| **Pin 33** | `Dev1/ai1` (+) | Analog Input 1 Positive (Y Position Monitor) | Driver Y, J4 Pin 3: Position Output (+) |
| **Pin 66** | `Dev1/ai9` / `ai1` (-) | Analog Input 1 Negative (Differential return) | Driver Y, J4 Pin 4: Position Output (-) |
| **Chassis Lug** | `SHIELD` | Cable Outer Braid Shield | Enclosure Star-Ground Grounding Lug |

### 3.2 Thorlabs Servo Driver Board Configuration
Each GVS112/M driver board is factory-tuned for its matched galvo rotor. Ensure the following jumper and power configurations:
- **Input Mode:** Differential configuration (J4 Pin 1 = Signal +, J4 Pin 2 = Signal -). **Do not tie Pin 2 to Local Ground on the driver board**; maintain the return reference directly to `AO GND` on the NI SCB-68A to eliminate ground loops.
- **Power Supply:** Connect a linear DC power supply providing ±15.0 VDC at ≥ 3.0 A per channel. Ensure ripple voltage does not exceed 10 mV RMS.
- **Heatsinking:** Both driver boards must remain firmly bolted to the enclosure's aluminum heatsink. The internal thermal protection trips if the heatsink temperature exceeds 70 °C.

---

## 4. Optical Calibration & Configuration (`hardware_config.json`)

The mathematical conversion between metric coordinates (mm) and drive voltages (V) is determined by the effective focal length of the telecentric F-Theta scan lens (**f = 163 mm**, working area **100 × 100 mm**, corresponding to **-50 mm to +50 mm** on each axis).

The nominal full-scale voltage span of the NI PXI-6229 DAC is **±10.0 V**. Therefore, the canonical spatial gain factor is:

> **k = 10.0 V / 50.0 mm = 0.200 V/mm**

For a commanded displacement *s* (in mm), the target voltage generated by the DAQ card is:

> **V(s) = s × k = s × 0.200 V/mm**

Under this optical geometry (f = 163 mm), the optical deflection angle of the scan beam is:

> **θ_opt = s / f**

The corresponding mechanical angular deflection of each galvo rotor mirror is:

> **θ_mech = θ_opt / 2 = s / (2 × f)**

Because optical reflection doubles the angular deflection of the incident beam (2 × θ_mech = θ_opt), this optical gain relationship precisely matches the factory-calibrated sensitivity of the Thorlabs GVS112/M driver board (0.5 rad/V optical deflection per commanded volt).

### 4.1 Canonical Hardware Configuration Schema (`hardware/hardware_config.json`)

```json
{
  "volts_per_mm": 0.200,
  "voltage_limits": {
    "min": -10.0,
    "max": 10.0
  },
  "daq": {
    "device_name": "Dev1",
    "analog_channels": [
      "Dev1/ao0",
      "Dev1/ao1"
    ],
    "laser_gate_channel": "Dev1/port0/line0",
    "ai_channels": [
      "Dev1/ai0",
      "Dev1/ai1"
    ],
    "ai_terminal_config": "DIFF",
    "sample_rate_hz": 100000.0,
    "sync_clock": "/Dev1/ao/SampleClock",
    "feedback_sign_x": 1,
    "feedback_sign_y": 1,
    "feedback_offset_x_v": 0.0,
    "feedback_offset_y_v": 0.0
  },
  "cad_cam": {
    "freecad_cmd": "FreeCADcmd",
    "timeout_seconds": 30,
    "rdp_tolerance": 0.0
  }
}
```

### 4.2 Galvo Dynamic Settling Delays
To compensate for galvo rotor inertia and optical response times, characteristic delays (configured in recipes and kinematics) are injected deterministically by `GalvoSignalGenerator`:
- `jump_delay_us` (default: 100–150 µs): Mechanical settling time following a high-speed non-marking jump (G0).
- `mark_delay_us` (default: 20–50 µs): Settling dwell at the end of a cutting/welding contour (G1) before the next move.
- `laser_on_delay_us` (default: 20–50 µs): Optical advance compensation allowing the mirrors to reach terminal velocity before laser emission begins.
- `laser_off_delay_us` (default: 20–30 µs): Extinction compensation extinguishing the beam before mirror deceleration.

---

## 5. Commissioning Protocol & Safety Verification

Follow this ordered sequence before powering up the high-power thulium fiber laser source:

```text
[Step 1: Visual Inspection] ---> [Step 2: Automated 8-Phase Test] ---> [Step 3: Driver DC Power]
                                                                                |
[Step 6: Production Run]   <--- [Step 5: Pilot Laser Beam]       <--- [Step 4: Oscilloscope Check]
```

### Step 1: Visual and Mechanical Inspection
1. Remove the protective lens cap from the F-Theta scan objective.
2. Verify that the fume extraction / exhaust ventilation system beneath the laser enclosure floor is powered on and pulling air.
3. Confirm that the safety enclosure interlock door switches are closed and armed.

### Step 2: Automated End-to-End System Validation Battery
Execute the automated test suite from the project root:

```powershell
python test_system_full.py
```

**Verification Checklist (All 8 Phases Must Pass):**
- **Phase 1 (Environment):** Python runtime, CustomTkinter, and NI-DAQmx connectivity verified.
- **Phase 2 (CAD Ingestion):** Automated DXF to G-code parsing via `CADConverter` and `GCodeParser`.
- **Phase 3 (Optimization):** RDP curve preservation and 2-Opt TSP path minimization verified.
- **Phase 4 (Waveforms):** Discretization at 100 kS/s (Δt = 10.0 µs), clamping strictly inside [-10.0 V, +10.0 V], and laser duty cycle verified.
- **Phase 5 (Hardware & E-STOP):** Hardware FIFO configuration, buffer write, and instantaneous safe park to 0.0 V on emergency stop.
- **Phase 6 (Database):** SQLite3 Write-Ahead Logging (`PRAGMA journal_mode=WAL;`), recipes, and production audit log verification.
- **Phase 7 (Threading & Telemetry):** Non-blocking background worker thread (`PuenteLaser`) and real-time telemetry streaming verified.
- **Phase 8 (Integrity):** Safe cleanup of all temporary execution artifacts.

*Expected Output:*
```text
STATUS: ALL SYSTEM CRITICAL MODULES OPERATIONAL AND HARDENED.
```

### Step 3: Galvo Driver Power-Up Sequence
1. Switch on the ±15.0 VDC linear regulated power supply.
2. Confirm that the green status LEDs on both Thorlabs driver boards illuminate steadily.
3. Check that both mirrors instantly center to optical home (0.000 V).
4. Gently touch the galvo motor housings; no high-frequency vibration, audible hum, or excessive heating should be present.

### Step 4: Full Pipeline Execution with Oscilloscope
Connect oscilloscope probes to `Dev1/ao0` (Channel 1), `Dev1/ao1` (Channel 2), and `Dev1/port0/line0` (Channel 3) on the SCB-68A block. Run a diagnostic test cycle or comparative preview:

```powershell
python test_system_full.py
```

**Verification Criteria:**
- Sample period Δt = 10.0 µs (100 kS/s).
- Clean corner transitions with zero ringing or overshoot.
- Digital laser modulation (`Dev1/port0/line0`) drops to 0.0 V (TTL LOW) during all rapid transit jumps (G0).

### Step 5: Low-Power Pilot Laser Beam Alignment
1. Engage the red pilot diode (635 nm).
2. Execute a calibrated square pattern (50.0 × 50.0 mm) onto a thermally sensitive alignment target.
3. Measure physical dimensions with a calibrated digital dial caliper.
4. If dimensional error exceeds ±0.05 mm, recalibrate `volts_per_mm` in `hardware_config.json`:

> **k_new = k_current × (Nominal Length / Measured Length)**

### Step 6: Production Run Authorization
Launch the production graphical interface:

```powershell
python iniciar_interfaz.py
```

1. Select the validated polymer recipe from the recipe dropdown (e.g., `Acrylic – Standard`, `Polycarbonate – High Precision`, or `Nylon – Fast Cutting`).
2. Load the target DXF vector design (or enter G-code).
3. Verify that the dual-canvas visualizer displays the trajectory within the working envelope (green bounds).
4. Press **START (EJECUTAR)** to begin synchronized hardware-timed processing. In case of anomaly, hit **EMERGENCY STOP (PARADA DE EMERGENCIA)** for instantaneous beam shutoff and galvo park.

---

## 6. Technical Support & System Diagnostics

- **Author / Developer:** Andrei Martínez Bahena (Residente Profesional TecNM / Centro de Investigación ÚFE AV ČR).
- **Host Institution:** Institute of Photonics and Electronics of the Czech Academy of Sciences (*Ústav fotoniky a elektroniky AV ČR, v. v. i.*).
- **Department:** Department of Optical Fiber Lasers and Non-Linear Optics (*Oddělení vláknových laserů a nelineární optiky*).
- **Address:** Chaberská 1014/57, 182 00 Praha 8, Czech Republic.
- **Reference Documentation:** System architecture, database migrations, and UML schemas are available in project documentation and unit test suites.
