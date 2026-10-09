# -*- coding: utf-8 -*-
"""
database/trazabilidad.py — Registro Histórico de Producción (Production Logging)

Registra automáticamente cada ciclo de grabado láser con:
  - Timestamp exacto
  - Operador responsable
  - Receta y parámetros aplicados (snapshot inmutable)
  - Archivo DXF ejecutado
  - Hardware utilizado
  - Métricas del ciclo (trazos, waypoints, duración)
  - Estado final (COMPLETADO / ABORTADO / FALLO_HARDWARE)
"""

from .gestor_db import GestorDB, gestor_global


class GestorTrazabilidad:
    """
    Gestiona las operaciones de escritura y consulta sobre la tabla
    `historial_produccion`.

    Uso típico desde principal.py:
        gt = GestorTrazabilidad()
        id_log = gt.registrar_ciclo({
            "operador":           "Técnico A",
            "archivo_dxf":        "batman.dxf",
            "hardware_usado":     "thorlabs_galvo",
            "receta_id":          2,
            "receta_nombre":      "Policarbonato — Alta Precisión",
            "velocidad_trazado":  1.0,
            "velocidad_viaje":    2.5,
            "trazos_totales":     47,
            "waypoints_totales":  3821,
            "duracion_segundos":  92.4,
            "estado":             "COMPLETADO",
        })
    """

    # Estados válidos para el campo 'estado'
    ESTADOS_VALIDOS = {"COMPLETADO", "ABORTADO", "FALLO_HARDWARE"}

    def __init__(self, gestor: GestorDB = None):
        self._db = gestor or gestor_global

    # ----------------------------------------------------------
    # WRITE: Registro de ciclo
    # ----------------------------------------------------------
    def registrar_ciclo(self, datos: dict) -> int:
        """
        Inserta un nuevo registro en el historial de producción.

        Args:
            datos: Diccionario con los campos del ciclo. Los mínimos
                   obligatorios son 'archivo_dxf' y 'estado'.

        Returns:
            int: ID del registro insertado.

        Raises:
            ValueError: Si 'archivo_dxf' está vacío o 'estado' es inválido.
        """
        if not datos.get("archivo_dxf", "").strip():
            raise ValueError("El campo 'archivo_dxf' es obligatorio.")

        estado = datos.get("estado", "COMPLETADO").upper()
        if estado not in self.ESTADOS_VALIDOS:
            raise ValueError(
                f"Estado '{estado}' no válido. Use: {self.ESTADOS_VALIDOS}"
            )

        sql = """
            INSERT INTO historial_produccion (
                operador, receta_id, receta_nombre,
                archivo_dxf, hardware_usado,
                velocidad_trazado, velocidad_viaje, num_pasadas,
                escala_dibujo, tolerancia_rdp, tolerancia_union,
                trazos_totales, waypoints_totales, duracion_segundos,
                estado, mensaje_error
            ) VALUES (
                :operador, :receta_id, :receta_nombre,
                :archivo_dxf, :hardware_usado,
                :velocidad_trazado, :velocidad_viaje, :num_pasadas,
                :escala_dibujo, :tolerancia_rdp, :tolerancia_union,
                :trazos_totales, :waypoints_totales, :duracion_segundos,
                :estado, :mensaje_error
            )
        """
        registro = self._aplicar_defaults_historial(datos)
        registro["estado"] = estado

        with self._db.conexion() as conn:
            cursor = conn.execute(sql, registro)
            nuevo_id = cursor.lastrowid

        print(
            f"[Trazabilidad] [LOG] Ciclo registrado - ID={nuevo_id} | "
            f"DXF: '{datos['archivo_dxf']}' | Estado: {estado}"
        )
        return nuevo_id

    # ----------------------------------------------------------
    # READ: Consultas del historial
    # ----------------------------------------------------------
    def listar_historial(self, limite: int = 100, offset: int = 0) -> list:
        """
        Retorna los últimos N registros del historial, más recientes primero.

        Args:
            limite:  Máximo de registros a retornar (default 100).
            offset:  Número de registros a saltar (para paginación).

        Returns:
            list[dict]: Lista de registros ordenados por timestamp DESC.
        """
        sql = """
            SELECT h.*, r.polimero
            FROM historial_produccion h
            LEFT JOIN recetas r ON h.receta_id = r.id
            ORDER BY h.id DESC
            LIMIT ? OFFSET ?
        """
        with self._db.conexion() as conn:
            rows = conn.execute(sql, (limite, offset)).fetchall()
        return [self._db.fila_a_dict(r) for r in rows]

    def obtener_registro(self, registro_id: int) -> dict:
        """
        Recupera un registro específico del historial por su ID.

        Returns:
            dict con todos los campos, o {} si no existe.
        """
        sql = "SELECT * FROM historial_produccion WHERE id = ?"
        with self._db.conexion() as conn:
            row = conn.execute(sql, (registro_id,)).fetchone()
        return self._db.fila_a_dict(row)

    def filtrar_por_operador(self, operador: str) -> list:
        """
        Retorna todos los ciclos ejecutados por un operador específico.

        Args:
            operador: Nombre del operador (búsqueda exacta, case-insensitive).
        """
        sql = """
            SELECT * FROM historial_produccion
            WHERE LOWER(operador) LIKE LOWER(?)
            ORDER BY id DESC
        """
        with self._db.conexion() as conn:
            rows = conn.execute(sql, (f"%{operador}%",)).fetchall()
        return [self._db.fila_a_dict(r) for r in rows]

    def filtrar_por_estado(self, estado: str) -> list:
        """
        Retorna todos los ciclos filtrados por estado final.

        Args:
            estado: 'COMPLETADO', 'ABORTADO' o 'FALLO_HARDWARE'.
        """
        estado = estado.upper()
        sql = """
            SELECT * FROM historial_produccion
            WHERE estado = ?
            ORDER BY id DESC
        """
        with self._db.conexion() as conn:
            rows = conn.execute(sql, (estado,)).fetchall()
        return [self._db.fila_a_dict(r) for r in rows]

    def filtrar_por_dxf(self, nombre_dxf: str) -> list:
        """
        Retorna todos los ciclos que procesaron un archivo DXF específico.

        Args:
            nombre_dxf: Nombre del archivo (búsqueda parcial).
        """
        sql = """
            SELECT * FROM historial_produccion
            WHERE LOWER(archivo_dxf) LIKE LOWER(?)
            ORDER BY id DESC
        """
        with self._db.conexion() as conn:
            rows = conn.execute(sql, (f"%{nombre_dxf}%",)).fetchall()
        return [self._db.fila_a_dict(r) for r in rows]

    def contar_ciclos_por_estado(self) -> dict:
        """
        Retorna un resumen estadístico de ciclos agrupados por estado.

        Returns:
            dict: {estado: cantidad}, por ejemplo:
                  {'COMPLETADO': 42, 'ABORTADO': 3, 'FALLO_HARDWARE': 1}
        """
        sql = "SELECT estado, COUNT(*) as total FROM historial_produccion GROUP BY estado"
        with self._db.conexion() as conn:
            rows = conn.execute(sql).fetchall()
        return {row["estado"]: row["total"] for row in rows}

    def estadisticas_generales(self) -> dict:
        """
        Retorna métricas agregadas del historial completo.

        Returns:
            dict con:
                - total_ciclos
                - duracion_promedio_s
                - duracion_total_horas
                - waypoints_totales_acumulados
        """
        sql = """
            SELECT
                COUNT(*)                         AS total_ciclos,
                AVG(duracion_segundos)           AS duracion_promedio_s,
                SUM(duracion_segundos) / 3600.0  AS duracion_total_horas,
                SUM(waypoints_totales)           AS waypoints_acumulados
            FROM historial_produccion
            WHERE estado = 'COMPLETADO'
        """
        with self._db.conexion() as conn:
            row = conn.execute(sql).fetchone()
        return self._db.fila_a_dict(row)

    # ----------------------------------------------------------
    # PRIVADOS
    # ----------------------------------------------------------
    def _aplicar_defaults_historial(self, datos: dict) -> dict:
        """Retorna el dict con valores por defecto para campos opcionales."""
        defaults = {
            "operador":           "Operador",
            "receta_id":          None,
            "receta_nombre":      "Manual",
            "archivo_dxf":        "",
            "hardware_usado":     "thorlabs_galvo",
            "velocidad_trazado":  None,
            "velocidad_viaje":    None,
            "num_pasadas":        1,
            "escala_dibujo":      None,
            "tolerancia_rdp":     None,
            "tolerancia_union":   None,
            "trazos_totales":     0,
            "waypoints_totales":  0,
            "duracion_segundos":  0.0,
            "estado":             "COMPLETADO",
            "mensaje_error":      "",
        }
        defaults.update(datos)
        return defaults
