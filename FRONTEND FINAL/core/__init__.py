# core/__init__.py
"""
Paquete Core del Sistema de Trazado Láser Vectorial
Módulos universales e independientes del hardware:
  - lector_dxf: Extracción de geometría vectorial desde archivos DXF.
  - optimizador_rutas: Algoritmos TSP (Vecinos Más Cercanos, 2-Opt) y RDP.
  - generador_trayectorias: Escalado uniforme, rotación y mapeo geométrico.
  - visualizador: Generación de previsualizaciones gráficas y diagnósticos.
"""
from .lector_dxf import LectorDXF, obtener_limites_dxf
from .optimizador_rutas import optimizar_y_unir_trazos, simplificar_trayectoria_rdp
from .generador_trayectorias import transformar_y_escalar_dxf
from .visualizador import generar_previsualizacion
