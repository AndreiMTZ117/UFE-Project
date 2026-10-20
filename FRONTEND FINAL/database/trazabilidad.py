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

    Uso típico:
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

    # Modos de proceso canónicos restringidos
    MODOS_PROCESO_VALIDOS = {"Cutting", "Welding", "Marking"}

    # Estados válidos para el campo 'estado' (canónicos y bilingües)
    ESTADOS_VALIDOS = {
        "COMPLETADO", "ABORTADO", "FALLO_HARDWARE",
        "COMPLETED", "ABORTED", "STOPPED", "ERROR", "FAILED"
    }

    # Normalización universal a valores canónicos de la base de datos
    MAPA_ESTADOS = {
        "COMPLETADO": "COMPLETADO",
        "COMPLETED": "COMPLETADO",
        "OK": "COMPLETADO",
        "SUCCESS": "COMPLETADO",
        "EXITOSO": "COMPLETADO",
        "ABORTADO": "ABORTADO",
        "ABORTED": "ABORTADO",
        "STOPPED": "ABORTADO",
        "DETENIDO": "ABORTADO",
        "CANCELADO": "ABORTADO",
        "CANCELLED": "ABORTADO",
        "FALLO_HARDWARE": "FALLO_HARDWARE",
        "HARDWARE_FAILURE": "FALLO_HARDWARE",
        "ERROR": "FALLO_HARDWARE",
        "FAILED": "FALLO_HARDWARE",
        "FALLO": "FALLO_HARDWARE",
    }

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
            ValueError: Si 'archivo_dxf' está vacío.
        """
        # Normalizar archivo DXF
        archivo_dxf = (
            datos.get("archivo_dxf")
            or datos.get("dxf")
            or datos.get("archivo")
            or ""
        ).strip()
        if not archivo_dxf:
            archivo_dxf = "Desconocido.dxf"

        # Normalizar estado de forma resiliente
        estado_in = str(datos.get("estado") or datos.get("status") or "COMPLETADO").strip().upper()
        if estado_in in self.MAPA_ESTADOS:
            estado = self.MAPA_ESTADOS[estado_in]
        elif "COMPLET" in estado_in or "OK" in estado_in or "SUCCESS" in estado_in:
            estado = "COMPLETADO"
        elif "ABORT" in estado_in or "STOP" in estado_in or "CANCEL" in estado_in:
            estado = "ABORTADO"
        else:
            estado = "FALLO_HARDWARE"

        # Normalizar sinónimos de métricas y metadatos
        duracion = datos.get("duracion_segundos")
        if duracion is None:
            duracion = datos.get("tiempo_proceso_s", datos.get("duracion_s", datos.get("duracion", 0.0)))

        waypoints = datos.get("waypoints_totales")
        if waypoints is None:
            waypoints = datos.get("puntos_totales", datos.get("waypoints", 0))

        trazos = datos.get("trazos_totales")
        if trazos is None:
            trazos = datos.get("total_trazos", datos.get("paths_totales", datos.get("trazos", 0)))

        hardware = datos.get("hardware_usado") or datos.get("hardware") or "thorlabs_galvo"
        msg_err = datos.get("mensaje_error") if datos.get("mensaje_error") is not None else datos.get("error_msg", datos.get("error", ""))
        receta_nom = datos.get("receta_nombre") or datos.get("recipe_name") or "Manual"
        receta_id_in = datos.get("receta_id") if "receta_id" in datos else datos.get("recipe_id")

        modo_raw = str(datos.get("modo_proceso") or datos.get("modo") or "Cutting").strip()
        modo_norm_map = {m.lower(): m for m in self.MODOS_PROCESO_VALIDOS}
        modo_proceso = modo_norm_map.get(modo_raw.lower(), "Cutting")

        sql = """
            INSERT INTO historial_produccion (
                operador, receta_id, receta_nombre, modo_proceso,
                archivo_dxf, hardware_usado,
                velocidad_trazado, velocidad_viaje, num_pasadas,
                escala_dibujo, tolerancia_rdp, tolerancia_union,
                trazos_totales, waypoints_totales, duracion_segundos,
                estado, mensaje_error,
                tracking_rms_um, tracking_max_um, tracking_lag_ms
            ) VALUES (
                :operador, :receta_id, :receta_nombre, :modo_proceso,
                :archivo_dxf, :hardware_usado,
                :velocidad_trazado, :velocidad_viaje, :num_pasadas,
                :escala_dibujo, :tolerancia_rdp, :tolerancia_union,
                :trazos_totales, :waypoints_totales, :duracion_segundos,
                :estado, :mensaje_error,
                :tracking_rms_um, :tracking_max_um, :tracking_lag_ms
            )
        """
        registro = self._aplicar_defaults_historial(datos)
        registro["archivo_dxf"] = archivo_dxf
        registro["modo_proceso"] = modo_proceso
        registro["estado"] = estado
        registro["duracion_segundos"] = float(duracion or 0.0)
        registro["waypoints_totales"] = int(waypoints or 0)
        registro["trazos_totales"] = int(trazos or 0)
        registro["hardware_usado"] = str(hardware)
        registro["mensaje_error"] = str(msg_err or "")

        with self._db.conexion() as conn:
            # Resolución de receta_id para respetar la integridad referencial (FOREIGN KEY)
            receta_id_valido = None
            if receta_id_in is not None:
                try:
                    rid_int = int(receta_id_in)
                    row = conn.execute("SELECT id, nombre FROM recetas WHERE id = ?", (rid_int,)).fetchone()
                    if row:
                        receta_id_valido = row["id"]
                        if not receta_nom or receta_nom == "Manual":
                            receta_nom = row["nombre"]
                except (ValueError, TypeError):
                    row = conn.execute("SELECT id, nombre FROM recetas WHERE LOWER(nombre) = LOWER(?)", (str(receta_id_in).strip(),)).fetchone()
                    if row:
                        receta_id_valido = row["id"]
                        receta_nom = row["nombre"]

            if receta_id_valido is None and receta_nom and receta_nom != "Manual":
                row = conn.execute("SELECT id, nombre FROM recetas WHERE LOWER(nombre) = LOWER(?)", (str(receta_nom).strip(),)).fetchone()
                if row:
                    receta_id_valido = row["id"]
                    receta_nom = row["nombre"]

            registro["receta_id"] = receta_id_valido
            registro["receta_nombre"] = str(receta_nom or "Manual")

            cursor = conn.execute(sql, registro)
            nuevo_id = cursor.lastrowid

        print(
            f"[Trazabilidad] [LOG] Ciclo registrado - ID={nuevo_id} | "
            f"DXF: '{archivo_dxf}' | Modo: {modo_proceso} | Estado: {estado} | Duración: {registro['duracion_segundos']:.2f}s"
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

    # Alias para compatibilidad con llamadas tipo obtener_historial
    obtener_historial = listar_historial

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
        estado_norm = str(estado).strip().upper()
        estado_clean = self.MAPA_ESTADOS.get(estado_norm, estado_norm)
        sql = """
            SELECT * FROM historial_produccion
            WHERE estado = ?
            ORDER BY id DESC
        """
        with self._db.conexion() as conn:
            rows = conn.execute(sql, (estado_clean,)).fetchall()
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
            "modo_proceso":       "Cutting",
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
            "tracking_rms_um":    None,
            "tracking_max_um":    None,
            "tracking_lag_ms":    None,
        }
        defaults.update(datos)
        return defaults
