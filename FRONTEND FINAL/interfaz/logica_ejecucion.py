# -*- coding: utf-8 -*-
"""
interfaz/logica_ejecucion.py — LÓGICA DE EJECUCIÓN: START, PAUSE/RESUME, STOP

Módulo encargado de controlar el ciclo de vida de ejecución del corte/grabado:
- Validación previa de hardware Thorlabs (físico o simulación virtual).
- Validación de archivos vectoriales (DXF / G-code) y parámetros cinemáticos.
- Control de estados: Inicio, Pausa, Reanudación y Parada de emergencia.
- Hilos de telemetría, callbacks asíncronos y actualización del monitor de voltajes y cronómetro LCD.
"""

import time
from tkinter import messagebox


class LogicaEjecucionMixin:
    """Mixin que gestiona el flujo de ejecución cinemática y telemetría."""

    def _on_click_start(self):
        """Inicia el trabajo de corte/grabado tras validar requisitos."""
        # 1. Validación de hardware / Simulación
        if not self.puente.esta_conectado_fisico():
            proceder = messagebox.askyesno(
                "Hardware Notice",
                "The Thorlabs GVS112/M system is currently configured in SIMULATION MODE.\n\n"
                "Do you want to start execution in VIRTUAL SIMULATION MODE?"
            )
            if not proceder:
                return

        # 2. Validación de archivo vectorial cargado
        if not self.puente.trazos_calibrados:
            messagebox.showwarning("Missing File", "You must load a DXF or G-code file with valid toolpaths before starting.")
            return

        # 3. Validación de parámetros cinemáticos
        params = self.panel_config.obtener_datos_formulario()
        if params.get("velocidad_trazado", 0) <= 0 or params.get("velocidad_viaje", 0) <= 0:
            messagebox.showwarning("Invalid Parameters", "Kinematic speeds must be greater than zero.")
            return

        # Preparar UI para ejecución activa
        self.panel_derecho.set_modo_running()
        self.trazos_completados.clear()
        if hasattr(self.panel_general, "limpiar_progreso"):
            self.panel_general.limpiar_progreso()
        self.tiempo_inicio_ejecucion = time.time()
        self.tiempo_pausa_acumulado = 0.0
        self.tiempo_ultima_pausa = 0.0
        self._telemetria_pendiente = None
        self._render_en_cola = False

        if self.receta_activa:
            params["_receta_id"] = self.receta_activa.get("id")
            params["_receta_nombre"] = self.receta_activa.get("nombre", "Manual")

        self.puente.iniciar_ejecucion(
            params_receta=params,
            on_progress=self._cb_progreso,
            on_log=self._cb_log,
            on_finished=self._cb_finalizado
        )

    def _on_click_pause_resume(self):
        """Pausa o reanuda la ejecución en curso (congela/reanuda cronómetro)."""
        esta_pausado = self.puente.pausar_o_reanudar()
        self.panel_derecho.set_estado_pausa(esta_pausado)
        if esta_pausado:
            self.tiempo_ultima_pausa = time.time()
            self.terminal.log("[PAUSE] Execution paused. Laser OFF. Timer frozen.")
        else:
            if self.tiempo_ultima_pausa > 0:
                self.tiempo_pausa_acumulado += (time.time() - self.tiempo_ultima_pausa)
                self.tiempo_ultima_pausa = 0.0
            self.terminal.log("[RESUME] Execution resumed. Laser ON. Timer running.")

    def _on_click_stop(self):
        """Parada de emergencia inmediata: aborta toda la ejecución, apaga el láser y resetea el reloj."""
        if not self.puente.en_ejecucion:
            return

        self.terminal.log("[STOP] Emergency stop executed by operator.")
        self.puente.detener_ejecucion()

    def _cb_progreso(self, trazo_idx, total_trazos, wp_idx, total_wp, x, y, trace_pct, total_pct, laser_on=True):
        """Callback invocado desde el hilo de trabajo: desacopla telemetría y evita saturar el event loop."""
        if getattr(self, "_cerrando", False):
            return

        # Almacenar la muestra más reciente
        self._telemetria_pendiente = (x, y, trace_pct, total_pct, laser_on)

        # Si ya hay un frame programado en la GUI, no encolar otro (Frame Dropping limpio)
        if not getattr(self, "_render_en_cola", False):
            self._render_en_cola = True
            try:
                self.after(16, self._despachar_progreso_gui)
            except Exception:
                pass

    def _despachar_progreso_gui(self):
        """Consume la telemetría pendiente en el hilo de la GUI a ~60 FPS máximos sin lag."""
        self._render_en_cola = False
        if getattr(self, "_cerrando", False) or not getattr(self, "_telemetria_pendiente", None):
            return

        x, y, trace_pct, total_pct, laser_on = self._telemetria_pendiente
        self._actualizar_progreso_gui(x, y, trace_pct, total_pct, laser_on)

    def _actualizar_progreso_gui(self, x: float, y: float, trace_pct: float, total_pct: float, laser_on: bool = True):
        """Actualiza en el hilo principal de la GUI las coordenadas, voltajes live y canvases de forma ultraeficiente."""
        if getattr(self, "_cerrando", False):
            return

        from .conexion_interfaz import HARDWARE_CONFIG
        from hardware_thorlabs_galvo.config_galvo import ESCALA_VX_POR_MM, ESCALA_VY_POR_MM, OFFSET_VX, OFFSET_VY

        cfg = HARDWARE_CONFIG.get(self.puente.hal_actual, HARDWARE_CONFIG["thorlabs_galvo"])
        cal_ancho = cfg.get("marco_ancho_cm", 10.0)
        cal_alto = cfg.get("marco_alto_cm", 10.0)
        rango_x = self.puente.x_max_limit - self.puente.x_min_limit
        rango_y = self.puente.y_max_limit - self.puente.y_min_limit
        kx = cal_alto / rango_x if rango_x > 0 else 1.0
        ky = cal_ancho / rango_y if rango_y > 0 else 1.0

        cm_x = round(self.puente.ancho_base_cm / 2.0 + (x - self.puente.centro_x) * kx, 2)
        cm_y = round(self.puente.alto_base_cm / 2.0 + (y - self.puente.centro_y) * ky, 2)

        prev_x, prev_y = self.pos_laser_actual
        self.pos_laser_actual = (cm_x, cm_y)

        # Registrar segmento incremental si hubo desplazamiento efectivo (> 0.05 mm)
        dist_sq = (cm_x - prev_x)**2 + (cm_y - prev_y)**2
        if dist_sq > 0.000025:
            if laser_on:
                seg = ((prev_x, prev_y), (cm_x, cm_y))
                self.trazos_completados.append(seg)
                # O(1) rápido: solo crea la línea nueva en Canvas General sin borrar ni iterar
                self.panel_general.agregar_segmento_progreso(seg[0], seg[1])
            else:
                self.panel_general.actualizar_cursor_laser(cm_x, cm_y)
        else:
            self.panel_general.actualizar_cursor_laser(cm_x, cm_y)

        # Actualizar voltajes instantáneos en el monitor DAQ
        vx_live = ESCALA_VX_POR_MM * (x - self.puente.centro_x) + OFFSET_VX
        vy_live = ESCALA_VY_POR_MM * (y - self.puente.centro_y) + OFFSET_VY
        self.panel_derecho.actualizar_voltajes_live(vx_live, vy_live)

        self.panel_derecho.actualizar_coordenadas(cm_x, cm_y)
        self.panel_derecho.dibujar_gauges(trace_pct, total_pct)

        # Actualizar Canvas Trace Point (utiliza Viewport Culling para procesar solo ~20 segmentos)
        trazos = getattr(self.puente, "trazos_fisicos_cm", self.puente.trazos_calibrados)
        self.panel_derecho.redibujar_trace(trazos, self.trazos_completados, self.pos_laser_actual)

    def _cb_log(self, mensaje: str):
        """Callback para imprimir logs en el terminal flotante."""
        if getattr(self, "_cerrando", False):
            return
        try:
            self.after(0, self.terminal.log, mensaje)
        except Exception:
            pass

    def _cb_finalizado(self, estado: str, error_msg: str, duracion_s: float):
        """Callback al terminar la secuencia de ejecución (ejecutado desde hilo de trabajo)."""
        if getattr(self, "_cerrando", False):
            return
        try:
            self.after(50, self._restaurar_ui_idle, estado, error_msg, duracion_s)
        except Exception:
            pass

    def _restaurar_ui_idle(self, estado: str, error_msg: str, duracion_s: float):
        """Restaura la interfaz al estado de reposo (Idle)."""
        if getattr(self, "_cerrando", False):
            return

        self.panel_derecho.set_modo_idle()
        self.panel_derecho.actualizar_timer("0:00:00")

        def _mostrar_resultado():
            if getattr(self, "_cerrando", False):
                return
            if estado == "COMPLETADO":
                self.panel_derecho.dibujar_gauges(100.0, 100.0, forzar=True)
                messagebox.showinfo("Cycle Finished", f"Job completed successfully in {duracion_s} seconds.")
            elif estado == "DETENIDO":
                messagebox.showwarning("Cycle Aborted", "The job was aborted immediately by the operator.\nThe laser was turned off and the Thorlabs head returned to safe home.")
            elif estado == "ERROR":
                messagebox.showerror("Cycle Error", f"An error occurred during execution:\n{error_msg}")

        try:
            self.after(100, _mostrar_resultado)
        except Exception:
            pass

    def _actualizar_timer_loop(self):
        """Bucle continuo para actualizar el cronómetro LCD de ejecución."""
        if getattr(self, "_cerrando", False):
            return

        if self.puente.en_ejecucion and not self.puente.esta_pausado:
            t_transcurrido = time.time() - self.tiempo_inicio_ejecucion - self.tiempo_pausa_acumulado
            if t_transcurrido < 0:
                t_transcurrido = 0.0
            mins = int(t_transcurrido // 60)
            segs = int(t_transcurrido % 60)
            horas = int(mins // 60)
            mins = int(mins % 60)
            self.panel_derecho.actualizar_timer(f"{horas}:{mins:02d}:{segs:02d}")

        try:
            self._timer_loop_id = self.after(200, self._actualizar_timer_loop)
        except Exception:
            self._timer_loop_id = None
