# -*- coding: utf-8 -*-
"""
database/gestor_db.py — Motor Central de Conexión y Gestión de la Base de Datos SQLite3

Responsabilidades:
  - Localizar y crear el archivo laser_system.db junto a este módulo.
  - Crear las tablas si no existen (migraciones idempotentes).
  - Proveer un context manager thread-safe para transacciones.
  - Precargar recetas por defecto si la tabla está vacía.
"""

import sqlite3
import os
from contextlib import contextmanager

# =========================================================
# RUTA DEL ARCHIVO DE BASE DE DATOS
# Siempre se ubica dentro de la carpeta database/
# =========================================================
_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_DIR, "laser_system.db")

# =========================================================
# DDL: DEFINICIÓN DE TABLAS
# =========================================================

_SQL_CREAR_TABLA_RECETAS = """
CREATE TABLE IF NOT EXISTS recetas (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre                TEXT    NOT NULL UNIQUE,
    polimero              TEXT    NOT NULL DEFAULT 'Genérico',
    notas                 TEXT    DEFAULT '',

    -- Parámetros cinemáticos
    velocidad_trazado     REAL    NOT NULL DEFAULT 2.0,
    velocidad_viaje       REAL    NOT NULL DEFAULT 3.5,
    num_pasadas           INTEGER NOT NULL DEFAULT 1,

    -- Temporización óptica (ms)
    laser_on_delay_ms     INTEGER NOT NULL DEFAULT 0,
    laser_off_delay_ms    INTEGER NOT NULL DEFAULT 0,
    mark_delay_ms         INTEGER NOT NULL DEFAULT 0,
    jump_delay_ms         INTEGER NOT NULL DEFAULT 0,

    -- Filtrado y optimización geométrica
    tolerancia_rdp        REAL    NOT NULL DEFAULT 0.0,
    tolerancia_union      REAL    NOT NULL DEFAULT 0.08,
    longitud_min_trazo    REAL    NOT NULL DEFAULT 0.01,

    -- Transformaciones espaciales predeterminadas
    escala_dibujo         REAL    NOT NULL DEFAULT 0.90,
    rotar_90_grados       INTEGER NOT NULL DEFAULT 0,

    -- Metadatos de auditoría
    fecha_creacion        TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    fecha_modificacion    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

_SQL_CREAR_TABLA_HISTORIAL = """
CREATE TABLE IF NOT EXISTS historial_produccion (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp           TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    operador            TEXT    NOT NULL DEFAULT 'Operador',

    -- Referencia a la receta usada (puede ser NULL si se usó config manual)
    receta_id           INTEGER REFERENCES recetas(id) ON DELETE SET NULL,
    receta_nombre       TEXT    DEFAULT 'Manual',

    -- Archivo procesado
    archivo_dxf         TEXT    NOT NULL,
    hardware_usado      TEXT    NOT NULL DEFAULT 'maqueta_servos',

    -- Snapshot de parámetros en el momento de ejecución
    velocidad_trazado   REAL,
    velocidad_viaje     REAL,
    num_pasadas         INTEGER DEFAULT 1,
    escala_dibujo       REAL,
    tolerancia_rdp      REAL,
    tolerancia_union    REAL,

    -- Métricas del ciclo
    trazos_totales      INTEGER DEFAULT 0,
    waypoints_totales   INTEGER DEFAULT 0,
    duracion_segundos   REAL    DEFAULT 0.0,

    -- Resultado final
    estado              TEXT    NOT NULL DEFAULT 'COMPLETADO',
    mensaje_error       TEXT    DEFAULT ''
);
"""

# =========================================================
# RECETAS POR DEFECTO PARA POLÍMEROS COMUNES
# Se insertan solo si la tabla recetas está vacía
# =========================================================
_RECETAS_DEFAULT = [
    {
        "nombre":             "Acrílico — Estándar",
        "polimero":           "Acrílico (PMMA)",
        "notas":              "Perfil base para acrílico transparente o de color. Velocidad moderada para evitar bordes quemados.",
        "velocidad_trazado":  1.5,
        "velocidad_viaje":    3.0,
        "num_pasadas":        1,
        "laser_on_delay_ms":  50,
        "laser_off_delay_ms": 30,
        "mark_delay_ms":      20,
        "jump_delay_ms":      100,
        "tolerancia_rdp":     0.005,
        "tolerancia_union":   0.08,
        "longitud_min_trazo": 0.01,
        "escala_dibujo":      0.78,
        "rotar_90_grados":    0,
    },
    {
        "nombre":             "Policarbonato — Alta Precisión",
        "polimero":           "Policarbonato (PC)",
        "notas":              "Velocidad lenta y múltiples pasadas para corte limpio en policarbonato de 3mm.",
        "velocidad_trazado":  1.0,
        "velocidad_viaje":    2.5,
        "num_pasadas":        2,
        "laser_on_delay_ms":  80,
        "laser_off_delay_ms": 60,
        "mark_delay_ms":      40,
        "jump_delay_ms":      150,
        "tolerancia_rdp":     0.002,
        "tolerancia_union":   0.05,
        "longitud_min_trazo": 0.005,
        "escala_dibujo":      0.78,
        "rotar_90_grados":    0,
    },
    {
        "nombre":             "Nylon — Grabado Suave",
        "polimero":           "Nylon (PA6/PA12)",
        "notas":              "Velocidad alta para grabado superficial sin perforar. No recomendado para corte completo.",
        "velocidad_trazado":  2.5,
        "velocidad_viaje":    4.0,
        "num_pasadas":        1,
        "laser_on_delay_ms":  20,
        "laser_off_delay_ms": 10,
        "mark_delay_ms":      10,
        "jump_delay_ms":      80,
        "tolerancia_rdp":     0.01,
        "tolerancia_union":   0.10,
        "longitud_min_trazo": 0.02,
        "escala_dibujo":      0.90,
        "rotar_90_grados":    0,
    },
    {
        "nombre":             "Maqueta — Prueba Vectorial",
        "polimero":           "Genérico (Prueba)",
        "notas":              "Perfil de validación geométrica. Velocidad muy lenta, sin restricciones ópticas. Usar en modo simulación.",
        "velocidad_trazado":  2.0,
        "velocidad_viaje":    3.5,
        "num_pasadas":        1,
        "laser_on_delay_ms":  0,
        "laser_off_delay_ms": 0,
        "mark_delay_ms":      0,
        "jump_delay_ms":      0,
        "tolerancia_rdp":     0.025,
        "tolerancia_union":   0.08,
        "longitud_min_trazo": 0.01,
        "escala_dibujo":      0.90,
        "rotar_90_grados":    0,
    },
]


# =========================================================
# CLASE PRINCIPAL: GestorDB
# =========================================================

class GestorDB:
    """
    Motor central de la base de datos SQLite3.

    Uso recomendado como singleton:
        db = GestorDB()
        with db.conexion() as conn:
            conn.execute("SELECT ...")
    """

    def __init__(self, ruta_db: str = DB_PATH):
        self.ruta_db = ruta_db
        self._inicializar()

    def _inicializar(self):
        """Crea las tablas e inserta recetas por defecto si es la primera ejecución."""
        print(f"[DB] Inicializando base de datos en: {self.ruta_db}")
        with self.conexion() as conn:
            conn.execute(_SQL_CREAR_TABLA_RECETAS)
            conn.execute(_SQL_CREAR_TABLA_HISTORIAL)
            conn.commit()

        # Insertar recetas por defecto solo si la tabla está vacía
        with self.conexion() as conn:
            total = conn.execute("SELECT COUNT(*) FROM recetas").fetchone()[0]
            if total == 0:
                self._insertar_recetas_default(conn)
                print("[DB] Recetas por defecto precargadas (Acrílico, Policarbonato, Nylon, Prueba).")
            else:
                print(f"[DB] {total} receta(s) ya existente(s). No se sobreescriben.")

    def _insertar_recetas_default(self, conn):
        """Inserta el conjunto inicial de recetas de fábrica."""
        sql = """
            INSERT OR IGNORE INTO recetas (
                nombre, polimero, notas,
                velocidad_trazado, velocidad_viaje, num_pasadas,
                laser_on_delay_ms, laser_off_delay_ms, mark_delay_ms, jump_delay_ms,
                tolerancia_rdp, tolerancia_union, longitud_min_trazo,
                escala_dibujo, rotar_90_grados
            ) VALUES (
                :nombre, :polimero, :notas,
                :velocidad_trazado, :velocidad_viaje, :num_pasadas,
                :laser_on_delay_ms, :laser_off_delay_ms, :mark_delay_ms, :jump_delay_ms,
                :tolerancia_rdp, :tolerancia_union, :longitud_min_trazo,
                :escala_dibujo, :rotar_90_grados
            )
        """
        for receta in _RECETAS_DEFAULT:
            conn.execute(sql, receta)
        conn.commit()

    @contextmanager
    def conexion(self):
        """
        Context manager que abre y cierra automáticamente la conexión.
        En caso de excepción, hace ROLLBACK automático.

        Uso:
            with db.conexion() as conn:
                conn.execute("...")
        """
        conn = sqlite3.connect(self.ruta_db, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Permite acceso por nombre de columna
        conn.execute("PRAGMA journal_mode=WAL")   # Write-Ahead Logging: mayor concurrencia
        conn.execute("PRAGMA foreign_keys=ON")    # Integridad referencial activa
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def fila_a_dict(self, row) -> dict:
        """Convierte un sqlite3.Row a dict plano para facilitar su uso."""
        return dict(row) if row else {}


# =========================================================
# INSTANCIA GLOBAL (singleton del módulo)
# =========================================================
# Puede importarse directamente en otros módulos:
#   from database.gestor_db import gestor_global
gestor_global = GestorDB()
