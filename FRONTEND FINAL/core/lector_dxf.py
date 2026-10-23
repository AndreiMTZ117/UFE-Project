# -*- coding: utf-8 -*-
"""dxf file reading and vector extraction"""

import os
import ezdxf
from ezdxf import path

def entidades_recursivas(entidades, profundidad=0, max_profundidad=12):
    """recursively explode insert blocks and dimensions"""
    if profundidad > max_profundidad:
        return

    for entidad in entidades:
        dxftype = entidad.dxftype()

        if dxftype in ('INSERT', 'DIMENSION'):
            try:
                sub_entidades = entidad.explode()
                for sub in entidades_recursivas(sub_entidades, profundidad + 1, max_profundidad):
                    yield sub
            except Exception:
                pass
        elif dxftype in ('VIEWPORT', 'MTEXT', 'TEXT', 'POINT', 'HATCH', 'IMAGE', 'UNDERLAY', 'WIPEOUT'):
            continue
        else:
            yield entidad


class LectorDXF:
    """dxf cad file reader"""

    def __init__(self, ruta_archivo):
        self.ruta_archivo = ruta_archivo
        self.doc = None
        self.espacio_modelo = None

        if not os.path.exists(ruta_archivo):
            raise FileNotFoundError(f"No se encontró el archivo DXF: '{ruta_archivo}'")

        try:
            self.doc = ezdxf.readfile(ruta_archivo)
            self.espacio_modelo = self.doc.modelspace()
            print(f"Archivo '{os.path.basename(ruta_archivo)}' cargado correctamente.")
        except Exception as e:
            raise RuntimeError(f"Error al abrir el archivo DXF '{ruta_archivo}': {e}")

    def extraer_coordenadas(self, paso_discretizacion=0.01):
        #extract vector paths by flattening curves
        if not self.espacio_modelo:
            return []

        trayectorias_laser = []
        entidades_planas = list(entidades_recursivas(self.espacio_modelo))

        for entidad in entidades_planas:
            try:
                trazo = path.make_path(entidad)
            except (TypeError, AttributeError):
                continue

            try:
                vertices = list(trazo.flattening(distance=paso_discretizacion))
            except Exception:
                continue

            coordenadas_trazo = []
            ultimo_pt = None

            for v in vertices:
                x = round(v.x, 4)
                y = round(v.y, 4)
                pt = (x, y)
                if pt != ultimo_pt:
                    coordenadas_trazo.append(pt)
                    ultimo_pt = pt

            if len(coordenadas_trazo) >= 2:
                trayectorias_laser.append(coordenadas_trazo)

        return trayectorias_laser


def obtener_limites_dxf(trayectorias):
    #calculate bounding box of trajectories
    puntos = [p for ruta in trayectorias for p in ruta]
    if not puntos:
        return 0.0, 1.0, 0.0, 1.0
    min_x = min(p[0] for p in puntos)
    max_x = max(p[0] for p in puntos)
    min_y = min(p[1] for p in puntos)
    max_y = max(p[1] for p in puntos)
    return min_x, max_x, min_y, max_y
