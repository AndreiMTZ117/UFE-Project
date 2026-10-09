# -*- coding: utf-8 -*-
"""
hardware_thorlabs_galvo/controlador_thorlabs.py — Driver Unificado GVS112/M

Clase ControladorThorlabsGVS con interfaz homogénea para dos modos:

  SIMULACION
    Emula la reproducción: calcula estadísticas de tiempo real, genera logs
    detallados y simula el barrido de la matriz de voltajes sin hardware físico.

  REAL
    Importa nidaqmx, crea la tarea DAQ con cfg_samp_clk_timing, carga el
    buffer FIFO de la PXI-6229 y ejecuta el barrido síncrono por hardware
    a la frecuencia de muestreo configurada.

Métodos públicos
----------------
  trazar_matriz(M, L, fs)      Traza la matriz 2xn de voltajes + gate laser.
  trazar_trayectorias(...)     Compatibilidad DXF: convierte a matriz y llama trazar_matriz.
  centrar_espejos()            Envía (0.0 V, 0.0 V) de forma segura.
  abortar_inmediato()          Para la tarea DAQ + laser OFF + espejos en reposo.
  apagar_laser()               Solo apaga la señal TTL del laser.
  encender_laser()             Enciende la señal TTL del laser.
  cerrar()                     Limpieza final y cierre de recursos.
"""

import time
from typing import Optional

import numpy as np

from .config_galvo import (
    MODO_HARDWARE,
    DISPOSITIVO_NI, CANAL_AO_X, CANAL_AO_Y, CANAL_DO_LASER,
    FRECUENCIA_MUESTREO_HZ,
    ESCALA_VX_POR_MM, ESCALA_VY_POR_MM,
    OFFSET_VX, OFFSET_VY,
    VELOCIDAD_MARCADO_MM_S, VELOCIDAD_SALTO_MM_S,
    JUMP_DELAY_US, LASER_ON_DELAY_US, LASER_OFF_DELAY_US,
)


class ControladorThorlabsGVS:
    """
    Driver de hardware unificado para el cabezal galvanométrico Thorlabs GVS112/M.

    Parámetros
    ----------
    modo : str, opcional
        Sobreescribe MODO_HARDWARE de config_galvo.py.
        Valores válidos: 'SIMULACION', 'REAL'.
    """

    def __init__(self, modo: Optional[str] = None):
        self.modo = (modo or MODO_HARDWARE).upper()
        self._tarea_ao: Optional[object] = None   # nidaqmx.Task (AO)
        self._tarea_do: Optional[object] = None   # nidaqmx.Task (DO laser)
        self._ejecutando = False

        print(f"[Thorlabs GVS112/M] Inicializando controlador - Modo: {self.modo}")

        if self.modo == 'REAL':
            self._inicializar_daq()
        else:
            print(
                "[Thorlabs GVS112/M] MODO SIMULACION activo.\n"
                "  -> Conecte la tarjeta PXI-6229 y cambie MODO_HARDWARE='REAL' en config_galvo.py."
            )

        # Alias para compatibilidad con conexion_interfaz.py
        self.tipo_interfaz = self.modo

    # ------------------------------------------------------------------
    # Inicialización del hardware NI DAQ
    # ------------------------------------------------------------------
    def _inicializar_daq(self):
        """Crea y configura las tareas NI-DAQmx para AO y DO."""
        try:
            import nidaqmx
            import nidaqmx.constants as nconst

            # Tarea de salidas analógicas X e Y
            self._tarea_ao = nidaqmx.Task("GVS_AO")
            self._tarea_ao.ao_channels.add_ao_voltage_chan(
                f"{DISPOSITIVO_NI}/{CANAL_AO_X}", min_val=-10.0, max_val=10.0
            )
            self._tarea_ao.ao_channels.add_ao_voltage_chan(
                f"{DISPOSITIVO_NI}/{CANAL_AO_Y}", min_val=-10.0, max_val=10.0
            )

            # Tarea de salida digital para compuerta laser (TTL)
            self._tarea_do = nidaqmx.Task("GVS_DO_Laser")
            self._tarea_do.do_channels.add_do_chan(
                f"{DISPOSITIVO_NI}/{CANAL_DO_LASER}"
            )

            print(f"[Thorlabs GVS112/M] DAQ inicializado: {DISPOSITIVO_NI} | "
                  f"AO: {CANAL_AO_X},{CANAL_AO_Y} | DO: {CANAL_DO_LASER}")

        except ImportError:
            raise RuntimeError(
                "[Thorlabs GVS112/M] nidaqmx no está instalado.\n"
                "  Instale con: pip install nidaqmx\n"
                "  O cambie MODO_HARDWARE='SIMULACION' en config_galvo.py."
            )
        except Exception as exc:
            raise RuntimeError(
                f"[Thorlabs GVS112/M] Error al inicializar DAQ: {exc}\n"
                "  Verifique conexión del chasis PXIe-1073 y nombre del dispositivo en NI-MAX."
            ) from exc

    # ------------------------------------------------------------------
    # API principal: trazado de matriz de voltajes
    # ------------------------------------------------------------------
    def trazar_matriz(
        self,
        M: np.ndarray,
        L: np.ndarray,
        fs: Optional[float] = None,
    ):
        """
        Ejecuta el barrido galvanométrico a partir de la matriz de voltajes.

        Parámetros
        ----------
        M : np.ndarray (2, n)
            Fila 0 = V_x, fila 1 = V_y. Deben estar en ±10 V.
        L : np.ndarray (n,) dtype bool
            Máscara de laser activo por muestra.
        fs : float, opcional
            Frecuencia de muestreo [Hz]. Si None, usa FRECUENCIA_MUESTREO_HZ.
        """
        if M.ndim != 2 or M.shape[0] != 2:
            raise ValueError("M debe tener forma (2, n).")
        if L.shape[0] != M.shape[1]:
            raise ValueError("L debe tener la misma longitud que las columnas de M.")

        fs = fs or FRECUENCIA_MUESTREO_HZ
        n  = M.shape[1]
        dt = 1.0 / fs
        tiempo_total_s = n * dt

        print(
            f"\n[Thorlabs GVS112/M] Iniciando barrido - "
            f"n={n:,} muestras | fs={fs/1e3:.1f} kS/s | T={tiempo_total_s:.4f} s"
        )
        self._ejecutando = True

        try:
            if self.modo == 'REAL':
                self._barrido_real(M, L, fs, n)
            else:
                self._barrido_simulacion(M, L, fs, n, tiempo_total_s)
        finally:
            self._ejecutando = False

    def _barrido_real(self, M: np.ndarray, L: np.ndarray, fs: float, n: int):
        """Barrido síncrono real sobre NI PXI-6229."""
        import nidaqmx
        import nidaqmx.constants as nconst

        # Configurar temporización por hardware (clock interno del DAQ)
        self._tarea_ao.timing.cfg_samp_clk_timing(
            rate            = fs,
            sample_mode     = nconst.AcquisitionType.FINITE,
            samps_per_chan  = n,
        )

        # Escritura en buffer FIFO: canal 0 = X, canal 1 = Y
        writer = nidaqmx.stream_writers.AnalogMultiChannelWriter(
            self._tarea_ao.out_stream, auto_start=False
        )
        writer.write_many_sample(M, timeout=10.0)

        # Comenzar barrido analógico y compuerta digital sincronizada
        self._tarea_ao.start()

        # Barrido digital laser: sincronizado muestra a muestra via DO task
        # (en implementaciones avanzadas se puede usar el mismo clock con DO)
        for estado in L:
            self._tarea_do.write(bool(estado))

        # Esperar finalización del barrido AO
        self._tarea_ao.wait_until_done(timeout=n / fs + 5.0)
        self._tarea_ao.stop()

        # Asegurar laser apagado y espejos en centro
        self._tarea_do.write(False)
        self.centrar_espejos()
        print("[Thorlabs GVS112/M] Barrido real completado correctamente.")

    def _barrido_simulacion(
        self,
        M: np.ndarray,
        L: np.ndarray,
        fs: float,
        n: int,
        tiempo_total_s: float,
    ):
        """Emula el barrido con estadísticas y logs sin hardware real."""
        muestras_laser_on  = int(np.sum(L))
        muestras_laser_off = n - muestras_laser_on
        tiempo_laser_on_s  = muestras_laser_on  / fs
        tiempo_laser_off_s = muestras_laser_off / fs

        vx_rms = float(np.sqrt(np.mean(M[0] ** 2)))
        vy_rms = float(np.sqrt(np.mean(M[1] ** 2)))

        print(
            f"[Thorlabs GVS112/M] [SIM] Estadisticas del barrido:\n"
            f"  Tiempo total      : {tiempo_total_s:.4f} s  ({tiempo_total_s*1e3:.1f} ms)\n"
            f"  Laser activo      : {tiempo_laser_on_s*1e3:.1f} ms  "
            f"({100*muestras_laser_on/max(n,1):.1f} %)\n"
            f"  Laser inactivo    : {tiempo_laser_off_s*1e3:.1f} ms\n"
            f"  Vx RMS            : {vx_rms:.3f} V\n"
            f"  Vy RMS            : {vy_rms:.3f} V\n"
            f"  |Vx|_max          : {float(np.max(np.abs(M[0]))):.3f} V\n"
            f"  |Vy|_max          : {float(np.max(np.abs(M[1]))):.3f} V"
        )

        # Simular retardo realista de ejecucion (fraccionado para responder al instante a cancelaciones)
        retardo_sim = min(tiempo_total_s, 2.0)
        t_inicio_sim = time.time()
        while (time.time() - t_inicio_sim) < retardo_sim:
            if not self._ejecutando:
                break
            time.sleep(0.02)
        if self._ejecutando:
            print("[Thorlabs GVS112/M] [SIM] Barrido simulado completado.")

    # ------------------------------------------------------------------
    # API de compatibilidad con el flujo DXF existente
    # ------------------------------------------------------------------
    def trazar_trayectorias(
        self,
        trayectorias,
        velocidad_marcado: float = VELOCIDAD_MARCADO_MM_S,
        velocidad_salto: float   = VELOCIDAD_SALTO_MM_S,
    ):
        """
        Compatibilidad con principal.py y conexion_interfaz.py.
        Convierte trayectorias DXF a matriz temporal y llama a trazar_matriz().
        """
        from core.generador_matriz_temporal import GeneradorMatrizTemporal

        gen = GeneradorMatrizTemporal(
            fs              = FRECUENCIA_MUESTREO_HZ,
            escala_vx       = ESCALA_VX_POR_MM,
            escala_vy       = ESCALA_VY_POR_MM,
            offset_vx       = OFFSET_VX,
            offset_vy       = OFFSET_VY,
            jump_delay_us   = JUMP_DELAY_US,
            laser_on_delay_us  = LASER_ON_DELAY_US,
            laser_off_delay_us = LASER_OFF_DELAY_US,
            velocidad_defecto_mm_s = velocidad_marcado,
            velocidad_viaje_mm_s   = velocidad_salto,
        )

        M, L, info = gen.desde_trayectorias_dxf(
            trayectorias,
            velocidad_corte_mm_s = velocidad_marcado,
            velocidad_viaje_mm_s = velocidad_salto,
        )

        print(f"[Thorlabs GVS112/M] Tiempo estimado de ejecucion: {info['tiempo_total_s']:.4f} s")
        self.trazar_matriz(M, L, fs=FRECUENCIA_MUESTREO_HZ)

    # ------------------------------------------------------------------
    # Control puntual de espejos y laser
    # ------------------------------------------------------------------
    def centrar_espejos(self):
        """Envía (0.0 V + offset, 0.0 V + offset) para posicionar espejos en el centro óptico."""
        vx0 = float(np.clip(OFFSET_VX, -10.0, 10.0))
        vy0 = float(np.clip(OFFSET_VY, -10.0, 10.0))

        if self.modo == 'REAL' and self._tarea_ao:
            try:
                self._tarea_ao.write([vx0, vy0])
            except Exception as exc:
                print(f"[Thorlabs GVS112/M] Aviso al centrar espejos: {exc}")
        print(f"[Thorlabs GVS112/M] Espejos centrados en ({vx0:.3f} V, {vy0:.3f} V).")

    def apagar_laser(self):
        """Desactiva la senal de modulacion del laser (TTL LOW / 0 V)."""
        if self.modo == 'REAL' and self._tarea_do:
            try:
                self._tarea_do.write(False)
            except Exception as exc:
                print(f"[Thorlabs GVS112/M] Aviso al apagar laser: {exc}")
        print("[Thorlabs GVS112/M] Laser desactivado (TTL 0 V / haz apagado).")

    def encender_laser(self):
        """Activa la senal de modulacion del laser (TTL HIGH / 5 V)."""
        if self.modo == 'REAL' and self._tarea_do:
            try:
                self._tarea_do.write(True)
            except Exception as exc:
                print(f"[Thorlabs GVS112/M] Aviso al encender laser: {exc}")
        print("[Thorlabs GVS112/M] Laser activado (TTL 5 V / emision activa).")

    def abortar_inmediato(self):
        """
        Parada de emergencia:
          1. Detiene la tarea DAQ si esta activa.
          2. Apaga el laser (TTL Low).
          3. Centra los espejos en reposo (0 V, 0 V).
        """
        self._ejecutando = False
        if self.modo == 'REAL':
            for tarea in (self._tarea_ao, self._tarea_do):
                if tarea:
                    try:
                        tarea.stop()
                    except Exception:
                        pass
        self.apagar_laser()
        self.centrar_espejos()
        print("[Thorlabs GVS112/M] [!] Parada de emergencia ejecutada.")

    # ------------------------------------------------------------------
    # Cierre de recursos
    # ------------------------------------------------------------------
    def cerrar(self):
        """Apaga el laser, centra espejos y libera las tareas DAQ."""
        self.apagar_laser()
        self.centrar_espejos()
        if self.modo == 'REAL':
            for tarea in (self._tarea_ao, self._tarea_do):
                if tarea:
                    try:
                        tarea.close()
                    except Exception:
                        pass
        self._tarea_ao = None
        self._tarea_do = None
        print("[Thorlabs GVS112/M] Controlador galvo cerrado correctamente.")
