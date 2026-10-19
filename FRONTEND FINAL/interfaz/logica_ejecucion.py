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
from .conexion_interfaz import HARDWARE_CONFIG
from interfaz.i18n import tr


class LogicaEjecucionMixin:
    """Mixin que gestiona el flujo de ejecución cinemática y telemetría."""

    def _on_click_start(self):
        """Inicia el trabajo de corte/grabado tras validar requisitos."""
        if getattr(self, "_ejecutando_inicio", False) or self.puente.en_ejecucion:
            return
        self._ejecutando_inicio = True
        try:
            # 1. Validacion de hardware / Simulacion
            if not self.puente.esta_conectado_fisico():
                proceder = messagebox.askyesno(
                    "Hardware Notice",
                    "The Thorlabs GVS112/M system is not physically connected.\n\n"
                    "Do you want to start execution in VIRTUAL SIMULATION MODE?"
                )
                if not proceder:
                    self._ejecutando_inicio = False
                    return

            # 2. Validación de archivo DXF
            if not self.puente.trazos_calibrados:
                messagebox.showwarning("Missing DXF", "You must load a DXF file with valid paths before starting.")
                self._ejecutando_inicio = False
                return

            # 3. Validación de parámetros cinemáticos
            params = self.panel_config.obtener_datos_formulario()
            if params.get("velocidad_trazado", 0) <= 0 or params.get("velocidad_viaje", 0) <= 0:
                messagebox.showwarning("Invalid Parameters", "Kinematic speeds must be greater than zero.")
                self._ejecutando_inicio = False
                return

            # Preparar UI para ejecución activa: limpieza total de cualquier marcado previo
            self.panel_general.ocultar_frame_dxf()
            self.panel_general.limpiar_completados()
            self.panel_derecho.limpiar_progreso()
            self.trazos_completados.clear()
            self._ancla_trazo = None
            self._ultimo_seg_activo = None
            self._progreso_pendiente = None
            self._es_framing = False
            self.panel_derecho.set_modo_running()
            self._set_bloqueo_edicion_ejecucion(True)
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
        finally:
            self._ejecutando_inicio = False

    def _on_click_pause_resume(self):
        """Pausa o reanuda la ejecución en curso (congela/reanuda cronómetro)."""
        esta_pausado = self.puente.pausar_o_reanudar()
        self.panel_derecho.set_estado_pausa(esta_pausado)
        if hasattr(self, "panel_config") and hasattr(self.panel_config, "set_estado_pausa"):
            self.panel_config.set_estado_pausa(esta_pausado)
        if esta_pausado:
            self.tiempo_ultima_pausa = time.time()
            self.terminal.log(tr("log_pause"))
        else:
            if self.tiempo_ultima_pausa > 0:
                self.tiempo_pausa_acumulado += (time.time() - self.tiempo_ultima_pausa)
                self.tiempo_ultima_pausa = 0.0
            self.terminal.log(tr("log_resume"))

    def _on_click_stop(self):
        """Parada de emergencia inmediata: solicita confirmación y aborta la ejecución."""
        if not self.puente.en_ejecucion:
            return

        estaba_pausado = self.puente.esta_pausado
        if not estaba_pausado:
            self.puente.pausar_o_reanudar()
            self.panel_derecho.set_estado_pausa(True)
            if hasattr(self, "panel_config") and hasattr(self.panel_config, "set_estado_pausa"):
                self.panel_config.set_estado_pausa(True)

        es_framing = getattr(self, "_es_framing", False)
        titulo = "Cancel Framing" if es_framing else "Cancel Execution"
        pregunta = (
            "Are you sure you want to stop the framing process?\n\n"
            "The optical head will be safely realigned to resting center (Home)."
            if es_framing else
            "Are you sure you want to cancel the current cutting process?"
        )

        confirma = messagebox.askyesno(titulo, pregunta)
        if not confirma:
            if not estaba_pausado:
                self.puente.pausar_o_reanudar()
                self.panel_derecho.set_estado_pausa(False)
                if hasattr(self, "panel_config") and hasattr(self.panel_config, "set_estado_pausa"):
                    self.panel_config.set_estado_pausa(False)
            return

        self._progreso_pendiente = None
        self._es_framing = False
        self.terminal.log(tr("log_stop"))
        self.puente.detener_ejecucion()

        # Limpiar inmediatamente los trazos del canvas para no dejar el marcado congelado
        self.panel_general.ocultar_frame_dxf()
        self.panel_general.limpiar_completados()
        self.panel_derecho.limpiar_progreso()
        self.trazos_completados.clear()
        self._ancla_trazo = None
        self._ultimo_seg_activo = None

        # Re-alinear al centro (Home) inmediatamente
        cx = self.puente.centro_cm_x
        cy = self.puente.centro_cm_y
        self.pos_laser_actual = (cx, cy)
        self.panel_general.actualizar_puntero(cx, cy)
        self.panel_derecho.actualizar_coordenadas(cx, cy)
        self.panel_derecho.redibujar_trace(pos_laser=(cx, cy))
        self.panel_derecho.set_modo_idle()
        if hasattr(self, "panel_config") and hasattr(self.panel_config, "set_modo_framing"):
            self.panel_config.set_modo_framing(False)
        self._set_bloqueo_edicion_ejecucion(False)

        # Asegurar espejos en reposo Home
        self.puente.centrar_galvos()

    def _on_click_frame(self):
        """Ejecuta la rutina de enmarcado (Framing) con el laser estrictamente apagado."""
        if self.puente.en_ejecucion:
            return

        if not self.puente.trazos_calibrados:
            messagebox.showwarning("Missing Geometry", "You must load a DXF file before running framing.")
            return

        # 1. Mostrar marco naranja punteado en el canvas vectorial (1:1 isometric)
        self.panel_general.mostrar_frame_dxf()

        # 2. Configurar UI en modo ejecución / framing (activar botones PAUSE y STOP)
        self._es_framing = True
        self.panel_derecho.set_modo_running()
        self.panel_derecho.set_estado_sistema("FRAMING")
        if hasattr(self, "panel_config") and hasattr(self.panel_config, "set_modo_framing"):
            self.panel_config.set_modo_framing(True)
        self._set_bloqueo_edicion_ejecucion(True)
        self.tiempo_inicio_ejecucion = time.time()
        self.tiempo_pausa_acumulado = 0.0
        self.tiempo_ultima_pausa = 0.0
        self._timer_after_id = self.after(200, self._actualizar_timer_loop)

        params = self.panel_config.obtener_datos_formulario()
        self.terminal.log(tr("log_framing_start"))
        self.puente.ejecutar_enmarcado(
            params=params,
            on_progress=self._cb_progreso,
            on_log=self._cb_log,
            on_finished=self._cb_finalizado,
            asincrono=True
        )

    def _cb_progreso(
        self, trazo_idx, total_trazos, wp_idx, total_wp, x, y, trace_pct, total_pct, laser_on=True,
        volt_x=None, volt_y=None
    ):
        """Callback invocado desde el hilo de trabajo con datos de telemetría."""
        if getattr(self, '_cerrando', False):
            return
        # Guardar la telemetria mas reciente de forma segura
        self._progreso_pendiente = (trazo_idx, total_trazos, wp_idx, total_wp, x, y, trace_pct, total_pct, laser_on, volt_x, volt_y)
        if not getattr(self, '_progreso_programado', False):
            self._progreso_programado = True
            try:
                self.after(16, self._despachar_progreso_gui)
            except Exception:
                pass

    def _despachar_progreso_gui(self):
        """Despacha la telemetria acumulada al hilo GUI a ~60fps sin saturar la cola."""
        self._progreso_programado = False
        if getattr(self, '_cerrando', False) or self._progreso_pendiente is None:
            return
        if not self.puente.en_ejecucion:
            self._progreso_pendiente = None
            return
        datos = self._progreso_pendiente
        self._progreso_pendiente = None
        # Pasar identificadores de trayectoria y segmento junto a coordenadas, porcentajes y voltajes instantaneos
        self._actualizar_progreso_gui(
            datos[0], datos[2], datos[4], datos[5], datos[6], datos[7], datos[8],
            datos[9] if len(datos) > 9 else None,
            datos[10] if len(datos) > 10 else None
        )

    def _actualizar_progreso_gui(
        self,
        trazo_idx: int,
        pt_idx: int,
        x: float,
        y: float,
        trace_pct: float,
        total_pct: float,
        laser_on: bool = True,
        volt_x: float = None,
        volt_y: float = None
    ):
        """Actualiza en el hilo principal de la GUI las coordenadas y gauges en tiempo real."""
        if getattr(self, '_cerrando', False) or not self.puente.en_ejecucion:
            return
        try:
            cfg = HARDWARE_CONFIG.get(self.puente.hal_actual, HARDWARE_CONFIG["thorlabs_galvo"])
            cal_ancho = cfg.get("marco_ancho_cm", 10.0)
            cal_alto = cfg.get("marco_alto_cm", 10.0)
            rango_x = self.puente.x_max_limit - self.puente.x_min_limit
            rango_y = self.puente.y_max_limit - self.puente.y_min_limit
            kx = cal_ancho / rango_x if rango_x > 0 else 1.0
            ky = cal_alto / rango_y if rango_y > 0 else 1.0

            cm_x_real = self.puente.ancho_base_cm / 2.0 + (x - self.puente.centro_x) * kx
            cm_y_real = self.puente.alto_base_cm / 2.0 + (y - self.puente.centro_y) * ky
            cm_x = round(cm_x_real, 2)
            cm_y = round(cm_y_real, 2)

            prev_x, prev_y = self.pos_laser_actual
            self.pos_laser_actual = (cm_x_real, cm_y_real)
            pos_actual = (cm_x_real, cm_y_real)

            # Actualizar el puntero visual del láser (puntito verde) en el canvas 1:1
            self.panel_general.actualizar_puntero(cm_x_real, cm_y_real)

            trazos_cm = getattr(self.puente, 'trazos_fisicos_cm', None)
            ancla = getattr(self, '_ancla_trazo', None)
            ultimo_seg = getattr(self, '_ultimo_seg_activo', None)

            if not laser_on:
                # Transición a movimiento en vacío (G0 viaje o fin de corte):
                # Cerrar cualquier segmento previo completando hasta el final de la figura
                if ultimo_seg is not None and trazos_cm:
                    prev_t, prev_pt = ultimo_seg
                    if 0 <= prev_t < len(trazos_cm):
                        ruta_ant = trazos_cm[prev_t]
                        for s in range(prev_pt, len(ruta_ant)):
                            s_ini = ruta_ant[s - 1]
                            s_fin = ruta_ant[s]
                            origen = ancla if s == prev_pt and ancla is not None else s_ini
                            if self.panel_general.agregar_segmento_completado(origen, s_fin, forzar=True):
                                self.trazos_completados.append((origen, s_fin))
                elif ancla is not None:
                    cierre = (prev_x, prev_y)
                    if self.panel_general.agregar_segmento_completado(ancla, cierre, forzar=True):
                        self.trazos_completados.append((ancla, cierre))
                ancla = None
                self._ultimo_seg_activo = None
            else:
                # Segmento de marcado activo (G1 corte):
                # Conectar estrictamente sobre los vectores CAD y forzar vértices al cambiar de segmento
                if trazos_cm and 0 <= trazo_idx < len(trazos_cm) and 1 <= pt_idx < len(trazos_cm[trazo_idx]):
                    ruta_actual = trazos_cm[trazo_idx]
                    v_ini = ruta_actual[pt_idx - 1]
                    v_fin = ruta_actual[pt_idx]

                    if ultimo_seg is None:
                        # Comienza un nuevo tramo de corte: asegurar segmentos previos desde el inicio
                        for s in range(1, pt_idx):
                            s_ini = ruta_actual[s - 1]
                            s_fin = ruta_actual[s]
                            if self.panel_general.agregar_segmento_completado(s_ini, s_fin, forzar=True):
                                self.trazos_completados.append((s_ini, s_fin))
                        ancla = v_ini
                        self._ultimo_seg_activo = (trazo_idx, pt_idx)
                    elif ultimo_seg != (trazo_idx, pt_idx):
                        prev_t, prev_pt = ultimo_seg
                        if prev_t == trazo_idx and prev_pt < pt_idx:
                            # Completar con fidelidad geométrica los segmentos intermedios hasta el vértice
                            for s in range(prev_pt, pt_idx):
                                s_ini = ruta_actual[s - 1]
                                s_fin = ruta_actual[s]
                                origen = ancla if s == prev_pt and ancla is not None else s_ini
                                if self.panel_general.agregar_segmento_completado(origen, s_fin, forzar=True):
                                    self.trazos_completados.append((origen, s_fin))
                            ancla = v_ini
                        else:
                            # Cambio de trayectoria / ruta: completar la ruta anterior hasta su último vértice
                            if 0 <= prev_t < len(trazos_cm):
                                ruta_ant = trazos_cm[prev_t]
                                for s in range(prev_pt, len(ruta_ant)):
                                    s_ini = ruta_ant[s - 1]
                                    s_fin = ruta_ant[s]
                                    origen = ancla if s == prev_pt and ancla is not None else s_ini
                                    if self.panel_general.agregar_segmento_completado(origen, s_fin, forzar=True):
                                        self.trazos_completados.append((origen, s_fin))
                            # Y asegurar segmentos iniciales de la nueva ruta hasta pt_idx
                            for s in range(1, pt_idx):
                                s_ini = ruta_actual[s - 1]
                                s_fin = ruta_actual[s]
                                if self.panel_general.agregar_segmento_completado(s_ini, s_fin, forzar=True):
                                    self.trazos_completados.append((s_ini, s_fin))
                            ancla = v_ini
                        self._ultimo_seg_activo = (trazo_idx, pt_idx)

                    if ancla is None:
                        ancla = v_ini

                    if self.panel_general.agregar_segmento_completado(ancla, pos_actual):
                        self.trazos_completados.append((ancla, pos_actual))
                        ancla = pos_actual
                else:
                    # Fallback de seguridad si trazos_fisicos_cm no está disponible
                    if ancla is None:
                        ancla = (prev_x, prev_y)
                    if self.panel_general.agregar_segmento_completado(ancla, pos_actual):
                        self.trazos_completados.append((ancla, pos_actual))
                        ancla = pos_actual

            self._ancla_trazo = ancla

            # Zoom relativo: el seguimiento usa la escala del canvas general como base
            escala_general = getattr(self.panel_general, '_escala_pixel', None)
            if escala_general:
                self.panel_derecho.escala_referencia_px_cm = escala_general
            self.panel_derecho.ancla_vivo = ancla if laser_on else None

            self.panel_derecho.actualizar_coordenadas(cm_x, cm_y)

            # Thorlabs GVS112/M mirror deflection voltages (-10V to +10V)
            if volt_x is not None and volt_y is not None:
                vx = max(-10.0, min(10.0, round(volt_x, 3)))
                vy = max(-10.0, min(10.0, round(volt_y, 3)))
            else:
                scale_v = getattr(self.puente, "escala_voltaje_v_mm", 0.200)
                vx = max(-10.0, min(10.0, round((x - self.puente.centro_x) * scale_v, 3)))
                vy = max(-10.0, min(10.0, round((y - self.puente.centro_y) * scale_v, 3)))
            self.panel_derecho.actualizar_voltajes(vx, vy, laser_on)

            # Medidores circulares: porcentaje de pieza actual (Trazo) y total acumulado
            self.panel_derecho.dibujar_gauges(trace_pct, total_pct)

            # Redibujar canvas trace (zoom 4x) con descarte de lineas fuera del visor
            self.panel_derecho.redibujar_trace(
                getattr(self.puente, 'trazos_fisicos_cm', self.puente.trazos_calibrados),
                self.trazos_completados,
                self.pos_laser_actual
            )
        except Exception:
            pass

    def _cb_log(self, mensaje: str):
        """Callback para imprimir logs en el terminal flotante."""
        if getattr(self, '_cerrando', False):
            return
        try:
            self.after(0, self.terminal.log, mensaje)
        except Exception:
            pass

    def _cb_finalizado(self, estado: str, error_msg: str, duracion_s: float):
        """Callback al terminar la secuencia de ejecución (ejecutado desde hilo de trabajo)."""
        if getattr(self, '_cerrando', False):
            return
        try:
            self.after(50, self._restaurar_ui_idle, estado, error_msg, duracion_s)
        except Exception:
            pass

    def _restaurar_ui_idle(self, estado: str, error_msg: str, duracion_s: float):
        """Restaura la interfaz al estado de reposo (Idle)."""
        if getattr(self, '_cerrando', False):
            return
        es_framing = getattr(self, '_es_framing', False)
        self._es_framing = False
        try:
            self._set_bloqueo_edicion_ejecucion(False)
            self.panel_derecho.set_modo_idle()
            self.panel_derecho.actualizar_timer("0:00:00")

            # Retornar el puntero visual del láser al centro (Home) en ambos canvases
            cx = self.puente.centro_cm_x
            cy = self.puente.centro_cm_y
            self.pos_laser_actual = (cx, cy)
            self.panel_general.actualizar_puntero(cx, cy)
            self.panel_derecho.actualizar_coordenadas(cx, cy)
            self.panel_derecho.redibujar_trace(pos_laser=(cx, cy))

            if es_framing:
                self.panel_derecho.set_modo_idle()
                if hasattr(self, "panel_config") and hasattr(self.panel_config, "set_modo_framing"):
                    self.panel_config.set_modo_framing(False)
                self.panel_derecho.dibujar_gauges(0.0, 0.0)
                if estado in ("COMPLETADO", "COMPLETED"):
                    self.panel_derecho.set_estado_sistema("READY")
                    self.terminal.log(tr("log_framing_done"))
                elif estado in ("DETENIDO", "ABORTADO", "ABORTED"):
                    self.panel_derecho.set_estado_sistema("STOPPED")
                    self.panel_general.ocultar_frame_dxf()
                    self.terminal.log(tr("log_framing_aborted"))
                elif estado in ("ERROR", "FAILED"):
                    self.panel_derecho.set_estado_sistema("STOPPED")
                    self.panel_general.ocultar_frame_dxf()
                    self.terminal.log(tr("log_framing_err", err=error_msg))
                return

            if estado in ("COMPLETADO", "COMPLETED"):
                self.panel_derecho.dibujar_gauges(100.0, 100.0)
                self.panel_derecho.set_estado_sistema("COMPLETED")
                # Al completar el trabajo con éxito, asegurar que todos los trazos se muestren 100% completados
                trazos_cm = getattr(self.puente, 'trazos_fisicos_cm', None)
                if trazos_cm:
                    for ruta in trazos_cm:
                        for s in range(1, len(ruta)):
                            p1, p2 = ruta[s - 1], ruta[s]
                            self.panel_general.agregar_segmento_completado(p1, p2, forzar=True)
                            self.trazos_completados.append((p1, p2))
                    self.panel_derecho.redibujar_trace(
                        trazos_cm,
                        self.trazos_completados,
                        self.pos_laser_actual
                    )
            elif estado in ("DETENIDO", "ABORTADO", "ABORTED"):
                self.panel_derecho.set_estado_sistema("STOPPED")
                self.panel_general.ocultar_frame_dxf()
                self.panel_general.limpiar_completados()
                self.panel_derecho.limpiar_progreso()
                self.trazos_completados.clear()
                self._ancla_trazo = None
                self._ultimo_seg_activo = None
                self._progreso_pendiente = None
            elif estado in ("ERROR", "FAILED"):
                self.panel_derecho.set_estado_sistema("STOPPED")
                self.panel_general.ocultar_frame_dxf()
                self.panel_general.limpiar_completados()
                self.panel_derecho.limpiar_progreso()
                self.trazos_completados.clear()
                self._ancla_trazo = None
                self._ultimo_seg_activo = None
                self._progreso_pendiente = None
        except Exception:
            pass

        # Mostrar feedback de resultado con protección contra app cerrando (solo para corte, no framing)
        def _mostrar_resultado():
            if getattr(self, '_cerrando', False) or es_framing:
                return
            try:
                if estado in ("COMPLETADO", "COMPLETED"):
                    messagebox.showinfo("Cycle Finished", f"Job successfully completed in {duracion_s} seconds.")
                elif estado in ("DETENIDO", "ABORTADO", "ABORTED"):
                    messagebox.showwarning("Cycle Aborted", "The job was immediately aborted by the operator.\nThe laser has been turned off and the head returned to resting center.")
                elif estado in ("ERROR", "FAILED"):
                    messagebox.showerror("Cycle Error", f"An error occurred during tracing:\n{error_msg}")
            except Exception:
                pass

        try:
            self.after(100, _mostrar_resultado)
        except Exception:
            pass

    def _actualizar_timer_loop(self):
        """Bucle continuo para actualizar el cronometro LCD de ejecucion."""
        if getattr(self, '_cerrando', False):
            return

        if self.puente.en_ejecucion and not self.puente.esta_pausado:
            t_transcurrido = time.time() - self.tiempo_inicio_ejecucion - self.tiempo_pausa_acumulado
            if t_transcurrido < 0:
                t_transcurrido = 0.0
            mins = int(t_transcurrido // 60)
            segs = int(t_transcurrido % 60)
            horas = int(mins // 60)
            mins = int(mins % 60)
            try:
                self.panel_derecho.actualizar_timer(f"{horas}:{mins:02d}:{segs:02d}")
            except Exception:
                return

        try:
            if not getattr(self, '_cerrando', False):
                self._timer_after_id = self.after(200, self._actualizar_timer_loop)
        except Exception:
            pass

    def _set_bloqueo_edicion_ejecucion(self, bloqueado: bool):
        """Bloquea o habilita todos los controles configurables mientras el trabajo está en ejecución."""
        if hasattr(self, 'barra_superior') and hasattr(self.barra_superior, 'set_bloqueo_ejecucion'):
            self.barra_superior.set_bloqueo_ejecucion(bloqueado)
        if hasattr(self, 'panel_config') and hasattr(self.panel_config, 'set_bloqueo_ejecucion'):
            self.panel_config.set_bloqueo_ejecucion(bloqueado)
        if hasattr(self, 'panel_general') and hasattr(self.panel_general, 'set_bloqueo_ejecucion'):
            self.panel_general.set_bloqueo_ejecucion(bloqueado)
        if hasattr(self, 'panel_derecho') and hasattr(self.panel_derecho, 'set_bloqueo_ejecucion'):
            self.panel_derecho.set_bloqueo_ejecucion(bloqueado)
