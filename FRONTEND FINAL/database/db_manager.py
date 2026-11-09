# -*- coding: utf-8 -*-
"""sqlite3 database connection and schema management"""

import sqlite3
import os
from contextlib import contextmanager

#database file path
_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_DIR, "laser_system.db")

#table schemas
_SQL_CREAR_TABLA_RECETAS = """
CREATE TABLE IF NOT EXISTS recetas (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre                TEXT    NOT NULL UNIQUE,
    polimero              TEXT    NOT NULL DEFAULT 'Genérico',
    notas                 TEXT    DEFAULT '',

    --kinematic parameters
    velocidad_trazado     REAL    NOT NULL DEFAULT 2.0,
    velocidad_viaje       REAL    NOT NULL DEFAULT 3.5,
    num_pasadas           INTEGER NOT NULL DEFAULT 1,

    --optical delays
    laser_on_delay_ms     INTEGER NOT NULL DEFAULT 0,
    laser_off_delay_ms    INTEGER NOT NULL DEFAULT 0,
    mark_delay_ms         INTEGER NOT NULL DEFAULT 0,
    jump_delay_ms         INTEGER NOT NULL DEFAULT 0,

    --geometry
    tolerancia_rdp        REAL    NOT NULL DEFAULT 0.0,
    tolerancia_union      REAL    NOT NULL DEFAULT 0.08,
    longitud_min_trazo    REAL    NOT NULL DEFAULT 0.01,

    --spatial transform
    escala_dibujo         REAL    NOT NULL DEFAULT 0.90,
    rotar_90_grados       INTEGER NOT NULL DEFAULT 0,

    --process mode
    duracion_min_segmento_ms INTEGER NOT NULL DEFAULT 0,
    duracion_min_viaje_ms    INTEGER NOT NULL DEFAULT 0,
    optimizar_tsp            INTEGER NOT NULL DEFAULT 1,
    modo_proceso             TEXT    NOT NULL DEFAULT 'Cutting' CHECK(modo_proceso IN ('Cutting', 'Welding', 'Marking')),

    --thermal cooling
    cooling_delay_s       REAL    NOT NULL DEFAULT 0.0,
    invert_x              INTEGER NOT NULL DEFAULT 0,
    invert_y              INTEGER NOT NULL DEFAULT 0,
    swap_xy               INTEGER NOT NULL DEFAULT 0,

    --audit timestamps
    fecha_creacion        TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    fecha_modificacion    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

_SQL_CREAR_TABLA_HISTORIAL = """
CREATE TABLE IF NOT EXISTS historial_produccion (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp           TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    operador            TEXT    NOT NULL DEFAULT 'Operador',

    --recipe reference
    receta_id           INTEGER REFERENCES recetas(id) ON DELETE SET NULL,
    receta_nombre       TEXT    DEFAULT 'Manual',

    --processed file
    archivo_dxf         TEXT    NOT NULL,
    hardware_usado      TEXT    NOT NULL DEFAULT 'thorlabs_galvo',

    --parameter snapshot
    modo_proceso        TEXT    NOT NULL DEFAULT 'Cutting' CHECK(modo_proceso IN ('Cutting', 'Welding', 'Marking')),
    velocidad_trazado   REAL,
    velocidad_viaje     REAL,
    num_pasadas         INTEGER DEFAULT 1,
    escala_dibujo       REAL,
    tolerancia_rdp      REAL,
    tolerancia_union    REAL,

    --cycle metrics
    trazos_totales      INTEGER DEFAULT 0,
    waypoints_totales   INTEGER DEFAULT 0,
    duracion_segundos   REAL    DEFAULT 0.0,

    --final result
    estado              TEXT    NOT NULL DEFAULT 'COMPLETADO',
    mensaje_error       TEXT    DEFAULT '',

    --tracking feedback
    tracking_rms_um     REAL,
    tracking_max_um     REAL,
    tracking_lag_ms     REAL
);
"""

#default recipes for common polymers
_RECETAS_DEFAULT = [
    {
        "nombre":             "Acrylic — Standard",
        "polimero":           "Acrylic (PMMA)",
        "notas":              "Base profile for clear or colored acrylic. Moderate speed to prevent heat-affected zones.",
        "modo_proceso":       "Cutting",
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
        "nombre":             "Polycarbonate — High Precision",
        "polimero":           "Polycarbonate (PC)",
        "notas":              "Slow speed and multiple passes for clean cuts in 3mm polycarbonate.",
        "modo_proceso":       "Cutting",
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
        "nombre":             "Nylon — Soft Engraving",
        "polimero":           "Nylon (PA6/PA12)",
        "notas":              "High speed for surface engraving without piercing. Not recommended for full cutting.",
        "modo_proceso":       "Marking",
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
        "nombre":             "Simulation — Vector Test",
        "polimero":           "Generic (Test)",
        "notas":              "Geometric validation profile. Low speed without optical delays. Used for simulation mode.",
        "modo_proceso":       "Marking",
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


#database manager class
class GestorDB:
    """sqlite3 database manager"""

    def __init__(self, ruta_db: str = DB_PATH):
        self.ruta_db = ruta_db
        self._inicializar()

    def _inicializar(self):
        """create tables and insert default recipes if empty"""
        print(f"[DB] Inicializando base de datos en: {self.ruta_db}")
        with self.conexion() as conn:
            conn.execute(_SQL_CREAR_TABLA_RECETAS)
            conn.execute(_SQL_CREAR_TABLA_HISTORIAL)

            #schema migrations
            info_cols = {r[1] for r in conn.execute("PRAGMA table_info(recetas)").fetchall()}
            columnas_extra = [
                ("duracion_min_segmento_ms", "INTEGER NOT NULL DEFAULT 0"),
                ("duracion_min_viaje_ms", "INTEGER NOT NULL DEFAULT 0"),
                ("optimizar_tsp", "INTEGER NOT NULL DEFAULT 1"),
                ("modo_proceso", "TEXT NOT NULL DEFAULT 'Cutting'"),
                ("cooling_delay_s", "REAL NOT NULL DEFAULT 0.0"),
                ("invert_x", "INTEGER NOT NULL DEFAULT 0"),
                ("invert_y", "INTEGER NOT NULL DEFAULT 0"),
                ("swap_xy", "INTEGER NOT NULL DEFAULT 0"),
            ]
            migrated = False
            for col_name, col_def in columnas_extra:
                if col_name not in info_cols:
                    conn.execute(f"ALTER TABLE recetas ADD COLUMN {col_name} {col_def}")
                    migrated = True

            info_cols_hist = {r[1] for r in conn.execute("PRAGMA table_info(historial_produccion)").fetchall()}
            if "modo_proceso" not in info_cols_hist:
                conn.execute("ALTER TABLE historial_produccion ADD COLUMN modo_proceso TEXT DEFAULT 'Cutting'")
                migrated = True

            #tracking feedback columns migration
            for col_name in ("tracking_rms_um", "tracking_max_um", "tracking_lag_ms"):
                if col_name not in info_cols_hist:
                    conn.execute(f"ALTER TABLE historial_produccion ADD COLUMN {col_name} REAL")

            #normalize process modes
            if migrated:
                conn.execute(
                    "UPDATE recetas SET modo_proceso = 'Cutting' "
                    "WHERE modo_proceso IS NULL OR modo_proceso NOT IN ('Cutting', 'Welding', 'Marking')"
                )
                conn.execute("UPDATE recetas SET modo_proceso = 'Marking' WHERE LOWER(nombre) LIKE '%nylon%'")
                conn.execute("UPDATE recetas SET modo_proceso = 'Marking' WHERE (LOWER(nombre) LIKE '%simula%' OR LOWER(nombre) LIKE '%maqueta%')")
                conn.execute(
                    "UPDATE historial_produccion SET modo_proceso = 'Cutting' "
                    "WHERE modo_proceso IS NULL OR modo_proceso NOT IN ('Cutting', 'Welding', 'Marking')"
                )

            #insert default recipes if table is empty
            total = conn.execute("SELECT COUNT(*) FROM recetas").fetchone()[0]
            if total == 0:
                self._insertar_recetas_default(conn)
                print("[DB] Recetas por defecto precargadas (Acrílico, Policarbonato, Nylon, Prueba).")
            else:
                print(f"[DB] {total} receta(s) ya existente(s). No se sobreescriben.")

    def _insertar_recetas_default(self, conn):
        """insert default recipe set"""
        sql = """
            INSERT OR IGNORE INTO recetas (
                nombre, polimero, notas, modo_proceso,
                velocidad_trazado, velocidad_viaje, num_pasadas,
                laser_on_delay_ms, laser_off_delay_ms, mark_delay_ms, jump_delay_ms,
                tolerancia_rdp, tolerancia_union, longitud_min_trazo,
                escala_dibujo, rotar_90_grados
            ) VALUES (
                :nombre, :polimero, :notas, :modo_proceso,
                :velocidad_trazado, :velocidad_viaje, :num_pasadas,
                :laser_on_delay_ms, :laser_off_delay_ms, :mark_delay_ms, :jump_delay_ms,
                :tolerancia_rdp, :tolerancia_union, :longitud_min_trazo,
                :escala_dibujo, :rotar_90_grados
            )
        """
        for receta in _RECETAS_DEFAULT:
            conn.execute(sql, receta)

    @contextmanager
    def conexion(self):
        """thread-safe context manager for sqlite connection"""
        conn = sqlite3.connect(self.ruta_db, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def fila_a_dict(self, row) -> dict:
        """convert sqlite3 row to dict"""
        return dict(row) if row else {}


#global singleton instance
gestor_global = GestorDB()
