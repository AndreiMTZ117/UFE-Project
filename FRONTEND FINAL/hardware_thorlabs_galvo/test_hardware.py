# -*- coding: utf-8 -*-
"""
hardware_thorlabs_galvo/test_hardware.py — Diagnóstico y Test Independiente del PXI-6229

Script de auto-diagnóstico que se ejecuta desde la terminal sin necesidad de
lanzar la interfaz gráfica:

    python hardware_thorlabs_galvo/test_hardware.py

Verificaciones realizadas
--------------------------
  1. Disponibilidad de la librería nidaqmx en el entorno Python.
  2. Detección del controlador NI-DAQmx instalado en Windows (registro de sistema).
  3. Listado y verificación del chasis PXIe-1073 y la tarjeta PXI-6229.
  4. Test de calibración en cruz (+/-1 V en X e Y) para verificar movimiento de espejos
     sin encender el láser.
  5. Retorno automático al centro (0 V, 0 V) al finalizar.
"""

import sys
import time
import os

# Configurar stdout a UTF-8 si está soportado para evitar fallos de codepage en Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Asegurar que el directorio raíz del proyecto esté en sys.path
# ---------------------------------------------------------------------------
_DIR_RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _DIR_RAIZ not in sys.path:
    sys.path.insert(0, _DIR_RAIZ)

from hardware_thorlabs_galvo.config_galvo import (
    DISPOSITIVO_NI, CANAL_AO_X, CANAL_AO_Y,
    MODO_HARDWARE,
)


SEPARADOR = "=" * 60
VOLTAJE_TEST = 1.0      # +/-1 V — movimiento mínimo y seguro para verificación
DURACION_PASO_S = 0.3   # Tiempo en cada posición del patrón en cruz


def _titulo(texto: str):
    print(f"\n{SEPARADOR}")
    print(f"  {texto}")
    print(SEPARADOR)


def _ok(msg: str):
    print(f"  [OK] {msg}")


def _error(msg: str):
    print(f"  [ERROR] {msg}", file=sys.stderr)


def _info(msg: str):
    print(f"  [INFO] {msg}")


# ---------------------------------------------------------------------------
# PASO 1: Verificar nidaqmx
# ---------------------------------------------------------------------------
def verificar_nidaqmx() -> bool:
    _titulo("PASO 1 - Verificar libreria nidaqmx")
    try:
        import nidaqmx
        version = getattr(nidaqmx, "__version__", "desconocida")
        _ok(f"nidaqmx importado correctamente (version: {version})")
        return True
    except ImportError:
        _error("nidaqmx no esta instalado.")
        _info("Instale con:  pip install nidaqmx")
        _info("Asegurese tambien de tener NI-DAQmx Runtime instalado en Windows.")
        return False


# ---------------------------------------------------------------------------
# PASO 2: Verificar controlador NI-DAQmx en Windows
# ---------------------------------------------------------------------------
def verificar_driver_ni() -> bool:
    _titulo("PASO 2 - Verificar controlador NI-DAQmx en Windows")
    try:
        import winreg
        clave = r"SOFTWARE\National Instruments\NI-DAQmx\CurrentVersion"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, clave) as k:
            version, _ = winreg.QueryValueEx(k, "Version")
        _ok(f"NI-DAQmx Runtime encontrado en el sistema (version: {version})")
        return True
    except FileNotFoundError:
        _error("Clave de registro de NI-DAQmx no encontrada.")
        _info("Instale NI-DAQmx desde: https://www.ni.com/es/support/downloads/drivers/download.ni-daq-mx.html")
        return False
    except ImportError:
        _error("Modulo winreg no disponible (sistema no-Windows).")
        return False
    except Exception as exc:
        _error(f"Error al consultar el registro: {exc}")
        return False


# ---------------------------------------------------------------------------
# PASO 3: Detectar dispositivo PXI-6229
# ---------------------------------------------------------------------------
def verificar_dispositivo() -> bool:
    _titulo(f"PASO 3 - Detectar dispositivo '{DISPOSITIVO_NI}' (PXI-6229)")
    try:
        import nidaqmx
        sistema = nidaqmx.system.System.local()
        dispositivos = [d.name for d in sistema.devices]
        _info(f"Dispositivos detectados: {dispositivos if dispositivos else '(ninguno)'}")

        if DISPOSITIVO_NI in dispositivos:
            dev = sistema.devices[DISPOSITIVO_NI]
            _ok(f"'{DISPOSITIVO_NI}' encontrado: {dev.product_type}")
            return True
        else:
            _error(
                f"'{DISPOSITIVO_NI}' NO encontrado. "
                f"Verifique el nombre en NI Measurement & Automation Explorer (NI-MAX)."
            )
            _info(f"Cambie DISPOSITIVO_NI en config_galvo.py si el nombre es diferente.")
            return False
    except Exception as exc:
        _error(f"Excepcion al acceder al sistema NI: {exc}")
        return False


# ---------------------------------------------------------------------------
# PASO 4: Patrón de calibración en cruz (+/-1 V)
# ---------------------------------------------------------------------------
def test_patron_cruz() -> bool:
    _titulo("PASO 4 - Patron de calibracion en CRUZ (+/-1 V) sin laser")
    _info(f"  Dispositivo : {DISPOSITIVO_NI}")
    _info(f"  Canal AO X  : {CANAL_AO_X}  ->  voltaje barrido entre -{VOLTAJE_TEST} V y +{VOLTAJE_TEST} V")
    _info(f"  Canal AO Y  : {CANAL_AO_Y}  ->  voltaje barrido entre -{VOLTAJE_TEST} V y +{VOLTAJE_TEST} V")
    _info(f"  Laser       : APAGADO durante todo el test\n")

    patron = [
        # (Vx, Vy, descripción)
        ( 0.0,          0.0,          "Centro      (0.0 V, 0.0 V)"),
        ( VOLTAJE_TEST,  0.0,         f"Derecha     (+{VOLTAJE_TEST} V, 0.0 V)"),
        ( 0.0,          0.0,          "Centro      (0.0 V, 0.0 V)"),
        (-VOLTAJE_TEST,  0.0,         f"Izquierda   (-{VOLTAJE_TEST} V, 0.0 V)"),
        ( 0.0,          0.0,          "Centro      (0.0 V, 0.0 V)"),
        ( 0.0,          VOLTAJE_TEST, f"Arriba      (0.0 V, +{VOLTAJE_TEST} V)"),
        ( 0.0,          0.0,          "Centro      (0.0 V, 0.0 V)"),
        ( 0.0,         -VOLTAJE_TEST, f"Abajo       (0.0 V, -{VOLTAJE_TEST} V)"),
        ( 0.0,          0.0,          "Reposo      (0.0 V, 0.0 V)"),
    ]

    try:
        import nidaqmx

        with nidaqmx.Task("GVS_TEST_AO") as tarea_ao:
            tarea_ao.ao_channels.add_ao_voltage_chan(
                f"{DISPOSITIVO_NI}/{CANAL_AO_X}", min_val=-10.0, max_val=10.0
            )
            tarea_ao.ao_channels.add_ao_voltage_chan(
                f"{DISPOSITIVO_NI}/{CANAL_AO_Y}", min_val=-10.0, max_val=10.0
            )

            for vx, vy, desc in patron:
                print(f"    -> {desc}")
                tarea_ao.write([vx, vy])
                time.sleep(DURACION_PASO_S)

        _ok("Patron en cruz completado. Espejos retornados al centro (0 V, 0 V).")
        return True

    except Exception as exc:
        _error(f"Fallo durante el patron de calibracion: {exc}")
        return False


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print(f"\n{'=' * 60}")
    print("  THORLABS GVS112/M - DIAGNOSTICO DE HARDWARE PXI-6229")
    print(f"  Modo en config: {MODO_HARDWARE}")
    print(f"{'=' * 60}\n")

    resultados = {}

    # Los pasos de diagnóstico se ejecutan secuencialmente
    resultados["nidaqmx"]      = verificar_nidaqmx()
    resultados["driver_ni"]    = verificar_driver_ni()

    # Solo continuar si los dos primeros pasos pasan
    if resultados["nidaqmx"] and resultados["driver_ni"]:
        resultados["dispositivo"] = verificar_dispositivo()
        if resultados["dispositivo"]:
            resultados["patron_cruz"] = test_patron_cruz()
        else:
            resultados["patron_cruz"] = False
    else:
        resultados["dispositivo"]  = False
        resultados["patron_cruz"]  = False

    # Resumen final
    _titulo("RESUMEN DE DIAGNOSTICO")
    todos_ok = True
    for nombre, ok in resultados.items():
        estado = "[PASS]" if ok else "[FAIL]"
        print(f"  {estado}  -  {nombre}")
        if not ok:
            todos_ok = False

    print()
    if todos_ok:
        print("  [EXITO] Hardware listo para operar. Puede lanzar la interfaz.")
        sys.exit(0)
    else:
        print("  [AVISO] Se detectaron problemas de hardware fisico o librerias.")
        print("          Para operar en simulacion, el sistema funciona de inmediato sin NI-DAQ.")
        sys.exit(1)


if __name__ == "__main__":
    main()
