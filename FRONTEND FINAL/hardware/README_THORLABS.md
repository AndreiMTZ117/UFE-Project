# Integración Cabezal Galvanométrico Thorlabs GVS112/M

El sistema está diseñado con una arquitectura **Hardware Abstraction Layer (HAL)** dedicada exclusivamente para el cabezal de escaneo galvanométrico **Thorlabs GVS112/M** y su entorno de simulación virtual de alta fidelidad.

## Modos de Operación

1. **Hardware Físico Thorlabs GVS112/M**:
   - Conexión analógica dual X/Y (+/- 10V) mediante tarjeta DAQ/DAC (National Instruments, LabJack o DAC de alta velocidad).
   - Control de modulación del láser mediante línea digital TTL (0V = Haz apagado, 5V = Emisión activa).
   - Se activa automáticamente cuando la tarjeta de interfaz está conectada y configurada.

2. **Modo Simulación Virtual (`SimuladorThorlabsGVS`)**:
   - Se activa de forma automática cuando el hardware físico no está presente.
   - Simula con precisión los tiempos de escaneo galvanométrico respetando la velocidad de marcado (`VELOCIDAD_MARCADO_MM_S`), velocidad de salto (`VELOCIDAD_SALTO_MM_S`), y delays mecánicos/ópticos.
   - Permite la operación y prueba completa de la interfaz gráfica, visualización y trazabilidad sin necesidad de hardware conectado.
