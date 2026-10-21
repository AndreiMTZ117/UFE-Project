# Fiber Laser Scanning & Polymer Processing Control System
**Host Institution:** Institute of Photonics and Electronics (ÚFE AV ČR), Czech Academy of Sciences, Prague  
**Department:** Department of Optical Fiber Lasers and Non-Linear Optics  
**Author / Developer:** Andrei Martínez Bahena (Residente Profesional TecNM / Centro de Investigación ÚFE AV ČR)  
**Version:** 1.0.0 (Production Release)  
**Target Hardware:** NI PXIe-1073 Chassis, NI PXI-6229 DAQ, Thorlabs GVS112/M Dual-Axis Galvo  
**Optics:** F-Theta Scan Lens (f = 163 mm, Working Area: 100 × 100 mm, λ = 1940–2050 nm Thulium Fiber Laser)

---

## 📖 Hardware & Deployment Documentation

For detailed pinout wiring, SCB-68A terminal connections, optical calibration formulas, and lab safety commissioning procedures, refer to the specialized hardware manuals:

- 🇬🇧 **[English Hardware Integration Manual](hardware/README_THORLABS.md)**
- 🇨🇿 **[Český integrační manuál hardwaru](hardware/README_THORLABS_CS.md)**

---

## 🚀 System Overview

This software platform provides deterministic, high-speed computerized numerical control (CNC / CAM) for two-axis galvanometer laser scanning and polymer material processing (welding, cutting, and precision marking).

It integrates a modular architecture that cleanly decouples human-machine interaction, geometric path planning, hardware-timed DAQ streaming, and transactional data persistence:

```text
┌────────────────────────────────────────────────────────┐
│             Cyber-Brutalist HMI (CustomTkinter)        │
│          Dual Vector Canvas & Real-Time Telemetry      │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│          CAM & Trajectory Generation Engine            │
│  - CADConverter: Automated DXF -> ISO 6983 G-code      │
│  - GCodeParser: Rapid (G0) & Feed (G1) TrajectoryBlocks │
│  - PathOptimizer: Ramer-Douglas-Peucker & 2-Opt TSP    │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│        Deterministic Signal Discretization (HAL)       │
│  - GalvoSignalGenerator: 100 kS/s Waveform Synthesis   │
│  - Dynamic Inertial Settling Delays (Jump/Mark/Laser)  │
│  - NIDaqController: NI-DAQmx Hardware-Timed Streaming  │
│  - Instantaneous E-STOP Beam Extinction & 0V Parking   │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│       Relational Data Persistence (SQLite3 WAL)        │
│  - Material Recipes: PMMA, Polycarbonate, Nylon, PEEK  │
│  - Production Audit Trail: Operator, Geometry, Metrics │
└────────────────────────────────────────────────────────┘
```

---

## ⚡ Key Architectural Features

1. **Cyber-Brutalist HMI (`interfaz/`):**
   - Built on CustomTkinter with embedded modern typography (`BrunoAce`, `Teachers`).
   - Dual-canvas interactive vector rendering: original CAD input space vs. optical galvo target space.
   - Non-blocking asynchronous threading architecture (`PuenteLaser`) preventing UI freeze during high-frequency streaming.
   - Draggable floating diagnostic terminal with real-time log streaming.
   - Multi-language support (English, Spanish, Czech).

2. **Automated CAD/CAM Pre-Processing (`core/`):**
   - Headless background conversion of 2D DXF blueprints into standard ISO 6983 G-code via FreeCAD CLI (`FreeCADcmd.exe`).
   - Curve simplification using the Ramer-Douglas-Peucker (RDP) algorithm with zero-loss tolerance preservation.
   - Non-marking jump minimization via 2-Opt heuristic Traveling Salesperson Problem (TSP) solver (pruning transit distance in under 0.3 s for N > 100 paths).

3. **Hardware-Timed Waveform Discretization (`core/GalvoSignalGenerator.py`):**
   - High-throughput spatial-to-voltage conversion (0.200 V/mm across ±50 mm working field).
   - Strict electrical clamping to [-10.0 V, +10.0 V] analog safety envelopes.
   - Sample rate: 100 kS/s (Δt = 10.0 µs) synchronized across analog command channels (AO0/AO1) and digital laser gate line (Port0/Line0).
   - Dedicated galvo kinematic settling compensation (`jump_delay`, `mark_delay`, `laser_on_delay`, `laser_off_delay`).

4. **Hardware Abstraction Layer & Simulation (`core/NIDaqController.py`):**
   - Native integration with NI PXI-6229 and NI PXIe-1073 chassis via `nidaqmx`.
   - Optional closed-loop position readback tracking via differential analog inputs (AI0/AI1).
   - Automatic fallback to high-fidelity virtual simulation mode (`simulador_thorlabs.py`) when hardware is disconnected, allowing complete offline development and operator training.

5. **Industrial Relational Database (`database/`):**
   - SQLite3 with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`) for high concurrency and zero database locks.
   - Recipe library with factory presets for PMMA (Acrylic), Polycarbonate (PC), Nylon, and PEEK.
   - Complete audit trail (`historial_produccion`) logging operator ID, DXF file, recipe snapshot, execution duration, and cycle status (`COMPLETADO` / `ABORTADO` / `FALLO_HARDWARE`).

---

## 🛠️ Installation & Environment Setup

### Prerequisites
- **Operating System:** Windows 10 or 11 (64-bit).
- **Python:** Python 3.10+ (64-bit) in system `PATH`.
- **National Instruments Driver:** NI-DAQmx Runtime 21.0+ (`nicaiu.dll`). *(Optional for offline simulation mode)*.
- **FreeCAD CLI:** FreeCAD 0.21+ / 1.0 (`FreeCADcmd.exe`).

### Automated Deployment (PowerShell)
Open PowerShell as Administrator in the project root directory:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\setup_environment.ps1
```

The script will:
- Detect and register `FreeCADcmd.exe` in the User `PATH`.
- Validate the Python 64-bit runtime version.
- Upgrade `pip` and install all dependencies from `requirements.txt`.
- Execute an automated self-diagnostic check.

---

## 🧪 System Validation & Testing

Run the comprehensive 8-phase automated end-to-end integration test suite:

```powershell
python test_system_full.py
```

### Verification Phases:
```text
[PASS] Phase 1: Environment & Dependency Validation
[PASS] Phase 2: CAD to G-Code Ingestion (CADConverter & Parser)
[PASS] Phase 3: Path Optimization & TSP Heuristic Pruning
[PASS] Phase 4: Waveform Generation, Delays & Electrical Clamping
[PASS] Phase 5: Hardware DAQ Controller (Simulation & E-STOP)
[PASS] Phase 6: SQLite3 Database, Schema Migrations & Audit Trail
[PASS] Phase 7: Threading Isolation & Async Telemetry Callbacks
[PASS] Phase 8: Artifact Cleanup & System Integrity
```

---

## 🖥️ Running the Application

Launch the production user interface:

```powershell
python iniciar_interfaz.py
```

### Quick Workflow:
1. Select a validated polymer recipe from the recipe dropdown (e.g., `Acrylic – Standard`).
2. Load a 2D DXF file (samples available in the `dxf/` directory).
3. Inspect the trajectory preview on the dual canvas.
4. Press **START (EJECUTAR)** to run the hardware-timed processing cycle.
5. In case of anomaly, hit **EMERGENCY STOP (PARADA DE EMERGENCIA)** for instantaneous beam extinction and mirror parking.

---

## 📁 Repository Structure

```text
FRONTEND FINAL/
│
├── iniciar_interfaz.py            # Main application launcher (CustomTkinter GUI)
├── test_system_full.py            # Automated 8-phase end-to-end test battery
├── setup_environment.ps1          # Automated setup & environment deployment script
├── requirements.txt               # Pinned Python package dependencies
├── visualizar_comparativa.py      # CAD vs. CAM comparative visualization tool
│
├── core/                          # Path planning, G-code parsing, and DAQ HAL
│   ├── CADConverter.py            # Automated DXF-to-Gcode FreeCAD CLI wrapper
│   ├── GCodeParser.py             # ISO 6983 G-code parser & TrajectoryBlock builder
│   ├── PathOptimizer.py           # RDP geometry simplification & 2-Opt TSP solver
│   ├── GalvoSignalGenerator.py    # 100 kS/s waveform generator & optical delays
│   ├── NIDaqController.py         # Hardware-timed NI-DAQmx controller & virtual mock
│   ├── config_loader.py           # Centralized configuration loader & fallback defaults
│   ├── generador_trayectorias.py  # Geometric trajectory math
│   └── lector_dxf.py              # Recursive DXF entity reader via ezdxf
│
├── hardware/                      # Physical driver layer and deployment manuals
│   ├── hardware_config.json       # DAQ channels, calibration (0.200 V/mm), and timing
│   ├── config_galvo.py            # Kinematic limits, scan field, and default delays
│   ├── controlador_thorlabs.py    # Driver abstraction for Thorlabs GVS112/M
│   ├── simulador_thorlabs.py      # High-fidelity virtual kinematic simulator
│   ├── README_THORLABS.md         # Hardware deployment manual (English)
│   └── README_THORLABS_CS.md      # Hardware deployment manual (Czech)
│
├── database/                      # Persistent storage and audit trail
│   ├── gestor_db.py               # SQLite3 engine with Write-Ahead Logging (WAL)
│   ├── recetas.py                 # Polymer recipe management & queries
│   ├── trazabilidad.py            # Production execution history logger
│   └── laser_system.db            # Local SQLite3 database file
│
├── interfaz/                      # Graphical User Interface (Cyber-Brutalist HMI)
│   ├── interfaz_app.py            # Main application frame & lifecycle coordinator
│   ├── barra_superior.py          # Status bar, mode selector, and system clock
│   ├── panel_general.py           # Left execution and manual jog control panel
│   ├── panel_configuracion.py     # Kinematics, delays, and optical parameter panel
│   ├── panel_derecho.py           # Right recipe management & audit log panel
│   ├── renderizado_dual.py        # Vector dual-canvas preview (CAD vs. Galvo space)
│   ├── terminal_flotante.py       # Floating real-time diagnostic console
│   ├── conexion_interfaz.py       # Asynchronous threading worker (PuenteLaser)
│   ├── constantes.py              # Visual design tokens, styles, and color constants
│   ├── i18n.py                    # Multi-language dictionary (ES, EN, CS)
│   └── fonts/                     # Embedded typography (BrunoAce, Teachers)
│
├── dxf/                           # Sample vector DXF blueprints
└── gcode/                         # Pre-compiled ISO 6983 G-code trajectories
```

---

## 🏛️ Institutional Credit & Contact

- **Author / Developer:** Andrei Martínez Bahena (Residente Profesional TecNM / Centro de Investigación ÚFE AV ČR).
- **Host Institution:** Institute of Photonics and Electronics of the Czech Academy of Sciences (*Ústav fotoniky a elektroniky AV ČR, v. v. i.*).
- **Department:** Department of Optical Fiber Lasers and Non-Linear Optics (*Oddělení vláknových laserů a nelineární optiky*).
- **Address:** Chaberská 1014/57, 182 00 Praha 8, Czech Republic.
