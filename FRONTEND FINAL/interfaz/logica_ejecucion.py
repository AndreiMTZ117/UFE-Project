# -*- coding: utf-8 -*-
"""
interfaz/logica_ejecucion.py — LÓGICA DE EJECUCIÓN: START, PAUSE/RESUME, STOP

Módulo encargado de controlar el ciclo de vida de ejecución del corte/grabado:
- Validación previa de hardware (físico o simulación virtual).
- Validación de archivos DXF y parámetros cinemáticos.
- Control de estados: Inicio, Pausa, Reanudación y Parada de emergencia.
- Hilos de telemetría, callbacks asíncronos y actualización del cronómetro LCD.
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
                "Aviso de Hardware",
                "No se detectó un microcontrolador ESP32 conectado en el puerto seleccionado.\n\n"
                "¿Deseas iniciar la ejecución en MODO SIMULACIÓN VIRTUAL?"
            )
            if not proceder:
                return

        # 2. Validación de archivo DXF
        if not self.puente.trazos_calibrados:
            messagebox.showwarning("Falta DXF", "Debes cargar un archivo DXF con trayectorias válidas antes de iniciar.")
            return

        # 3. Validación de parámetros cinemáticos
        params = self.panel_config.obtener_datos_formulario()
        if params.get("velocidad_trazado", 0) <= 0 or params.get("velocidad_viaje", 0) <= 0:
            messagebox.showwarning("Parámetros Inválidos", "Las velocidades cinemáticas deben ser mayores a cero.")
            return

        # Preparar UI para ejecución activa
        self.panel_derecho.set_modo_running()
        self.trazos_completados.clear()
        self.tiempo_inicio_ejecucion = time.time()
        self.tiempo_pausa_acumulado = 0.0
        self.tiempo_ultima_pausa = 0.0

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
            self.terminal.log("[PAUSA] Ejecución pausada. Láser apagado. Cronómetro congelado.")
        else:
            if self.tiempo_ultima_pausa > 0:
                self.tiempo_pausa_acumulado += (time.time() - self.tiempo_ultima_pausa)
                self.tiempo_ultima_pausa = 0.0
            self.terminal.log("[REANUDAR] Ejecución reanudada. Láser encendido. Cronómetro activo.")

    def _on_click_stop(self):
        """Parada de emergencia inmediata: aborta toda la ejecución, apaga el láser y resetea el reloj."""
        if not self.puente.en_ejecucion:
            return

        self.terminal.log("[STOP] Parada de emergencia ejecutada por el operador.")
        self.puente.detener_ejecucion()

    def _cb_progreso(self, trazo_idx, total_trazos, wp_idx, total_wp, x, y, trace_pct, total_pct, laser_on=True):
        """Callback invocado desde el hilo de trabajo con datos de telemetría."""
        self.after(0, self._actualizar_progreso_gui, x, y, trace_pct, total_pct, laser_on)

    def _actualizar_progreso_gui(self, x: float, y: float, trace_pct: float, total_pct: float, laser_on: bool = True):
        """Actualiza en el hilo principal de la GUI las coordenadas y gauges en tiempo real."""
        # Convertir coordenada de hardware a posición física métrica (cm) para el Canvas
        from .conexion_interfaz import HARDWARE_CONFIG
        cfg = HARDWARE_CONFIG.get(self.puente.hal_actual, HARDWARE_CONFIG["maqueta_servos"])
        cal_ancho = cfg.get("marco_ancho_cm", 28.0)
        cal_alto = cfg.get("marco_alto_cm", 25.0)
        rango_x = self.puente.x_max_limit - self.puente.x_min_limit
        rango_y = self.puente.y_max_limit - self.puente.y_min_limit
        kx = cal_alto / rango_x if rango_x > 0 else 1.0
        ky = cal_ancho / rango_y if rango_y > 0 else 1.0

        cm_x = round(self.puente.ancho_base_cm / 2.0 + (x - self.puente.centro_x) * kx, 2)
        cm_y = round(self.puente.alto_base_cm / 2.0 + (y - self.puente.centro_y) * ky, 2)

        prev_x, prev_y = self.pos_laser_actual
        self.pos_laser_actual = (cm_x, cm_y)
        if laser_on:
            self.trazos_completados.append(((prev_x, prev_y), (cm_x, cm_y)))

        self.panel_derecho.actualizar_coordenadas(cm_x, cm_y)
        self.panel_derecho.dibujar_gauges(trace_pct, total_pct)
        self._actualizar_vistas_canvases()

    def _cb_log(self, mensaje: str):
        """Callback para imprimir logs en el terminal flotante."""
        self.after(0, self.terminal.log, mensaje)

    def _cb_finalizado(self, estado: str, error_msg: str, duracion_s: float):
        """Callback al terminar la secuencia de ejecución (ejecutado desde hilo de trabajo)."""
        # Usar self.after para no bloquear la GUI con messageboxes durante la transición
        self.after(50, self._restaurar_ui_idle, estado, error_msg, duracion_s)

    def _restaurar_ui_idle(self, estado: str, error_msg: str, duracion_s: float):
        """Restaura la interfaz al estado de reposo (Idle)."""
        self.panel_derecho.set_modo_idle()
        self.panel_derecho.actualizar_timer("0:00:00")

        # Mostrar feedback de resultado con un pequeño delay para permitir
        # que la GUI se estabilice completamente antes del messagebox
        def _mostrar_resultado():
            if estado == "COMPLETADO":
                self.panel_derecho.dibujar_gauges(100.0, 100.0)
                messagebox.showinfo("Ciclo Finalizado", f"Trabajo completado exitosamente en {duracion_s} segundos.")
            elif estado == "DETENIDO":
                messagebox.showwarning("Ciclo Detenido", "El trabajo fue abortado inmediatamente por el operador.\nEl láser se apagó y el cabezal retornó al centro de reposo.")
            elif estado == "ERROR":
                messagebox.showerror("Error de Ciclo", f"Ocurrió un error durante el trazado:\n{error_msg}")

        self.after(100, _mostrar_resultado)

    def _actualizar_timer_loop(self):
        """Bucle continuo para actualizar el cronómetro LCD de ejecución."""
        if self.puente.en_ejecucion and not self.puente.esta_pausado:
            t_transcurrido = time.time() - self.tiempo_inicio_ejecucion - self.tiempo_pausa_acumulado
            if t_transcurrido < 0:
                t_transcurrido = 0.0
            mins = int(t_transcurrido // 60)
            segs = int(t_transcurrido % 60)
            horas = int(mins // 60)
            mins = int(mins % 60)
            self.panel_derecho.actualizar_timer(f"{horas}:{mins:02d}:{segs:02d}")

        self.after(200, self._actualizar_timer_loop)
