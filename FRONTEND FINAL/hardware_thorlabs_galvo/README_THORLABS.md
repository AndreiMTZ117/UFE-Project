# Integración Cabezal Galvanométrico Thorlabs GVS112/M

El sistema está diseñado exclusivamente para el cabezal galvanométrico Thorlabs GVS112/M con soporte dual:
- **MODO: SIMULACIÓN**: Emula la reproducción, calcula estadísticas temporales y voltajes sin requerir hardware físico.
- **MODO: PXI-6229 REAL**: Control por hardware síncrono mediante NI DAQmx y tarjeta NI PXI-6229.

## Configuración de Operación:

En `hardware_thorlabs_galvo/config_galvo.py`:

```python
# Para operar en simulación virtual (sin hardware conectado):
MODO_HARDWARE = 'SIMULACION'

# Para operar conectado al chasis PXIe-1073 con tarjeta PXI-6229:
MODO_HARDWARE = 'REAL'
```

## Pruebas de Diagnóstico:
Se incluye un script de comprobación independiente del sistema:
```bash
python hardware_thorlabs_galvo/test_hardware.py
```
Verifica la presencia de `nidaqmx`, la detección del chasis/tarjeta en el sistema operativo y ejecuta un patrón de calibración en cruz de $\pm 1\text{ V}$ para verificar el movimiento de los espejos antes de encender el láser.
