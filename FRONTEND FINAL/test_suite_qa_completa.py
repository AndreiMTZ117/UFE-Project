# -*- coding: utf-8 -*-
"""comprehensive functional and non-functional qa test suite (10 categories)"""

from __future__ import annotations

import ast
import atexit
import contextlib
import gc
import glob
import math
import os
import shutil
import sys
import tempfile
import threading
import time
import tracemalloc
import warnings
from typing import Any, Dict, List, Tuple

import numpy as np

# ensure project root is present in sys.path
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.CADConverter import CADConverter
from core.GCodeParser import GCodeParser, TrajectoryBlock
from core.GalvoSignalGenerator import GalvoSignalGenerator
from core.NIDaqController import NIDaqController, probe_daq_hardware
from core.PathOptimizer import PathOptimizer, fusionar_trazos_contiguos
from core.config_loader import DEFAULT_HARDWARE_CONFIG, get_volts_per_mm, load_hardware_config
from core.dxf_reader import LectorDXF, obtener_limites_dxf
from core.trajectory_generator import transform_and_scale_dxf
from database.db_manager import GestorDB
from database.recipes import GestorRecetas
from database.traceability import GestorTrazabilidad
import ui.config_panel as cp
import ui.general_panel as gp
import ui.right_panel as rp
import ui.top_bar as tb
import ui.floating_terminal as ft
from ui.constants import RECETAS_PREDETERMINADAS, agregar_tooltip
from ui.i18n import _TEXTOS, cambiar_idioma, obtener_idioma, tr
import ui.interface_bridge as ib
from ui.interface_bridge import PuenteLaser, calc_inertial_lag_ms

_TEMP_ARTIFACTS: List[str] = []


def _register_temp(path: str) -> str:
    if path and path not in _TEMP_ARTIFACTS:
        _TEMP_ARTIFACTS.append(path)
    return path


def _cleanup_temp() -> None:
    gc.collect()
    for path in list(_TEMP_ARTIFACTS):
        for _ in range(5):
            try:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                for sfx in ("-wal", "-shm", "-journal"):
                    side = path + sfx
                    if os.path.isfile(side):
                        os.remove(side)
                break
            except Exception:
                time.sleep(0.05)
                gc.collect()


atexit.register(_cleanup_temp)


@contextlib.contextmanager
def _silence_stdio():
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = devnull, devnull
        try:
            yield
        finally:
            sys.stdout, sys.stderr = old_out, old_err


# ==============================================================================
# 1. PRUEBAS FUNCIONALES DE CAJA BLANCA (WHITE-BOX TESTING)
# ==============================================================================
def test_01_caja_blanca() -> Dict[str, Any]:
    """verify internal mathematical discretization, delays, pincushion, rdp, tsp and fft lag"""
    fs = 100_000.0
    v_per_mm = 0.02535
    blocks = [
        TrajectoryBlock("G0", (0.0, 0.0), (10.0, 0.0), 1000.0),   # 10 mm @ 1000 mm/s = 10 ms = 1000 samples
        TrajectoryBlock("G1", (10.0, 0.0), (30.0, 0.0), 500.0),   # 20 mm @ 500 mm/s  = 40 ms = 4000 samples
    ]
    gen = GalvoSignalGenerator(
        blocks,
        sample_rate_hz=fs,
        scale_factor_v_per_mm=v_per_mm,
        voltage_limits=(-10.0, 10.0),
        jump_delay_us=200.0,       # 20 samples
        mark_delay_us=100.0,       # 10 samples
        laser_on_delay_us=50.0,    # 5 samples
        laser_off_delay_us=50.0,   # 5 samples
        pincushion_kx=0.05,
        pincushion_ky=0.05,
    )
    voltages, gate = gen.generate_signals()

    # Exact sample count verification:
    # 1 prepended initial sample
    # + G0 (1000 ramp + 20 jump_delay = 1020)
    # + G1 (4000 ramp + 10 mark_delay = 4010)
    # Total = 1 + 1020 + 4010 = 5031 samples
    # Laser gate offsets: on_index = 1 + 1020 + 5 = 1026; off_index = min(1 + 1020 + 4000 + 5, 5031) = 5026
    expected_samples = 1 + (1000 + 20) + (4000 + 10)
    assert voltages.shape == (2, expected_samples), f"Expected (2, {expected_samples}), got {voltages.shape}"
    assert gate.shape == (1, expected_samples), f"Expected (1, {expected_samples}), got {gate.shape}"

    # Verify laser gate state transitions inside the internal timeline
    assert np.all(gate[0, :1026] == 0), "Laser gate must be 0 during initial sample, G0, jump_delay and laser_on_delay"
    assert np.all(gate[0, 1026:5026] == 1), "Laser gate must be 1 during G1 ramp and laser_off_delay extension"
    assert np.all(gate[0, 5026:] == 0), "Laser gate must return to 0 after laser_off_delay"

    # Pincushion pre-distortion mathematical check
    pts_corr = gen._apply_pincushion_correction(np.array([[100.0, 100.0]]))
    assert pts_corr[0, 0] < 100.0 and pts_corr[0, 1] < 100.0, "Positive pincushion kx/ky must pre-compress coordinates"

    # RDP internal recursion & 2-Opt branch verification
    pts = np.column_stack((np.linspace(0.0, 20.0, 50), np.sin(np.linspace(0.0, 3.14, 50))))
    assert len(PathOptimizer.rdp(pts, epsilon=0.0)) == 50
    assert 2 < len(PathOptimizer.rdp(pts, epsilon=0.1)) < 50

    # FFT cross-correlation inertial lag white-box check (exact 2.50 ms synthetic shift)
    t = np.linspace(0.0, 0.1, 10_000)
    cmd_sig = np.vstack([np.sin(2 * np.pi * 50 * t), np.cos(2 * np.pi * 50 * t)])
    shift_samples = 250  # 2.50 ms at 100 kHz
    meas_sig = np.zeros_like(cmd_sig)
    meas_sig[:, shift_samples:] = cmd_sig[:, :-shift_samples]
    lag_detected = calc_inertial_lag_ms(meas_sig, cmd_sig, sample_rate_hz=fs)
    assert math.isclose(lag_detected, 2.50, abs_tol=0.05), f"Expected 2.50 ms lag, got {lag_detected} ms"

    return {
        "discretized_samples": expected_samples,
        "fft_lag_detected_ms": lag_detected,
    }


# ==============================================================================
# 2. PRUEBAS FUNCIONALES DE CAJA NEGRA (BLACK-BOX: EQUIVALENCE & BOUNDARY VALUES)
# ==============================================================================
def test_02_caja_negra(ui_ctx: Dict[str, Any]) -> Dict[str, Any]:
    """equivalence partitioning, boundary value analysis and kinematic coupling rules"""
    fd, tmp_db = tempfile.mkstemp(prefix="qa_bb_", suffix=".db")
    os.close(fd)
    _register_temp(tmp_db)

    with _silence_stdio():
        db = GestorDB(ruta_db=tmp_db)
        gr = GestorRecetas(db)

        cases_evaluated = 0

        # 1. Valid equivalence partition & exact lower/upper boundaries in DB
        boundary_recipes = [
            # Lower exact boundary
            {
                "nombre": "BB_Lower_Bound",
                "polimero": "PMMA",
                "modo_proceso": "Cutting",
                "velocidad_trazado": 0.01,
                "velocidad_viaje": 0.01,
                "num_pasadas": 1,
                "escala_dibujo": 0.01,
                "cooling_delay_s": 0.0,
                "tolerancia_rdp": 0.0,
                "tolerancia_union": 0.0,
            },
            # Upper exact boundary
            {
                "nombre": "BB_Upper_Bound",
                "polimero": "PTFE",
                "modo_proceso": "Marking",
                "velocidad_trazado": 1200.0,
                "velocidad_viaje": 3000.0,
                "num_pasadas": 40,
                "escala_dibujo": 1.0,
                "cooling_delay_s": 45.0,
                "tolerancia_rdp": 0.10,
                "tolerancia_union": 1.0,
            },
        ]
        for br in boundary_recipes:
            rid = gr.crear_receta(br)
            assert rid > 0
            cases_evaluated += 1

        # 2. Invalid partitions outside boundaries (must raise ValueError)
        invalid_db_cases = [
            {"nombre": "", "polimero": "PMMA"},                                  # empty name
            {"nombre": "NoPoly", "polimero": "   "},                             # empty polymer
            {"nombre": "BadVMarkLow", "polimero": "PC", "velocidad_trazado": 0.0},
            {"nombre": "BadVMarkHigh", "polimero": "PC", "velocidad_trazado": 1200.01},
            {"nombre": "BadVJumpHigh", "polimero": "PC", "velocidad_viaje": 3000.5},
            {"nombre": "BadPassesLow", "polimero": "PC", "num_pasadas": 0},
            {"nombre": "BadPassesHigh", "polimero": "PC", "num_pasadas": 41},
            {"nombre": "BadScaleHigh", "polimero": "PC", "escala_dibujo": 1.01},
            {"nombre": "BadCoolingHigh", "polimero": "PC", "cooling_delay_s": 45.1},
            {"nombre": "BadMode", "polimero": "PC", "modo_proceso": "Ablation"},
        ]
        for inv in invalid_db_cases:
            raised = False
            try:
                gr.crear_receta(inv)
            except ValueError:
                raised = True
            assert raised, f"Invalid case did not raise ValueError: {inv}"
            cases_evaluated += 1

    # 3. UI Form Black-Box & Cross-Parameter Kinematic Coupling
    panel: cp.PanelConfiguracion = ui_ctx["cfg"]
    base_valid = gr.listar_recetas()[0]
    panel.poblar_formulario(base_valid)
    has_err, errs, warns = panel.obtener_diagnostico_formulario()
    assert not has_err and len(errs) == 0
    cases_evaluated += 1

    # Coupled Error 1: Mark Speed >= 600 mm/s with Min Mark Dwell < 5 ms
    panel.poblar_formulario({**base_valid, "velocidad_trazado": 600.0, "duracion_min_segmento_ms": 0})
    has_err, errs, _ = panel.obtener_diagnostico_formulario()
    assert has_err and any(tr("param_velocidad_trazado") in e or tr("param_duracion_min_segmento_ms") in e for e in errs)
    cases_evaluated += 1

    # Coupled Warning 1: Mark Speed > 300 mm/s with Min Mark Dwell == 0 ms
    panel.poblar_formulario({**base_valid, "velocidad_trazado": 350.0, "duracion_min_segmento_ms": 0})
    has_err, errs, warns = panel.obtener_diagnostico_formulario()
    assert not has_err and len(warns) >= 1
    cases_evaluated += 1

    # Coupled Error 2: Travel Speed >= 2000 mm/s with Jump Settling Delay < 2.0 ms
    panel.poblar_formulario({**base_valid, "velocidad_viaje": 2500.0, "jump_delay_ms": 0})
    has_err, errs, _ = panel.obtener_diagnostico_formulario()
    assert has_err and any(tr("param_velocidad_viaje") in e or tr("param_jump_delay_ms") in e for e in errs)
    cases_evaluated += 1

    # Non-numeric string input ("abc")
    panel.inputs["velocidad_trazado"].delete(0, "end")
    panel.inputs["velocidad_trazado"].insert(0, "abc")
    has_err, errs, _ = panel.obtener_diagnostico_formulario()
    assert has_err and len(errs) >= 1
    cases_evaluated += 1

    panel.poblar_formulario(base_valid)
    return {"black_box_cases": cases_evaluated}


# ==============================================================================
# 3. PRUEBAS DE HUMO (SMOKE TESTING)
# ==============================================================================
def test_03_humo(ui_ctx: Dict[str, Any]) -> Dict[str, Any]:
    """verify cold boot of all modules, ast compilation, database boot and ui instantiation"""
    py_files = [
        p for p in glob.glob(os.path.join(_PROJECT_ROOT, "**", "*.py"), recursive=True)
        if os.path.basename(p) != os.path.basename(__file__)
    ]
    for p in py_files:
        with open(p, "r", encoding="utf-8") as fh:
            ast.parse(fh.read(), filename=p)

    puente: PuenteLaser = ui_ctx["puente"]
    recipes = puente.get_recipes()
    assert len(recipes) >= 5, f"Expected at least 5 factory recipes, found {len(recipes)}"

    w_cfg: cp.PanelConfiguracion = ui_ctx["cfg"]
    w_gen: gp.PanelGeneral = ui_ctx["gen"]
    w_der: rp.PanelDerecho = ui_ctx["der"]
    w_term: ft.TerminalFlotante = ui_ctx["term"]

    w_cfg.poblar_formulario(recipes[0])
    w_gen.actualizar_dimensiones(puente.ancho_base_cm, puente.alto_base_cm)
    w_der.set_centro(puente.centro_cm_x, puente.centro_cm_y)
    w_term.log("Smoke test boot check OK")

    return {"compiled_modules": len(py_files), "factory_recipes": len(recipes)}


# ==============================================================================
# 4. PRUEBAS DE REGRESIÓN (REGRESSION TESTING)
# ==============================================================================
def test_04_regresion(ui_ctx: Dict[str, Any]) -> Dict[str, Any]:
    """verify all historical bug fixes remain permanently resolved"""
    checks = 0

    # Regression 1: Closed square loop does not duplicate closing vertex in fusionar_trazos_contiguos
    closed_sq = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    res_sq = fusionar_trazos_contiguos([closed_sq], tol_union=0.1)
    assert len(res_sq[0]) == 5, f"Expected 5 points, got {len(res_sq[0])}"
    checks += 1

    # Regression 2: poblar_formulario suppresses on_parametro_cambiado callbacks
    calls: List[Tuple[str, Any]] = ui_ctx["cb_calls"]
    p_cfg: cp.PanelConfiguracion = ui_ctx["cfg"]
    puente: PuenteLaser = ui_ctx["puente"]
    calls.clear()
    p_cfg.poblar_formulario(puente.get_recipes()[0])
    assert len(calls) == 0, f"Expected 0 callbacks during poblar_formulario, got {len(calls)}"
    p_cfg._validar_campo("velocidad_trazado")
    assert len(calls) == 1, "Manual field validation must fire exactly 1 callback"
    calls.clear()
    checks += 1

    # Regression 3: recalculate_paths returns physical dimensions in cm (not hardware mm)
    puente.trazos_originales = [[(0.0, 0.0), (100.0, 0.0), (100.0, 50.0), (0.0, 50.0), (0.0, 0.0)]]
    stats = puente.recalculate_paths({"escala_dibujo": 0.5, "tolerancia_rdp": 0.0, "tolerancia_union": 0.05})
    assert math.isclose(stats["ancho_cm"], 18.75, abs_tol=0.05)
    assert math.isclose(stats["alto_cm"], 9.38, abs_tol=0.05)
    checks += 1

    # Regression 4: mostrar_frame_dxf computes bounding box from trazos_actuales when called with None
    p_gen: gp.PanelGeneral = ui_ctx["gen"]
    p_gen.trazos_actuales = [[(5.0, 6.0), (15.0, 18.0)]]
    p_gen.mostrar_frame_dxf()
    assert p_gen.frame_box_cm == (5.0, 6.0, 15.0, 18.0)
    checks += 1

    # Regression 5: agregar_tooltip idempotency across language switches
    p_der: rp.PanelDerecho = ui_ctx["der"]
    tip_before = p_der.btn_start._tooltip_inst
    cambiar_idioma("CS")
    tip_after = p_der.btn_start._tooltip_inst
    assert tip_before is tip_after and tip_after.texto == tr("tooltip_btn_start")
    cambiar_idioma("EN")
    checks += 1

    return {"regression_checks_passed": checks}


# ==============================================================================
# 5. PRUEBAS NO FUNCIONALES DE RENDIMIENTO (PERFORMANCE TESTING)
# ==============================================================================
def test_05_rendimiento() -> Dict[str, Any]:
    """measure execution latency and memory footprint across critical pipelines"""
    tracemalloc.start()

    # 5a. DXF scaling & geometric transformation latency (100 contours, 1000 vertices)
    synthetic_dxf = [
        [(float(i * 2 + k * 0.1), float((i % 10) * 2 + k * 0.1)) for k in range(10)]
        for i in range(100)
    ]
    t0 = time.perf_counter()
    scaled = transform_and_scale_dxf(
        synthetic_dxf,
        x_min_limit=-187.5, x_max_limit=187.5,
        y_min_limit=-191.5, y_max_limit=191.5,
        escala=0.85,
        marco_ancho_cm=37.5, marco_alto_cm=38.3,
        tolerancia_rdp=0.005,
        tolerancia_union=0.05,
        optimizar_recorrido=True,
    )
    t_transform_ms = (time.perf_counter() - t0) * 1000.0
    assert len(scaled) > 0 and t_transform_ms < 1000.0

    # 5b. TSP 2-Opt (N=40) and Greedy (N=150) optimization speed
    opt = PathOptimizer(epsilon=0.0, rapid_speed_mm_s=2000.0)
    contours_40 = [np.array([[float(i * 3), 0.0], [float(i * 3 + 1), 1.0]]) for i in range(40)]
    t0 = time.perf_counter()
    opt.tsp_2opt(contours_40, start_point=(0.0, 0.0))
    t_tsp40_ms = (time.perf_counter() - t0) * 1000.0

    contours_150 = [np.array([[float(i * 2), 0.0], [float(i * 2 + 1), 1.0]]) for i in range(150)]
    t0 = time.perf_counter()
    opt._solve_order(contours_150, start_point=(0.0, 0.0))
    t_tsp150_ms = (time.perf_counter() - t0) * 1000.0
    assert t_tsp150_ms < 500.0

    # 5c. 100 kHz Waveform Synthesis throughput (> 1,000,000 samples)
    blocks = [
        TrajectoryBlock("G1", (-100.0, -100.0), (100.0, 100.0), 25.0),  # ~282.84 mm @ 25 mm/s = 11.31 s = 1,131,371 samples
    ]
    t0 = time.perf_counter()
    gen = GalvoSignalGenerator(blocks, sample_rate_hz=100_000.0, scale_factor_v_per_mm=0.02535)
    v_mat, g_mat = gen.generate_signals()
    t_synth_ms = (time.perf_counter() - t0) * 1000.0
    n_samples = int(v_mat.shape[1])
    assert n_samples > 1_000_000 and t_synth_ms < 1000.0

    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_ram_mb = peak_bytes / (1024.0 * 1024.0)

    return {
        "dxf_transform_ms": round(t_transform_ms, 2),
        "tsp_2opt_40_ms": round(t_tsp40_ms, 2),
        "tsp_greedy_150_ms": round(t_tsp150_ms, 2),
        "waveform_1M_synth_ms": round(t_synth_ms, 2),
        "samples_synthesized": n_samples,
        "peak_ram_mb": round(peak_ram_mb, 2),
    }


# ==============================================================================
# 6. PRUEBAS NO FUNCIONALES DE CARGA (CONCURRENT LOAD TESTING)
# ==============================================================================
def test_06_carga() -> Dict[str, Any]:
    """concurrent multi-threaded read/write load over sqlite3 wal database"""
    fd, tmp_db = tempfile.mkstemp(prefix="qa_load_", suffix=".db")
    os.close(fd)
    _register_temp(tmp_db)

    errors: List[Exception] = []
    ops_counter = [0]
    counter_lock = threading.Lock()

    def _writer_worker(tid: int, gr_inst: GestorRecetas, gt_inst: GestorTrazabilidad):
        try:
            rid = gr_inst.crear_receta({
                "nombre": f"LoadRecipe_T{tid}",
                "polimero": "PMMA",
                "modo_proceso": "Cutting",
                "velocidad_trazado": 10.0 + tid,
                "velocidad_viaje": 100.0 + tid,
            })
            for step in range(20):
                gr_inst.actualizar_receta(rid, {"velocidad_trazado": 15.0 + step})
                gt_inst.registrar_ciclo({
                    "operador": f"Thread_{tid}",
                    "archivo_dxf": f"part_{step}.dxf",
                    "receta_id": rid,
                    "receta_nombre": f"LoadRecipe_T{tid}",
                    "modo_proceso": "Cutting",
                    "estado": "COMPLETADO",
                    "velocidad_trazado": 15.0 + step,
                    "velocidad_viaje": 100.0,
                    "duracion_segundos": 0.25,
                })
                with counter_lock:
                    ops_counter[0] += 2
        except Exception as e:
            errors.append(e)

    def _reader_worker(gr_inst: GestorRecetas, gt_inst: GestorTrazabilidad):
        try:
            for _ in range(20):
                recs = gr_inst.listar_recetas()
                hist = gt_inst.listar_historial(limite=30)
                assert isinstance(recs, list) and isinstance(hist, list)
                with counter_lock:
                    ops_counter[0] += 2
        except Exception as e:
            errors.append(e)

    with _silence_stdio():
        db = GestorDB(ruta_db=tmp_db)
        gr = GestorRecetas(db)
        gt = GestorTrazabilidad(db)

        t0 = time.perf_counter()
        threads = [threading.Thread(target=_writer_worker, args=(i, gr, gt)) for i in range(4)]
        threads += [threading.Thread(target=_reader_worker, args=(gr, gt)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15.0)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        total_logs = gt.listar_historial(limite=200)

    assert len(errors) == 0, f"Concurrent SQLite WAL load test failed with errors: {errors}"
    assert len(total_logs) == 80, f"Expected 80 production logs from 4 writers, got {len(total_logs)}"

    return {
        "concurrent_threads": 8,
        "total_db_transactions": ops_counter[0],
        "load_duration_ms": round(elapsed_ms, 2),
    }


# ==============================================================================
# 7. PRUEBAS NO FUNCIONALES DE ESTRÉS (STRESS TESTING)
# ==============================================================================
def test_07_estres() -> Dict[str, Any]:
    """push geometry density, out-of-bounds coordinates and rapid e-stop to extremes"""
    # 7a. High-density geometry (50 contours x 40 segments = 2,000 segments)
    dense_paths = []
    for c_idx in range(50):
        base_x = (c_idx % 10) * 15.0
        base_y = (c_idx // 10) * 15.0
        contour = [
            (base_x + math.cos(2 * math.pi * k / 40) * 5.0, base_y + math.sin(2 * math.pi * k / 40) * 5.0)
            for k in range(41)
        ]
        dense_paths.append(contour)

    scaled_dense = transform_and_scale_dxf(
        dense_paths,
        x_min_limit=-187.5, x_max_limit=187.5,
        y_min_limit=-191.5, y_max_limit=191.5,
        escala=0.95,
        marco_ancho_cm=37.5, marco_alto_cm=38.3,
        tolerancia_rdp=0.0,
        tolerancia_union=0.05,
        optimizar_recorrido=True,
    )
    total_pts = sum(len(r) for r in scaled_dense)
    assert total_pts >= 2000

    # 7b. Extreme out-of-bounds coordinate excursion (+/- 10,000 mm)
    extreme_blocks = [
        TrajectoryBlock("G0", (0.0, 0.0), (10_000.0, -10_000.0), 3000.0),
        TrajectoryBlock("G1", (10_000.0, -10_000.0), (-10_000.0, 10_000.0), 1200.0),
    ]
    gen = GalvoSignalGenerator(
        extreme_blocks,
        sample_rate_hz=100_000.0,
        scale_factor_v_per_mm=0.02535,
        voltage_limits=(-10.0, 10.0),
    )
    v_ext, g_ext = gen.generate_signals()
    assert not np.any(np.isnan(v_ext)) and not np.any(np.isinf(v_ext))
    assert float(np.min(v_ext)) >= -10.0 and float(np.max(v_ext)) <= 10.0

    # 7c. Rapid Start -> Pause -> Resume -> Atomic E-STOP burst stress
    with _silence_stdio():
        daq = NIDaqController(simulate=True)
        daq.setup_hardware(("Dev1/ao0", "Dev1/ao1"), "Dev1/port0/line0", f_s=100_000.0)
        daq.write_buffers(v_ext[:, :5000], g_ext[:, :5000])
        daq.start_emission()
        t0 = time.perf_counter()
        daq.stop_and_clear()
        estop_ms = (time.perf_counter() - t0) * 1000.0
    assert daq.state == "idle" and estop_ms < 20.0

    return {
        "stressed_waypoints": total_pts,
        "clamped_voltage_range": (float(np.min(v_ext)), float(np.max(v_ext))),
        "atomic_estop_ms": round(estop_ms, 3),
    }


# ==============================================================================
# 8. PRUEBAS NO FUNCIONALES DE SEGURIDAD (SECURITY & LASER SAFETY TESTING)
# ==============================================================================
def test_08_seguridad() -> Dict[str, Any]:
    """verify sql injection immunity, corrupted file handling and physical laser gate interlocks"""
    fd, tmp_db = tempfile.mkstemp(prefix="qa_sec_", suffix=".db")
    os.close(fd)
    _register_temp(tmp_db)

    with _silence_stdio():
        db = GestorDB(ruta_db=tmp_db)
        gr = GestorRecetas(db)
        gt = GestorTrazabilidad(db)

    # 8a. SQL Injection payloads in recipe and audit trail fields
    sqli_payload = "'; DROP TABLE recetas; DROP TABLE historial_produccion; --"
    with _silence_stdio():
        rid = gr.crear_receta({
            "nombre": sqli_payload,
            "polimero": "' OR '1'='1",
            "notas": "'); DELETE FROM recetas; --",
            "modo_proceso": "Cutting",
        })
        gt.registrar_ciclo({
            "operador": sqli_payload,
            "archivo_dxf": sqli_payload,
            "receta_id": rid,
            "receta_nombre": sqli_payload,
            "modo_proceso": "Cutting",
            "estado": "COMPLETADO",
        })

    # Verify tables still exist and payload was stored literally as inert text
    rec_loaded = gr.obtener_receta(rid)
    assert rec_loaded["nombre"] == sqli_payload
    assert len(gr.listar_recetas()) >= 5

    # 8b. Corrupted / empty DXF and missing file handling
    fd_bad, bad_dxf = tempfile.mkstemp(prefix="qa_corrupt_", suffix=".dxf")
    with os.fdopen(fd_bad, "w", encoding="utf-8") as fh:
        fh.write("THIS IS NOT A VALID DXF FILE CONTENT $$$")
    _register_temp(bad_dxf)

    with _silence_stdio():
        puente = PuenteLaser()
        corrupt_handled = False
        try:
            puente.load_dxf(bad_dxf, {})
        except Exception:
            corrupt_handled = True
        assert corrupt_handled, "Corrupted DXF file must raise a controlled exception"

        missing_handled = False
        try:
            puente.load_dxf("non_existent_file_12345.dxf", {})
        except FileNotFoundError:
            missing_handled = True
        assert missing_handled, "Missing DXF file must raise FileNotFoundError"

    # 8c. Physical Laser Gate Safety Interlocks (Gate = 0 during G0, delays, and cooling)
    blocks = [
        TrajectoryBlock("G0", (0.0, 0.0), (20.0, 20.0), 1000.0),
        TrajectoryBlock("G1", (20.0, 20.0), (40.0, 20.0), 500.0),
        TrajectoryBlock("G0", (40.0, 20.0), (0.0, 0.0), 1000.0),
    ]
    gen = GalvoSignalGenerator(blocks, sample_rate_hz=100_000.0, scale_factor_v_per_mm=0.02535)
    v, g = gen.generate_signals()
    assert g[0, 0] == 0, "First sample must have Laser OFF"
    assert g[0, -1] == 0, "Final G0 sample must have Laser OFF"

    return {"sqli_neutralized": True, "laser_interlock_verified": True}


# ==============================================================================
# 9. PRUEBAS NO FUNCIONALES DE USABILIDAD (USABILITY TESTING)
# ==============================================================================
def test_09_usabilidad(ui_ctx: Dict[str, Any]) -> Dict[str, Any]:
    """verify 100% i18n coverage, actionable error messages with field names/units and execution lock"""
    # 9a. 100% Bilingual EN/CS dictionary completeness
    total_keys = len(_TEXTOS)
    for k, trans in _TEXTOS.items():
        assert "EN" in trans and trans["EN"].strip(), f"Empty EN translation for {k}"
        assert "CS" in trans and trans["CS"].strip(), f"Empty CS translation for {k}"

    # 9b. Actionable error messages must contain exact UI field label and unit
    p_cfg: cp.PanelConfiguracion = ui_ctx["cfg"]
    base_rec = ui_ctx["puente"].get_recipes()[0]
    p_cfg.poblar_formulario(base_rec)
    p_cfg.inputs["velocidad_trazado"].delete(0, "end")
    p_cfg.inputs["velocidad_trazado"].insert(0, "9999")
    has_err, errs, _ = p_cfg.obtener_diagnostico_formulario()
    assert has_err and len(errs) >= 1
    assert tr("param_velocidad_trazado") in errs[0] and "mm/s" in errs[0], (
        f"Error message must include exact field name '{tr('param_velocidad_trazado')}' and unit 'mm/s': {errs[0]}"
    )

    # 9c. Execution lock prevents accidental parameter tampering while laser is firing
    p_cfg.set_bloqueo_ejecucion(True)
    assert p_cfg.bloqueado_ejecucion is True
    for entry in p_cfg.inputs.values():
        assert entry.cget("state") == "disabled", "All form inputs must be disabled during active execution"
    p_cfg.set_bloqueo_ejecucion(False)
    for entry in p_cfg.inputs.values():
        assert entry.cget("state") == "normal", "All form inputs must be re-enabled when returning to idle"

    p_cfg.poblar_formulario(base_rec)
    return {"i18n_keys_verified": total_keys, "disabled_inputs_on_lock": len(cp._LIMITES_PARAMETROS)}


# ==============================================================================
# 10. PRUEBAS DE COMPATIBILIDAD Y PORTABILIDAD (COMPATIBILITY & PORTABILITY)
# ==============================================================================
def test_10_compatibilidad_portabilidad() -> Dict[str, Any]:
    """verify identical behavior across optional dependencies (scipy/numpy, freecad, nidaqmx, json fallback)"""
    # 10a. Compare scipy.signal vs pure numpy.fft fallback in calc_inertial_lag_ms
    fs = 100_000.0
    t = np.linspace(0.0, 0.08, 8_000)
    cmd = np.vstack([np.sin(2 * np.pi * 40 * t), np.cos(2 * np.pi * 40 * t)])
    meas = np.zeros_like(cmd)
    meas[:, 180:] = cmd[:, :-180]  # 1.80 ms lag

    lag_scipy = calc_inertial_lag_ms(meas, cmd, fs)
    orig_scipy = ib.scipy_signal
    try:
        ib.scipy_signal = None
        lag_numpy = calc_inertial_lag_ms(meas, cmd, fs)
    finally:
        ib.scipy_signal = orig_scipy

    assert math.isclose(lag_scipy, 1.80, abs_tol=0.05)
    assert math.isclose(lag_scipy, lag_numpy, abs_tol=0.02), (
        f"Fallback numpy FFT lag ({lag_numpy} ms) diverged from scipy ({lag_scipy} ms)"
    )

    # 10b. Missing hardware_config.json fallback resilience
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        fallback_cfg = load_hardware_config("non_existent_config_path_999.json")
    assert fallback_cfg["distortion_correction"]["field_half_width_mm"] == 187.5
    assert fallback_cfg["distortion_correction"]["field_half_height_mm"] == 191.5
    assert fallback_cfg["volts_per_mm"] == 0.02535

    # 10c. Hardware vs Virtual Simulation portability check
    daq_info = probe_daq_hardware("Dev1")
    assert isinstance(daq_info["available"], bool) and "label" in daq_info

    return {
        "lag_scipy_ms": lag_scipy,
        "lag_numpy_fallback_ms": lag_numpy,
        "daq_portability_status": daq_info["label"],
    }


# ==============================================================================
# MAIN RUNNER & REPORT GENERATOR
# ==============================================================================
def run_qa_suite() -> int:
    import customtkinter as ctk

    t_global = time.perf_counter()
    root = ctk.CTk()
    root.withdraw()

    cb_calls: List[Tuple[str, Any]] = []
    with _silence_stdio():
        puente_shared = PuenteLaser()
    ui_ctx: Dict[str, Any] = {
        "puente": puente_shared,
        "cb_calls": cb_calls,
        "top": tb.BarraSuperior(root),
        "cfg": cp.PanelConfiguracion(root, on_parametro_cambiado=lambda k, v: cb_calls.append((k, v))),
        "gen": gp.PanelGeneral(root),
        "der": rp.PanelDerecho(root),
        "term": ft.TerminalFlotante(root),
    }

    results: List[Tuple[str, str, float, Dict[str, Any]]] = []

    suite_definitions = [
        ("1. Pruebas Funcionales de Caja Blanca (White-Box)", lambda: test_01_caja_blanca()),
        ("2. Pruebas Funcionales de Caja Negra (Black-Box)", lambda: test_02_caja_negra(ui_ctx)),
        ("3. Pruebas Funcionales de Humo (Smoke Testing)", lambda: test_03_humo(ui_ctx)),
        ("4. Pruebas Funcionales de Regresión (Regression)", lambda: test_04_regresion(ui_ctx)),
        ("5. Pruebas No Funcionales de Rendimiento (Performance)", lambda: test_05_rendimiento()),
        ("6. Pruebas No Funcionales de Carga (Concurrent Load)", lambda: test_06_carga()),
        ("7. Pruebas No Funcionales de Estrés (Stress Testing)", lambda: test_07_estres()),
        ("8. Pruebas No Funcionales de Seguridad (Security & Safety)", lambda: test_08_seguridad()),
        ("9. Pruebas No Funcionales de Usabilidad (Usability)", lambda: test_09_usabilidad(ui_ctx)),
        ("10. Pruebas de Compatibilidad y Portabilidad", lambda: test_10_compatibilidad_portabilidad()),
    ]

    print("=" * 78)
    print("   BATERIA INTEGRAL DE PRUEBAS FUNCIONALES Y NO FUNCIONALES (10 CATEGORIAS)   ")
    print("=" * 78)

    try:
        for name, fn in suite_definitions:
            t0 = time.perf_counter()
            metrics = fn()
            dt_ms = (time.perf_counter() - t0) * 1000.0
            results.append((name, "PASS", dt_ms, metrics))
            print(f"[PASS] {name:<58} ({dt_ms:>7.2f} ms)")
            for mk, mv in metrics.items():
                print(f"       • {mk}: {mv}")
    except Exception as exc:
        print(f"\n[FAIL] Error ejecutando pruebas: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        try:
            root.destroy()
        except Exception:
            pass
        _cleanup_temp()

    total_s = time.perf_counter() - t_global
    print("=" * 78)
    print(f"RESULTADO GLOBAL: 10/10 CATEGORIAS SUPERADAS SIN ERRORES EN {total_s:.2f} s")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(run_qa_suite())
