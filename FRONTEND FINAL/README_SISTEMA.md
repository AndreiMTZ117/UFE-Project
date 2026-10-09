# UFE Laser - Sistema de Trazado Vectorial con Thorlabs GVS112/M

## Arquitectura del Sistema

`
FRONTEND FINAL/
|-- iniciar_interfaz.py         <- Lanzador principal (HMI)
|-- principal.py                <- CLI de ejecucion sin GUI
|-- test_integracion_fases.py   <- Suite de validacion completa
|
|-- core/                       <- Motor de procesamiento vectorial
|   |-- lector_dxf.py           <- Parser ezdxf para archivos .dxf
|   |-- lector_gcode.py         <- Interprete de G-code estandar
|   |-- generador_matriz_temporal.py  <- Discretizador (Matriz DAQ V x t)
|   |-- generador_trayectorias.py     <- Escala + TSP + RDP
|   |-- optimizador_rutas.py    <- Algoritmo de optimizacion de rutas
|   -- visualizador.py         <- Generador de previsualizaciones PNG
|
|-- hardware_thorlabs_galvo/    <- Driver y configuracion de hardware
|   |-- config_galvo.py         <- *** UNICO ARCHIVO A EDITAR EN PRODUCCION ***
|   |-- controlador_thorlabs.py <- Driver unificado SIMULACION/REAL
|   |-- test_hardware.py        <- Diagnostico de tarjeta NI PXI-6229
|   -- README_THORLABS.md      <- Notas de calibracion del galvo
|
|-- interfaz/                   <- HMI CustomTkinter (Cyber-Brutalism)
|   |-- interfaz_app.py         <- Orquestador principal
|   |-- barra_superior.py       <- Indicador MODO: SIMULACION / PXI-6229 REAL
|   |-- panel_configuracion.py  <- Recetas SQLite3 y parametros cinematicos
|   |-- panel_general.py        <- Canvas isometrico 1:1 con reglas
|   |-- panel_derecho.py        <- Gauges, trace-point y controles de ciclo
|   |-- terminal_flotante.py    <- Consola de logs + historial de produccion
|   |-- conexion_interfaz.py    <- Puente backend-GUI asincrono
|   |-- gestion_datos.py        <- Carga inicial de datos
|   |-- eventos_interaccion.py  <- Callbacks del usuario
|   |-- logica_ejecucion.py     <- Ciclo START / PAUSE / STOP
|   -- renderizado_dual.py     <- Sincronizacion de canvases
|
|-- database/                   <- Persistencia SQLite3
|   |-- recetas.py              <- CRUD de recetas de material
|   -- trazabilidad.py         <- Registro de ciclos de produccion
|
-- dxf/                        <- Archivos de muestra (DXF + G-code)
`

---

## Instalacion de Dependencias

`powershell
pip install customtkinter ezdxf numpy scipy
# Solo en maquina con tarjeta NI conectada:
pip install nidaqmx
`

---

## Configuracion de Hardware (config_galvo.py)

Editar UNICAMENTE hardware_thorlabs_galvo/config_galvo.py:

`python
# Modo de operacion
MODO_HARDWARE = 'SIMULACION'   # Cambiar a 'REAL' con PXI-6229

# NI DAQ (PXI-6229)
DISPOSITIVO_NI = 'Dev1'        # Verificar en NI-MAX
CANAL_AO_X     = 'ao0'         # Eje X galvo (+/-10V)
CANAL_AO_Y     = 'ao1'         # Eje Y galvo (+/-10V)
CANAL_DO_LASER = 'port0/line0' # Compuerta laser (TTL 0/5V)

# Campo optico (lente F-Theta instalada)
CAMPO_X_MIN_MM = -50.0
CAMPO_X_MAX_MM =  50.0
CAMPO_Y_MIN_MM = -50.0
CAMPO_Y_MAX_MM =  50.0

# Calibracion optica
ESCALA_VX_POR_MM = 0.20   # V/mm
ESCALA_VY_POR_MM = 0.20   # V/mm
OFFSET_VX = 0.00           # Correccion de cero eje X [V]
OFFSET_VY = 0.00           # Correccion de cero eje Y [V]
`

IMPORTANTE: No modificar otros archivos para adaptar hardware.

---

## Ejecucion

### HMI Grafica --------------------------
`powershell
python iniciar_interfaz.py
`

### CLI (sin GUI)
`powershell
python principal.py                     # Primer DXF/G-code encontrado
python principal.py pieza.dxf           # Archivo DXF especifico
python principal.py corte.gcode         # Archivo G-code especifico
`

### Diagnostico de Hardware
`powershell
python hardware_thorlabs_galvo/test_hardware.py
`

### Validacion de Integracion
`powershell
python test_integracion_fases.py
`

---

## Flujo de Datos

`
Archivo DXF / G-code
     |
     v
  LectorDXF / LectorGcode (core/)
     |
     v
  GeneradorMatrizTemporal
  -> Matriz M[2xN] voltajes en +/-10V
  -> Mascara L[N] gate de laser
  -> Tiempo exacto T = N / fs
     |
     v
  ControladorThorlabsGVS
  |-- SIMULACION: estadisticas sin hardware
  -- REAL: NI-DAQmx -> PXI-6229 -> GVS112/M
     |
     v
  GestorTrazabilidad
  -> Registro en SQLite3
`

---

## Procedimiento de Puesta en Marcha Real (PXI-6229)

1. Conectar chasis PXI-e y verificar en NI-MAX que aparece como Dev1
2. Conectar salidas analogicas:
   - AO0 -> Entrada Eje X del GVS112/M (+/-10V)
   - AO1 -> Entrada Eje Y del GVS112/M (+/-10V)
   - P0.0 -> Compuerta TTL del laser (0V=apagado, 5V=encendido)
3. Cambiar en config_galvo.py: MODO_HARDWARE = 'REAL'
4. Ejecutar diagnostico: python hardware_thorlabs_galvo/test_hardware.py
5. Verificar con osciloscopio:
   - Senal de salida en AO0 y AO1 para un cuadrado de prueba
   - Forma de onda esperada: rampa trapezoidal de -10V a +10V
6. Ajustar ESCALA_VX_POR_MM y OFFSET_VX segun la lente F-Theta

---

## Parametros de Recetas

| Parametro               | Descripcion                        | Rango         |
|-------------------------|------------------------------------|---------------|
| velocidad_trazado       | Velocidad laser ON                 | 0.01-100 mm/s |
| velocidad_viaje         | Velocidad salto G0 (laser OFF)     | 0.01-100 mm/s |
| escala_dibujo           | Fraccion del campo optico usado    | 0.01-1.0      |
| tolerancia_rdp          | Simplificacion RDP                 | 0.0-10.0 mm   |
| tolerancia_union        | Union de trazos cercanos           | 0.0-10.0 mm   |
| laser_on_delay_ms       | Retardo encendido laser            | 0-10000 ms    |
| laser_off_delay_ms      | Retardo apagado laser              | 0-10000 ms    |
| jump_delay_ms           | Estabilizacion de espejos          | 0-10000 ms    |
| rotacion_grados         | Rotacion libre                     | 0-360 grados  |

---

## Base de Datos (SQLite3)

Ubicacion: database/laser_system.db

- Tabla recetas: materiales y parametros de corte
- Tabla historial_produccion: cada ciclo ejecutado

Exportar historial desde la HMI: boton Terminal -> CSV

---

## Seguridad

- Las senales de voltaje se protegen con np.clip(V, -10.0, 10.0) antes del DAQ.
- La parada de emergencia (STOP) es no bloqueante: aborta el DAQ, apaga el laser
  y centra los espejos en 0V en menos de 50 ms.
- La funcion pausar_por_seguridad() congela el movimiento sin desconectar hardware.

---
Sistema UFE Laser v2.0 - Thorlabs GVS112/M + NI PXI-6229
