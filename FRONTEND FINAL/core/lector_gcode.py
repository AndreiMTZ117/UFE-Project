# -*- coding: utf-8 -*-
"""
core/lector_gcode.py — Intérprete de G-code (ISO 6983) para Thorlabs GVS112/M

Soporta archivos generados por dxf2gcode, FreeCAD Path Workbench y
otras cadenas CAM estándar (.gcode, .nc, .ngc).

Entidades interpretadas
-----------------------
  G0 X... Y...          Salto rápido en vacío  (laser apagado, velocidad de viaje)
  G1 X... Y... F...     Movimiento lineal activo (laser encendido, velocidad de corte)
  M3 [S<potencia>]      Activar laser / inicio de corte
  M5                    Desactivar laser
  S<valor>              Potencia del laser (0–255 o 0.0–1.0, se normaliza a [0,1])
  ;  o  (...)           Comentarios — se ignoran

Salida
------
  list[dict] con una entrada por segmento:
    {
        "tipo":      "CORTE" | "VIAJE",
        "x1": float, "y1": float,   # punto de inicio [mm]
        "x2": float, "y2": float,   # punto de destino [mm]
        "feed": float,              # velocidad [mm/min], 0.0 si no especificada
        "potencia": float,          # 0.0 – 1.0 (normalizado)
        "laser_on": bool,           # True si el laser debe estar activo en este tramo
    }
"""

import re
import os
from typing import List, Dict, Optional


# ---------------------------------------------------------------------------
# Expresiones regulares de captura de palabras G-code
# ---------------------------------------------------------------------------
_RE_WORD = re.compile(
    r'([A-Z])\s*([-+]?\d*\.?\d+)',
    re.IGNORECASE
)
_RE_COMMENT_PAREN  = re.compile(r'\(.*?\)')    # comentarios entre paréntesis
_RE_COMMENT_SEMI   = re.compile(r';.*$')       # comentarios desde punto y coma


def _limpiar_linea(linea: str) -> str:
    """Elimina comentarios y espacios sobrantes de una linea G-code."""
    linea = _RE_COMMENT_PAREN.sub('', linea)
    linea = _RE_COMMENT_SEMI.sub('', linea)
    return linea.strip().upper()


def _extraer_palabras(linea: str) -> Dict[str, float]:
    """Devuelve un dict {letra: valor} para todas las palabras de la linea."""
    return {m.group(1): float(m.group(2)) for m in _RE_WORD.finditer(linea)}


class LectorGcode:
    """
    Parser de G-code estándar orientado al control de galvanómetros.

    Parámetros
    ----------
    ruta_archivo : str
        Ruta absoluta o relativa al archivo .gcode / .nc / .ngc.
    feed_defecto_mm_min : float
        Velocidad de avance usada cuando no se especifica F en G1 [mm/min].
        Por defecto 500 mm/min (≈ 8.3 mm/s).
    feed_viaje_mm_min : float
        Velocidad de viaje usada en G0 [mm/min].
        Por defecto 12000 mm/min (≈ 200 mm/s).
    """

    def __init__(
        self,
        ruta_archivo: str,
        feed_defecto_mm_min: float = 500.0,
        feed_viaje_mm_min: float   = 12_000.0,
    ):
        if not os.path.isfile(ruta_archivo):
            raise FileNotFoundError(f"[LectorGcode] No se encontro: {ruta_archivo}")

        self.ruta_archivo       = ruta_archivo
        self.feed_defecto       = feed_defecto_mm_min
        self.feed_viaje         = feed_viaje_mm_min

        # Estado continuo de la máquina
        self._x: float          = 0.0
        self._y: float          = 0.0
        self._feed: float       = feed_defecto_mm_min
        self._laser_on: bool    = False
        self._potencia: float   = 1.0       # 0.0–1.0 normalizada
        self._modal_g: int      = 0         # G modal activo (0 o 1)

        self._segmentos: List[Dict] = []

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def leer(self) -> List[Dict]:
        """
        Parsea el archivo y retorna la lista de segmentos.

        Returns
        -------
        list[dict]
            Cada dict describe un segmento lineal con tipo, coordenadas,
            velocidad, potencia y estado del laser.
        """
        self._segmentos = []
        self._x = self._y = 0.0
        self._feed = self.feed_defecto
        self._laser_on = False
        self._potencia = 1.0
        self._modal_g = 0

        with open(self.ruta_archivo, 'r', encoding='utf-8', errors='replace') as fh:
            for n_linea, linea_raw in enumerate(fh, start=1):
                linea = _limpiar_linea(linea_raw)
                if not linea:
                    continue
                try:
                    self._procesar_linea(linea)
                except Exception as exc:
                    print(f"[LectorGcode] Aviso en linea {n_linea}: {exc}  -> '{linea_raw.rstrip()}'")

        print(
            f"[LectorGcode] Parseado '{os.path.basename(self.ruta_archivo)}': "
            f"{len(self._segmentos)} segmentos extraidos."
        )
        return self._segmentos

    @property
    def segmentos(self) -> List[Dict]:
        """Lista de segmentos (disponible tras llamar a leer())."""
        return self._segmentos

    def segmentos_corte(self) -> List[Dict]:
        """Filtra y retorna solo los segmentos con laser activo."""
        return [s for s in self._segmentos if s["laser_on"]]

    def segmentos_viaje(self) -> List[Dict]:
        """Filtra y retorna solo los segmentos de viaje en vacío."""
        return [s for s in self._segmentos if not s["laser_on"]]

    # ------------------------------------------------------------------
    # Motor interno de interpretación
    # ------------------------------------------------------------------
    def _procesar_linea(self, linea: str):
        palabras = _extraer_palabras(linea)

        # 1. Actualizar potencia si aparece S en esta linea
        if 'S' in palabras:
            raw_s = palabras['S']
            # Normalizar: si el valor > 1 se asume escala 0-255
            self._potencia = raw_s / 255.0 if raw_s > 1.0 else raw_s
            self._potencia = max(0.0, min(1.0, self._potencia))

        # 2. Procesar M-codes primero (control de laser)
        if 'M' in palabras:
            m_val = int(palabras['M'])
            if m_val == 3:    # M3 → laser ON
                self._laser_on = True
            elif m_val in (5, 2, 30):  # M5 / M2 / M30 → laser OFF / fin programa
                self._laser_on = False

        # 3. Actualizar feed si se especifica en esta linea
        if 'F' in palabras and palabras['F'] > 0:
            self._feed = palabras['F']

        # 4. Determinar código G activo (modal)
        if 'G' in palabras:
            g_val = int(palabras['G'])
            if g_val in (0, 1):
                self._modal_g = g_val

        # 5. Si hay movimiento (X o Y presentes), generar segmento
        tiene_movimiento = ('X' in palabras) or ('Y' in palabras)
        if not tiene_movimiento:
            return

        x2 = palabras.get('X', self._x)
        y2 = palabras.get('Y', self._y)

        # Ignorar segmentos de longitud cero
        if abs(x2 - self._x) < 1e-9 and abs(y2 - self._y) < 1e-9:
            self._x, self._y = x2, y2
            return

        es_viaje = (self._modal_g == 0)
        segmento = {
            "tipo":     "VIAJE" if es_viaje else "CORTE",
            "x1":       self._x,
            "y1":       self._y,
            "x2":       x2,
            "y2":       y2,
            "feed":     self.feed_viaje if es_viaje else self._feed,
            "potencia": 0.0 if es_viaje else self._potencia,
            "laser_on": False if es_viaje else self._laser_on,
        }
        self._segmentos.append(segmento)

        # Actualizar posición de máquina
        self._x, self._y = x2, y2


# ---------------------------------------------------------------------------
# Función de conveniencia
# ---------------------------------------------------------------------------
def leer_gcode(ruta_archivo: str, **kwargs) -> List[Dict]:
    """
    Función de nivel superior para parsear un archivo G-code directamente.

    Ejemplo
    -------
    >>> segmentos = leer_gcode("pieza.gcode")
    >>> cortes = [s for s in segmentos if s["laser_on"]]
    """
    return LectorGcode(ruta_archivo, **kwargs).leer()
