# -*- coding: utf-8 -*-
"""
iniciar_interfaz.py — Lanzador directo de la HMI UFE Laser (CustomTkinter)

Ejecución:
    python iniciar_interfaz.py
"""

import sys
import os
import io

# ── Fix de encoding en Windows (PowerShell / cmd) ─────────────────────────────
# Evita UnicodeEncodeError con caracteres UTF-8 al imprimir en consolas cp1252.
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except AttributeError:
        pass  # Entornos sin buffer (PyInstaller, IDLE)

# Añadir directorio raíz al PYTHONPATH
directorio_raiz = os.path.dirname(os.path.abspath(__file__))
if directorio_raiz not in sys.path:
    sys.path.insert(0, directorio_raiz)

if __name__ == "__main__":
    try:
        from interfaz.interfaz_app import iniciar
        iniciar()
    except ModuleNotFoundError as e:
        print(f"[ERROR] Modulo no encontrado: {e}")
        print("  Instale dependencias con: pip install customtkinter ezdxf numpy")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Fallo al iniciar la interfaz: {e}")
        sys.exit(1)
