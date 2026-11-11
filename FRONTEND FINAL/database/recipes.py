# -*- coding: utf-8 -*-
"""recipes crud operations"""

from .db_manager import GestorDB, gestor_global

#canonical process modes for laser
MODOS_PROCESO_VALIDOS = {"Cutting", "Welding", "Marking"}


class GestorRecetas:
    """manage recipes crud operations"""

    #numerical validation ranges
    _VALIDACIONES = {
        "velocidad_trazado":         (0.01, 1200.0),
        "velocidad_viaje":           (0.01, 3000.0),
        "num_pasadas":               (1, 40),
        "laser_on_delay_ms":         (0, 300),
        "laser_off_delay_ms":        (0, 300),
        "mark_delay_ms":             (0, 150),
        "jump_delay_ms":             (0, 500),
        "tolerancia_rdp":            (0.0, 0.10),
        "tolerancia_union":          (0.0, 1.0),
        "longitud_min_trazo":        (0.0, 10.0),
        "escala_dibujo":             (0.01, 1.0),
        "duracion_min_segmento_ms":  (0, 300),
        "duracion_min_viaje_ms":     (0, 1000),
        "optimizar_tsp":             (0, 1),
        "cooling_delay_s":           (0.0, 45.0),
        "invert_x":                  (0, 1),
        "invert_y":                  (0, 1),
        "swap_xy":                   (0, 1),
    }

    def __init__(self, gestor: GestorDB = None):
        self._db = gestor or gestor_global

    #create
    def crear_receta(self, datos: dict) -> int:
        """insert recipe into db"""
        if not datos.get("nombre", "").strip():
            raise ValueError("Field 'nombre' (Recipe Name) is required and cannot be empty.")
        if not datos.get("polimero", "").strip():
            raise ValueError("Field 'polimero' (Polymer Material) is required.")

        self._validar_rangos(datos)

        sql = """
            INSERT INTO recetas (
                nombre, polimero, notas,
                velocidad_trazado, velocidad_viaje, num_pasadas,
                laser_on_delay_ms, laser_off_delay_ms, mark_delay_ms, jump_delay_ms,
                tolerancia_rdp, tolerancia_union, longitud_min_trazo,
                escala_dibujo, rotar_90_grados,
                duracion_min_segmento_ms, duracion_min_viaje_ms, optimizar_tsp, modo_proceso,
                cooling_delay_s, invert_x, invert_y, swap_xy
            ) VALUES (
                :nombre, :polimero, :notas,
                :velocidad_trazado, :velocidad_viaje, :num_pasadas,
                :laser_on_delay_ms, :laser_off_delay_ms, :mark_delay_ms, :jump_delay_ms,
                :tolerancia_rdp, :tolerancia_union, :longitud_min_trazo,
                :escala_dibujo, :rotar_90_grados,
                :duracion_min_segmento_ms, :duracion_min_viaje_ms, :optimizar_tsp, :modo_proceso,
                :cooling_delay_s, :invert_x, :invert_y, :swap_xy
            )
        """
        #apply defaults for optional fields
        registro = self._aplicar_defaults(datos)

        with self._db.conexion() as conn:
            cursor = conn.execute(sql, registro)
            nuevo_id = cursor.lastrowid

        print(f"[Recetas] [OK] Receta creada: '{datos['nombre']}' (ID={nuevo_id})")
        return nuevo_id

    #read
    def obtener_receta(self, receta_id: int) -> dict:
        """get recipe by id"""
        sql = "SELECT * FROM recetas WHERE id = ?"
        with self._db.conexion() as conn:
            row = conn.execute(sql, (receta_id,)).fetchone()
        return self._db.fila_a_dict(row)

    def listar_recetas(self) -> list:
        """list all recipes"""
        sql = "SELECT * FROM recetas ORDER BY nombre ASC"
        with self._db.conexion() as conn:
            rows = conn.execute(sql).fetchall()
        return [self._db.fila_a_dict(r) for r in rows]

    #update
    def actualizar_receta(self, receta_id: int, datos: dict) -> bool:
        """update recipe fields by id"""
        if not datos:
            return False

        self._validar_rangos(datos)

        #build dynamic set clause
        campos_editables = {
            "nombre", "polimero", "notas", "rotar_90_grados", "modo_proceso",
            *self._VALIDACIONES,
        }
        columnas = {k: v for k, v in datos.items() if k in campos_editables}
        if not columnas:
            return False

        set_clause = ", ".join(f"{col} = :{col}" for col in columnas)
        parametros = dict(columnas)
        parametros["_id"] = receta_id

        sql = f"""
            UPDATE recetas
            SET {set_clause},
                fecha_modificacion = datetime('now','localtime')
            WHERE id = :_id
        """
        with self._db.conexion() as conn:
            cursor = conn.execute(sql, parametros)
            filas = cursor.rowcount

        if filas > 0:
            print(f"[Recetas] [OK] Receta ID={receta_id} actualizada. Campos: {list(datos.keys())}")
        else:
            print(f"[Recetas] [AVISO] No se encontro receta con ID={receta_id}.")
        return filas > 0

    #delete
    def eliminar_receta(self, receta_id: int) -> bool:
        """delete recipe by id"""
        #fetch name and delete in single transaction
        with self._db.conexion() as conn:
            row = conn.execute("SELECT nombre FROM recetas WHERE id = ?", (receta_id,)).fetchone()
            nombre_prev = row["nombre"] if row else f"ID={receta_id}"
            filas = conn.execute("DELETE FROM recetas WHERE id = ?", (receta_id,)).rowcount

        if filas > 0:
            print(f"[Recetas] [DEL] Receta eliminada: '{nombre_prev}' (ID={receta_id})")
        else:
            print(f"[Recetas] [AVISO] No se encontro receta con ID={receta_id}.")
        return filas > 0

    #helpers
    def _validar_rangos(self, datos: dict):
        """validate value ranges and process modes"""
        for campo, (minv, maxv) in self._VALIDACIONES.items():
            if campo in datos:
                val = datos[campo]
                if not (minv <= float(val) <= maxv):
                    raise ValueError(
                        f"Field '{campo}' value {val} is outside allowed physical range [{minv}, {maxv}]."
                    )
        if "modo_proceso" in datos and datos["modo_proceso"] is not None:
            m_str = str(datos["modo_proceso"]).strip()
            modos_norm = {m.lower(): m for m in MODOS_PROCESO_VALIDOS}
            if m_str.lower() in modos_norm:
                datos["modo_proceso"] = modos_norm[m_str.lower()]
            else:
                permitidos = sorted(list(MODOS_PROCESO_VALIDOS))
                raise ValueError(
                    f"Invalid process mode / Modo de proceso no válido: '{datos['modo_proceso']}'. "
                    f"Allowed modes: {permitidos}."
                )

    def _aplicar_defaults(self, datos: dict) -> dict:
        """apply defaults for missing fields"""
        defaults = {
            "nombre":                    "",
            "polimero":                  "Genérico",
            "notas":                     "",
            "velocidad_trazado":         2.0,
            "velocidad_viaje":           3.5,
            "num_pasadas":               1,
            "duracion_min_segmento_ms":  50,
            "duracion_min_viaje_ms":     300,
            "optimizar_tsp":             1,
            "modo_proceso":              "Cutting",
            "cooling_delay_s":           0.0,
            "invert_x":                  0,
            "invert_y":                  0,
            "swap_xy":                   0,
            "laser_on_delay_ms":         0,
            "laser_off_delay_ms":        0,
            "mark_delay_ms":             0,
            "jump_delay_ms":             0,
            "tolerancia_rdp":            0.0,
            "tolerancia_union":          0.08,
            "longitud_min_trazo":        0.01,
            "escala_dibujo":             0.90,
            "rotar_90_grados":           0,
        }
        defaults.update(datos)
        return defaults
