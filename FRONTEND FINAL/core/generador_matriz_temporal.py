# -*- coding: utf-8 -*-
"""
core/generador_matriz_temporal.py — Generador de Matriz Temporal 2×n para Galvo

Convierte la secuencia de segmentos lineales producida por LectorGcode (o
LectorDXF) en una matriz de voltajes analógicos lista para ser enviada al
DAQ (NI PXI-6229) a frecuencia de muestreo constante f_s.

Fundamento matemático
---------------------
Para cada segmento (x1, y1) → (x2, y2) a velocidad v [mm/s]:

    d = sqrt((x2-x1)² + (y2-y1)²)   [mm]
    T = d / v                         [s]
    N = round(T · f_s)               [muestras]

    t_k  = k · Δt  para k = 0 … N-1
    x(t_k) = x1 + (x2-x1)/T · t_k
    y(t_k) = y1 + (y2-y1)/T · t_k

Conversión a voltaje (calibración lineal):
    V_x(k) = k_vx · x(t_k) + V_off_x
    V_y(k) = k_vy · y(t_k) + V_off_y

Clamping estricto a ±10 V para proteger el GVS112/M:
    V_x = np.clip(V_x, -10.0, 10.0)
    V_y = np.clip(V_y, -10.0, 10.0)

Retardos galvanométricos
------------------------
Los retardos se inyectan como muestras adicionales en posición fija:
  · Jump Delay   → tras cada G0/VIAJE, N_jd muestras en la posición destino
  · Laser-On  Delay → al inicio de cada CORTE, N_lon muestras con láser=0
  · Laser-Off Delay → al final  de cada CORTE, N_lof muestras con láser=0

Salida estándar
---------------
  M   : np.ndarray shape (2, n)   — fila 0: V_x, fila 1: V_y
  L   : np.ndarray shape (n,)     — 0 = láser apagado, 1 = láser encendido (dtype bool)
  info: dict con metadatos (n muestras, tiempo total, trazos, etc.)
"""

import math
from typing import Dict, List, Optional, Tuple, Union

import numpy as np


# ---------------------------------------------------------------------------
# Tipo de segmento compatible con lector_gcode.py y lector_dxf.py
# ---------------------------------------------------------------------------
Segmento = Dict   # {"tipo": str, "x1","y1","x2","y2": float, "feed": float, "laser_on": bool}


class GeneradorMatrizTemporal:
    """
    Discretizador cinemático de trayectorias vectoriales a señales analógicas.

    Parámetros
    ----------
    fs : float
        Frecuencia de muestreo [Hz]. Típico: 100 000 Hz (100 kS/s).
    escala_vx : float
        Factor de conversión mm → V eje X [V/mm].
    escala_vy : float
        Factor de conversión mm → V eje Y [V/mm].
    offset_vx : float
        Voltaje de cero eje X [V].
    offset_vy : float
        Voltaje de cero eje Y [V].
    jump_delay_us : float
        Retardo de Jump (estabilización mecánica) [µs].
    laser_on_delay_us : float
        Retardo de encendido de láser [µs].
    laser_off_delay_us : float
        Retardo de apagado de láser [µs].
    velocidad_defecto_mm_s : float
        Velocidad usada si el segmento no especifica feed [mm/s].
    velocidad_viaje_mm_s : float
        Velocidad de viaje para segmentos VIAJE sin feed [mm/s].
    n_min_por_segmento : int
        Número mínimo de muestras por segmento (evita segmentos de longitud 0).
    """

    V_MAX = 10.0   # Límite físico ±10 V del GVS112/M

    def __init__(
        self,
        fs: float               = 100_000.0,
        escala_vx: float        = 0.20,
        escala_vy: float        = 0.20,
        offset_vx: float        = 0.00,
        offset_vy: float        = 0.00,
        jump_delay_us: float    = 250.0,
        laser_on_delay_us: float  = 100.0,
        laser_off_delay_us: float =  50.0,
        velocidad_defecto_mm_s: float  = 500.0,
        velocidad_viaje_mm_s: float    = 2_000.0,
        n_min_por_segmento: int        = 2,
    ):
        if fs <= 0:
            raise ValueError("fs debe ser positiva.")

        self.fs                    = fs
        self.dt                    = 1.0 / fs
        self.escala_vx             = escala_vx
        self.escala_vy             = escala_vy
        self.offset_vx             = offset_vx
        self.offset_vy             = offset_vy
        self.n_min                 = max(1, n_min_por_segmento)

        # Retardos convertidos a número de muestras enteras
        self._n_jump_delay  = max(0, round(jump_delay_us    * 1e-6 * fs))
        self._n_lon_delay   = max(0, round(laser_on_delay_us  * 1e-6 * fs))
        self._n_lof_delay   = max(0, round(laser_off_delay_us * 1e-6 * fs))

        self._v_def  = velocidad_defecto_mm_s
        self._v_viaje = velocidad_viaje_mm_s

    # ------------------------------------------------------------------
    # API pública principal
    # ------------------------------------------------------------------
    def generar(
        self,
        segmentos: List[Segmento],
    ) -> Tuple[np.ndarray, np.ndarray, Dict]:
        """
        Discretiza una lista de segmentos y retorna la matriz de voltajes.

        Parámetros
        ----------
        segmentos : list[dict]
            Salida de LectorGcode.leer() o equivalente de trayectorias DXF.

        Retorna
        -------
        M : np.ndarray (2, n)
            Fila 0 → V_x, Fila 1 → V_y. Clamped a ±10 V.
        L : np.ndarray (n,) dtype bool
            True = láser activo en esa muestra.
        info : dict
            Metadatos: n_muestras, tiempo_total_s, n_segmentos_corte,
            n_segmentos_viaje, max_vx, max_vy.
        """
        if not segmentos:
            vacio = np.zeros((2, 0))
            return vacio, np.zeros(0, dtype=bool), {"n_muestras": 0}

        bloques_vx: List[np.ndarray] = []
        bloques_vy: List[np.ndarray] = []
        bloques_laser: List[np.ndarray] = []

        n_corte = 0
        n_viaje = 0
        laser_activo_previo = False

        for seg in segmentos:
            es_corte = bool(seg.get("laser_on", False))

            # Velocidad efectiva del segmento
            feed_mm_min = float(seg.get("feed", 0.0))
            if feed_mm_min > 0:
                v_mm_s = feed_mm_min / 60.0
            else:
                v_mm_s = self._v_def if es_corte else self._v_viaje

            x1, y1 = float(seg["x1"]), float(seg["y1"])
            x2, y2 = float(seg["x2"]), float(seg["y2"])

            d = math.hypot(x2 - x1, y2 - y1)
            if d < 1e-12:
                continue   # Segmento de longitud nula — ignorar

            T = d / max(v_mm_s, 1e-6)
            N = max(self.n_min, round(T * self.fs))

            # --- Inyección de retardos al comienzo de un CORTE ---
            if es_corte and not laser_activo_previo and self._n_lon_delay > 0:
                # Laser-On Delay: muestras en posición x1,y1 con láser apagado
                vx_lon, vy_lon = self._punto_a_voltaje(x1, y1)
                bloques_vx.append(   np.full(self._n_lon_delay, vx_lon))
                bloques_vy.append(   np.full(self._n_lon_delay, vy_lon))
                bloques_laser.append(np.zeros(self._n_lon_delay, dtype=bool))

            # --- Inyección de Jump Delay al comienzo de un VIAJE ---
            if not es_corte and self._n_jump_delay > 0:
                # Jump Delay: muestras en posición x1,y1 con láser apagado
                vx_jd, vy_jd = self._punto_a_voltaje(x1, y1)
                bloques_vx.append(   np.full(self._n_jump_delay, vx_jd))
                bloques_vy.append(   np.full(self._n_jump_delay, vy_jd))
                bloques_laser.append(np.zeros(self._n_jump_delay, dtype=bool))

            # --- Discretización paramétrica del segmento ---
            t_k  = np.arange(N) * self.dt
            T_seg = T   # duración del segmento
            x_k  = x1 + (x2 - x1) / T_seg * t_k
            y_k  = y1 + (y2 - y1) / T_seg * t_k

            vx_k = self.escala_vx * x_k + self.offset_vx
            vy_k = self.escala_vy * y_k + self.offset_vy

            laser_k = np.ones(N, dtype=bool) if es_corte else np.zeros(N, dtype=bool)

            bloques_vx.append(vx_k)
            bloques_vy.append(vy_k)
            bloques_laser.append(laser_k)

            # --- Inyección de Laser-Off Delay al final de un CORTE ---
            if es_corte and self._n_lof_delay > 0:
                vx_lof, vy_lof = self._punto_a_voltaje(x2, y2)
                bloques_vx.append(   np.full(self._n_lof_delay, vx_lof))
                bloques_vy.append(   np.full(self._n_lof_delay, vy_lof))
                bloques_laser.append(np.zeros(self._n_lof_delay, dtype=bool))

            laser_activo_previo = es_corte
            if es_corte:
                n_corte += 1
            else:
                n_viaje += 1

        # --- Concatenar todos los bloques ---
        if not bloques_vx:
            vacio = np.zeros((2, 0))
            return vacio, np.zeros(0, dtype=bool), {"n_muestras": 0}

        Vx = np.concatenate(bloques_vx)
        Vy = np.concatenate(bloques_vy)
        L  = np.concatenate(bloques_laser)

        # --- Clamping estricto ±10 V ---
        Vx = np.clip(Vx, -self.V_MAX, self.V_MAX)
        Vy = np.clip(Vy, -self.V_MAX, self.V_MAX)

        M = np.vstack([Vx, Vy])   # shape (2, n)

        n = M.shape[1]
        tiempo_total_s = n * self.dt

        info = {
            "n_muestras":          n,
            "tiempo_total_s":      round(tiempo_total_s, 6),
            "n_segmentos_corte":   n_corte,
            "n_segmentos_viaje":   n_viaje,
            "max_vx":              float(np.max(np.abs(Vx))) if n > 0 else 0.0,
            "max_vy":              float(np.max(np.abs(Vy))) if n > 0 else 0.0,
            "fs":                  self.fs,
        }

        print(
            f"[MatrizTemporal] n={n:,} muestras | "
            f"T={tiempo_total_s:.4f} s | "
            f"Corte: {n_corte} seg | Viaje: {n_viaje} seg | "
            f"|Vx|_max={info['max_vx']:.3f} V | |Vy|_max={info['max_vy']:.3f} V"
        )
        return M, L, info

    # ------------------------------------------------------------------
    # Generador a partir de trayectorias DXF (lista de rutas de puntos)
    # ------------------------------------------------------------------
    def desde_trayectorias_dxf(
        self,
        trayectorias: List[List[Tuple[float, float]]],
        velocidad_corte_mm_s: float  = 500.0,
        velocidad_viaje_mm_s: float  = 2_000.0,
        posicion_inicial: Tuple[float, float] = (0.0, 0.0),
    ) -> Tuple[np.ndarray, np.ndarray, Dict]:
        """
        Convierte trayectorias DXF (listas de puntos) al formato de segmentos
        y llama a generar().

        Parámetros
        ----------
        trayectorias : list[list[tuple]]
            Lista de rutas, cada ruta es una lista de (x, y) en mm.
        velocidad_corte_mm_s : float
            Velocidad de marcado con láser activo [mm/s].
        velocidad_viaje_mm_s : float
            Velocidad de desplazamiento en vacío [mm/s].
        posicion_inicial : tuple
            Posición de inicio antes del primer trazo (por defecto origen).

        Retorna
        -------
        Igual que generar(): (M, L, info)
        """
        segmentos: List[Segmento] = []
        pos_x, pos_y = posicion_inicial

        feed_corte_mm_min = velocidad_corte_mm_s * 60.0
        feed_viaje_mm_min = velocidad_viaje_mm_s * 60.0

        for ruta in trayectorias:
            if not ruta:
                continue

            # Viaje desde posición actual hasta primer punto de la ruta
            px0, py0 = ruta[0]
            if math.hypot(px0 - pos_x, py0 - pos_y) > 1e-9:
                segmentos.append({
                    "tipo": "VIAJE",
                    "x1": pos_x, "y1": pos_y,
                    "x2": px0,   "y2": py0,
                    "feed": feed_viaje_mm_min,
                    "potencia": 0.0,
                    "laser_on": False,
                })
            pos_x, pos_y = px0, py0

            # Segmentos de corte a lo largo de la ruta
            for i in range(1, len(ruta)):
                px1, py1 = ruta[i]
                segmentos.append({
                    "tipo": "CORTE",
                    "x1": pos_x, "y1": pos_y,
                    "x2": px1,   "y2": py1,
                    "feed": feed_corte_mm_min,
                    "potencia": 1.0,
                    "laser_on": True,
                })
                pos_x, pos_y = px1, py1

        return self.generar(segmentos)

    # ------------------------------------------------------------------
    # Métodos de utilidad pública
    # ------------------------------------------------------------------
    def tiempo_estimado_s(self, segmentos: List[Segmento]) -> float:
        """
        Calcula el tiempo total de ejecución analíticamente sin discretizar.

        Fórmula: T = Σ (d_i / v_i) + retardos

        Retorna el tiempo en segundos.
        """
        t_total = 0.0
        laser_previo = False

        for seg in segmentos:
            es_corte = bool(seg.get("laser_on", False))
            feed_mm_min = float(seg.get("feed", 0.0))
            v_mm_s = (feed_mm_min / 60.0) if feed_mm_min > 0 else (
                self._v_def if es_corte else self._v_viaje
            )
            d = math.hypot(
                float(seg["x2"]) - float(seg["x1"]),
                float(seg["y2"]) - float(seg["y1"])
            )
            if d < 1e-12:
                continue

            t_total += d / max(v_mm_s, 1e-6)

            # Retardos de galvo
            if not es_corte:
                t_total += self._n_jump_delay * self.dt
            if es_corte and not laser_previo:
                t_total += self._n_lon_delay * self.dt
            if es_corte:
                t_total += self._n_lof_delay * self.dt

            laser_previo = es_corte

        return t_total

    def centrar_espejos_voltaje(self) -> Tuple[float, float]:
        """Retorna (0.0+offset, 0.0+offset) para posicionar espejos en centro óptico."""
        return (self.offset_vx, self.offset_vy)

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------
    def _punto_a_voltaje(self, x_mm: float, y_mm: float) -> Tuple[float, float]:
        vx = np.clip(self.escala_vx * x_mm + self.offset_vx, -self.V_MAX, self.V_MAX)
        vy = np.clip(self.escala_vy * y_mm + self.offset_vy, -self.V_MAX, self.V_MAX)
        return float(vx), float(vy)


# ---------------------------------------------------------------------------
# Función de conveniencia de alto nivel
# ---------------------------------------------------------------------------
def generar_matriz_desde_gcode(
    ruta_gcode: str,
    fs: float = 100_000.0,
    escala_vx: float = 0.20,
    escala_vy: float = 0.20,
    **kwargs,
) -> Tuple[np.ndarray, np.ndarray, Dict]:
    """
    Pipeline completo: lee G-code y retorna (M, L, info) listos para el DAQ.

    Ejemplo
    -------
    >>> M, L, info = generar_matriz_desde_gcode("pieza.gcode")
    >>> print(f"Tiempo estimado: {info['tiempo_total_s']:.2f} s")
    """
    from core.lector_gcode import LectorGcode
    segmentos = LectorGcode(ruta_gcode).leer()
    gen = GeneradorMatrizTemporal(fs=fs, escala_vx=escala_vx, escala_vy=escala_vy, **kwargs)
    return gen.generar(segmentos)
