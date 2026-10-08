# Integracion Cabezal Galvanometrico Thorlabs GVS112/M

El sistema esta disenado con arquitectura **Hardware Abstraction Layer (HAL)**.

## Como cambiar del modo Maqueta de Servos al modo Thorlabs Galvo:

En `principal.py`, simplemente cambia una variable:

```python
# Para la maqueta de servos (ESP32):
HARDWARE_ACTIVO = 'maqueta_servos'

# Para la estacion de trabajo con cabezal Thorlabs GVS112/M:
HARDWARE_ACTIVO = 'thorlabs_galvo'
```

El procesador de DXF, el optimizador de rutas TSP, el escalado proporcional y la generacion de vectores en `core/` funcionan exactamente igual para ambas maquinas sin necesidad de modificar nada mas.
