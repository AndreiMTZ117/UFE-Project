# -*- coding: utf-8 -*-
"""
database/recetas.py — CRUD Completo de Recetas de Proceso

Operaciones disponibles:
  CREATE  → crear_receta(datos)
  READ    → obtener_receta(id), listar_recetas(), buscar_por_polimero(polimero)
  UPDATE  → actualizar_receta(id, datos)
  UTILITY → receta_a_config(id)  →  retorna dict de configuración listo para el sistema
"""

from .gestor_db import GestorDB, gestor_global

# Modos de proceso canónicos restringidos para el sistema láser
MODOS_PROCESO_VALIDOS = {"Cutting", "Welding", "Marking"}


class GestorRecetas:
    """
    Gestiona las operaciones CRUD sobre la tabla `recetas`.

    Uso:
        gr = GestorRecetas()
        id_nuevo = gr.crear_receta({"nombre": "Mi Receta", "polimero": "Acrílico", ...})
        receta   = gr.obtener_receta(id_nuevo)
        gr.actualizar_receta(id_nuevo, {"velocidad_trazado": 1.8})
        gr.eliminar_receta(id_nuevo)
    """

    # Columnas numéricas con sus rangos de validación mínima (compatibles con galvanómetros de alta velocidad)
    _VALIDACIONES = {
        "velocidad_trazado":         (0.01, 50000.0),
        "velocidad_viaje":           (0.01, 50000.0),
        "num_pasadas":               (1, 999),
        "laser_on_delay_ms":         (0, 10000),
        "laser_off_delay_ms":        (0, 10000),
        "mark_delay_ms":             (0, 10000),
        "jump_delay_ms":             (0, 10000),
        "tolerancia_rdp":            (0.0, 10.0),
        "tolerancia_union":          (0.0, 10.0),
        "longitud_min_trazo":        (0.0, 10.0),
        "escala_dibujo":             (0.01, 1.0),
        "duracion_min_segmento_ms":  (0, 10000),
        "duracion_min_viaje_ms":     (0, 10000),
        "optimizar_tsp":             (0, 1),
        "cooling_delay_s":           (0.0, 3600.0),
        "invert_x":                  (0, 1),
        "invert_y":                  (0, 1),
        "swap_xy":                   (0, 1),
    }

    def __init__(self, gestor: GestorDB = None):
        self._db = gestor or gestor_global

    # ----------------------------------------------------------
    # CREATE
    # ----------------------------------------------------------
    def crear_receta(self, datos: dict) -> int:
        """
        Inserta una nueva receta en la base de datos.

        Args:
            datos: Diccionario con los campos de la receta.
                   'nombre' y 'polimero' son obligatorios.

        Returns:
            int: ID autoincremental de la receta creada.

        Raises:
            ValueError: Si falta 'nombre' o 'polimero', o si ya existe ese nombre.
            sqlite3.IntegrityError: Si el nombre ya existe (UNIQUE constraint).
        """
        if not datos.get("nombre", "").strip():
            raise ValueError("El campo 'nombre' es obligatorio y no puede estar vacío.")
        if not datos.get("polimero", "").strip():
            raise ValueError("El campo 'polimero' es obligatorio.")

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
        # Aplicar valores por defecto para campos opcionales no enviados
        registro = self._aplicar_defaults(datos)

        with self._db.conexion() as conn:
            cursor = conn.execute(sql, registro)
            nuevo_id = cursor.lastrowid

        print(f"[Recetas] [OK] Receta creada: '{datos['nombre']}' (ID={nuevo_id})")
        return nuevo_id

    # ----------------------------------------------------------
    # READ
    # ----------------------------------------------------------
    def obtener_receta(self, receta_id: int) -> dict:
        """
        Recupera una receta por su ID.

        Returns:
            dict con todos los campos de la receta, o {} si no existe.
        """
        sql = "SELECT * FROM recetas WHERE id = ?"
        with self._db.conexion() as conn:
            row = conn.execute(sql, (receta_id,)).fetchone()
        return self._db.fila_a_dict(row)

    def obtener_receta_por_nombre(self, nombre: str) -> dict:
        """
        Recupera una receta buscando por nombre exacto (case-insensitive).

        Returns:
            dict con todos los campos, o {} si no existe.
        """
        sql = "SELECT * FROM recetas WHERE LOWER(nombre) = LOWER(?)"
        with self._db.conexion() as conn:
            row = conn.execute(sql, (nombre.strip(),)).fetchone()
        return self._db.fila_a_dict(row)

    def listar_recetas(self) -> list:
        """
        Retorna todas las recetas ordenadas por nombre ascendente.

        Returns:
            list[dict]: Lista de todas las recetas como diccionarios.
        """
        sql = "SELECT * FROM recetas ORDER BY nombre ASC"
        with self._db.conexion() as conn:
            rows = conn.execute(sql).fetchall()
        return [self._db.fila_a_dict(r) for r in rows]

    def buscar_por_polimero(self, polimero: str) -> list:
        """
        Filtra recetas por tipo de polímero (búsqueda parcial, case-insensitive).

        Args:
            polimero: Texto a buscar dentro del campo 'polimero'.

        Returns:
            list[dict]: Recetas cuyo campo polimero contiene el texto.
        """
        sql = "SELECT * FROM recetas WHERE LOWER(polimero) LIKE LOWER(?) ORDER BY nombre ASC"
        with self._db.conexion() as conn:
            rows = conn.execute(sql, (f"%{polimero}%",)).fetchall()
        return [self._db.fila_a_dict(r) for r in rows]

    # ----------------------------------------------------------
    # UPDATE
    # ----------------------------------------------------------
    def actualizar_receta(self, receta_id: int, datos: dict) -> bool:
        """
        Actualiza los campos especificados en 'datos' de la receta con el ID dado.
        Solo se actualizan los campos presentes en el diccionario (actualización parcial).

        Args:
            receta_id: ID de la receta a modificar.
            datos: Diccionario con solo los campos que cambian.

        Returns:
            True si se modificó al menos 1 fila. False si el ID no existe.

        Raises:
            ValueError: Si se intenta cambiar el nombre a uno ya existente.
        """
        if not datos:
            return False

        self._validar_rangos(datos)

        # Construir SET dinámico solo con los campos enviados (sin tocar el resto)
        campos_editables = {
            "nombre", "polimero", "notas",
            "velocidad_trazado", "velocidad_viaje", "num_pasadas",
            "laser_on_delay_ms", "laser_off_delay_ms", "mark_delay_ms", "jump_delay_ms",
            "tolerancia_rdp", "tolerancia_union", "longitud_min_trazo",
            "escala_dibujo", "rotar_90_grados",
            "duracion_min_segmento_ms", "duracion_min_viaje_ms", "optimizar_tsp", "modo_proceso",
            "cooling_delay_s", "invert_x", "invert_y", "swap_xy"
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

    # ----------------------------------------------------------
    # DELETE
    # ----------------------------------------------------------
    def eliminar_receta(self, receta_id: int) -> bool:
        """
        Elimina la receta con el ID especificado.
        Las entradas en historial_produccion que referencian esta receta
        quedan con receta_id = NULL (ON DELETE SET NULL).

        Args:
            receta_id: ID de la receta a eliminar.

        Returns:
            True si se eliminó. False si no existía.
        """
        # Guardar nombre antes de eliminar (para el log de confirmación)
        receta = self.obtener_receta(receta_id)
        nombre_prev = receta.get("nombre", f"ID={receta_id}")

        sql = "DELETE FROM recetas WHERE id = ?"
        with self._db.conexion() as conn:
            cursor = conn.execute(sql, (receta_id,))
            filas = cursor.rowcount

        if filas > 0:
            print(f"[Recetas] [DEL] Receta eliminada: '{nombre_prev}' (ID={receta_id})")
        else:
            print(f"[Recetas] [AVISO] No se encontro receta con ID={receta_id}.")
        return filas > 0

    # ----------------------------------------------------------
    # UTILITY
    # ----------------------------------------------------------
    def receta_a_config(self, receta_id: int) -> dict:
        """
        Convierte una receta almacenada en la base de datos al formato
        de parámetros de ejecución del sistema.

        Returns:
            dict con claves compatibles con las variables de config_galvo.py,
            o {} si la receta no existe.
        """
        receta = self.obtener_receta(receta_id)
        if not receta:
            return {}

        return {
            # Cinemáticos
            "velocidad_trazado":        receta.get("velocidad_trazado", 2.0),
            "velocidad_viaje":          receta.get("velocidad_viaje", 3.5),
            "num_pasadas":              receta.get("num_pasadas", 1),
            "duracion_min_segmento_ms": receta.get("duracion_min_segmento_ms", 50),
            "duracion_min_viaje_ms":    receta.get("duracion_min_viaje_ms", 300),
            "optimizar_tsp":            bool(receta.get("optimizar_tsp", 1)),
            "modo_proceso":             receta.get("modo_proceso", "Cutting"),
            "cooling_delay_s":          float(receta.get("cooling_delay_s", 0.0)),
            "invert_x":                 bool(receta.get("invert_x", 0)),
            "invert_y":                 bool(receta.get("invert_y", 0)),
            "swap_xy":                  bool(receta.get("swap_xy", 0)),
            # Temporización óptica
            "laser_on_delay_ms":        receta.get("laser_on_delay_ms", 0),
            "laser_off_delay_ms":       receta.get("laser_off_delay_ms", 0),
            "mark_delay_ms":            receta.get("mark_delay_ms", 0),
            "jump_delay_ms":            receta.get("jump_delay_ms", 0),
            # Geométricos
            "tolerancia_rdp":           receta.get("tolerancia_rdp", 0.0),
            "tolerancia_union":         receta.get("tolerancia_union", 0.08),
            "longitud_min_trazo":       receta.get("longitud_min_trazo", 0.01),
            "escala_dibujo":            receta.get("escala_dibujo", 0.90),
            "rotar_90_grados":          bool(receta.get("rotar_90_grados", 0)),
            # Metadatos
            "_receta_id":               receta.get("id"),
            "_receta_nombre":           receta.get("nombre", "Manual"),
            "_polimero":                receta.get("polimero", "General"),
        }

    # ----------------------------------------------------------
    # PRIVADOS: Validación y Defaults
    # ----------------------------------------------------------
    def _validar_rangos(self, datos: dict):
        """Valida que los valores numéricos y atributos estén dentro de rangos y opciones físicamente válidos."""
        for campo, (minv, maxv) in self._VALIDACIONES.items():
            if campo in datos:
                val = datos[campo]
                if not (minv <= float(val) <= maxv):
                    raise ValueError(
                        f"El campo '{campo}' tiene valor {val}, fuera del rango permitido [{minv}, {maxv}]."
                    )
        if "modo_proceso" in datos and datos["modo_proceso"] is not None:
            m_str = str(datos["modo_proceso"]).strip()
            modos_norm = {m.lower(): m for m in MODOS_PROCESO_VALIDOS}
            if m_str.lower() in modos_norm:
                datos["modo_proceso"] = modos_norm[m_str.lower()]
            else:
                permitidos = sorted(list(MODOS_PROCESO_VALIDOS))
                raise ValueError(
                    f"Modo de proceso no válido: '{datos['modo_proceso']}'. "
                    f"Valores permitidos: {permitidos}."
                )

    def _aplicar_defaults(self, datos: dict) -> dict:
        """Devuelve el dict con valores por defecto para los campos no enviados."""
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
