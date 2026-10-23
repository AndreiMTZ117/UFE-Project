# -*- coding: utf-8 -*-
"""execution logic lifecycle start pause resume and stop"""

import time
import threading
from collections import deque
from tkinter import messagebox
from .conexion_interfaz import HARDWARE_CONFIG
from core.config_loader import get_volts_per_mm
from interfaz.i18n import tr


class LogicaEjecucionMixin:
    """mixin managing kinematic execution workflow and telemetry"""

    def _on_click_start(self):
        """start cutting or marking job after validating requirements"""
        if getattr(self, "_ejecutando_inicio", False) or self.puente.is_running:
            return
        self._ejecutando_inicio = True
        try:
            #1. validate hardware or simulation
            if not self.puente.is_physically_connected():
                proceder = messagebox.askyesno(
                    tr("dlg_hw_notice_title"),
                    tr("dlg_hw_notice_msg")
                )
                if not proceder:
                    self._ejecutando_inicio = False
                    return

            #2. validate dxf file
            if not self.puente.trazos_calibrados:
                messagebox.showwarning(tr("dlg_missing_dxf_title"), tr("dlg_missing_dxf_msg"))
                self._ejecutando_inicio = False
                return

            #3. validate kinematic parameters
            params = self.panel_config.obtener_datos_formulario()
            if params.get("velocidad_trazado", 0) <= 0 or params.get("velocidad_viaje", 0) <= 0:
                messagebox.showwarning(tr("dlg_invalid_params_title"), tr("dlg_invalid_params_msg"))
                self._ejecutando_inicio = False
                return

            #prepare ui for active execution and clear previous markings
            self.panel_general.ocultar_frame_dxf()
            self.panel_general.limpiar_completados()
            self.panel_derecho.limpiar_progreso()
            self.trazos_completados.clear()
            self.trazos_pasadas_previas.clear()
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

            self._pass_actual = 1
            self.puente.start_execution(
                params_receta=params,
                on_progress=self._cb_progreso,
                on_log=self._cb_log,
                on_finished=self._cb_finalizado,
                on_pass_change=self._cb_cambio_pasada
            )
        finally:
            self._ejecutando_inicio = False

    def _on_click_pause_resume(self):
        """toggle pause or resume during execution"""
        is_paused = self.puente.toggle_pause()
        self.panel_derecho.set_estado_pausa(is_paused)
        if hasattr(self, "panel_config") and hasattr(self.panel_config, "set_estado_pausa"):
            self.panel_config.set_estado_pausa(is_paused)
        if is_paused:
            self.tiempo_ultima_pausa = time.time()
            self.terminal.log(tr("log_pause"))
        else:
            if self.tiempo_ultima_pausa > 0:
                self.tiempo_pausa_acumulado += (time.time() - self.tiempo_ultima_pausa)
                self.tiempo_ultima_pausa = 0.0
            self.terminal.log(tr("log_resume"))

    def _on_click_stop(self):
        """emergency stop with confirmation dialog"""
        if not self.puente.is_running:
            return

        estaba_pausado = self.puente.is_paused
        if not estaba_pausado:
            self.puente.toggle_pause()
            self.panel_derecho.set_estado_pausa(True)
            if hasattr(self, "panel_config") and hasattr(self.panel_config, "set_estado_pausa"):
                self.panel_config.set_estado_pausa(True)

        es_framing = getattr(self, "_es_framing", False)
        titulo = tr("dlg_cancel_framing_title") if es_framing else tr("dlg_cancel_exec_title")
        pregunta = tr("dlg_cancel_framing_msg") if es_framing else tr("dlg_cancel_exec_msg")

        confirma = messagebox.askyesno(titulo, pregunta)
        if not confirma:
            if not estaba_pausado:
                self.puente.toggle_pause()
                self.panel_derecho.set_estado_pausa(False)
                if hasattr(self, "panel_config") and hasattr(self.panel_config, "set_estado_pausa"):
                    self.panel_config.set_estado_pausa(False)
            return

        self._progreso_pendiente = None
        self._es_framing = False
        self.terminal.log(tr("log_stop"))
        self.puente.stop_execution()

        #clear canvas markings immediately
        self.panel_general.ocultar_frame_dxf()
        self.panel_general.limpiar_completados()
        self.panel_derecho.limpiar_progreso()
        self.trazos_completados.clear()
        self.trazos_pasadas_previas.clear()
        self._ancla_trazo = None
        self._ultimo_seg_activo = None

        #recenter mirrors to home immediately
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

        #ensure mirrors parked at home
        self.puente.center_galvos()

    def _on_click_frame(self):
        """run framing routine with laser off"""
        if self.puente.is_running:
            return

        if not self.puente.trazos_calibrados:
            messagebox.showwarning(tr("dlg_missing_geom_title"), tr("dlg_missing_geom_msg"))
            return

        #1. show dashed framing box on canvas
        self.panel_general.mostrar_frame_dxf()

        #2. configure ui in running mode
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
        self.puente.run_framing(
            params=params,
            on_progress=self._cb_progreso,
            on_log=self._cb_log,
            on_finished=self._cb_finalizado,
            asincrono=True
        )

    def _cb_cambio_pasada(self, pass_idx: int, total_passes: int):
        """worker thread pass change callback"""
        if getattr(self, '_cerrando', False):
            return
        try:
            self.after(0, self._on_nueva_pasada, pass_idx)
        except Exception:
            pass

    def _on_nueva_pasada(self, pass_idx: int):
        """transition visual rendering to new pass"""
        if pass_idx <= getattr(self, '_pass_actual', 1) and pass_idx != 1:
            return

        #1. dispatch pending telemetry
        if getattr(self, '_progreso_pendiente', None) is not None:
            self._despachar_progreso_gui()

        self._pass_actual = pass_idx

        #2. archive completed segments into previous passes
        if self.trazos_completados:
            self.trazos_pasadas_previas.extend(self.trazos_completados)

        #3. fade previous passes on canvas
        if hasattr(self.panel_general, "archivar_pasada_completada"):
            self.panel_general.archivar_pasada_completada()
        if hasattr(self.panel_derecho, "archivar_pasada_completada"):
            self.panel_derecho.archivar_pasada_completada()

        #4. clear active traces for new pass
        self.trazos_completados.clear()
        self._ancla_trazo = None
        self._ultimo_seg_activo = None

    def _cb_progreso(
        self, trazo_idx, total_trazos, wp_idx, total_wp, x, y, trace_pct, total_pct, laser_on=True,
        volt_x=None, volt_y=None
    ):
        """worker thread telemetry callback"""
        if getattr(self, '_cerrando', False):
            return
        #save latest telemetry safely
        self._progreso_pendiente = (trazo_idx, total_trazos, wp_idx, total_wp, x, y, trace_pct, total_pct, laser_on, volt_x, volt_y)
        if not getattr(self, '_progreso_programado', False):
            self._progreso_programado = True
            try:
                self.after(16, self._despachar_progreso_gui)
            except Exception:
                pass

    def _despachar_progreso_gui(self):
        """dispatch accumulated telemetry to gui thread at 60fps"""
        self._progreso_programado = False
        if getattr(self, '_cerrando', False) or self._progreso_pendiente is None:
            return
        if not self.puente.is_running:
            self._progreso_pendiente = None
            return
        datos = self._progreso_pendiente
        self._progreso_pendiente = None
        #pass trajectory identifiers coordinates percentages and voltages
        self._actualizar_progreso_gui(
            datos[0], datos[2], datos[4], datos[5], datos[6], datos[7], datos[8],
            datos[9] if len(datos) > 9 else None,
            datos[10] if len(datos) > 10 else None
        )

    #hardware feedback tracking
    def _hw_a_cm(self, x_hw: float, y_hw: float):
        """convert hardware coordinates in mm to canvas cm"""
        cfg = HARDWARE_CONFIG.get(self.puente.hal_actual, HARDWARE_CONFIG["thorlabs_galvo"])
        cal_ancho = cfg.get("marco_ancho_cm", 10.0)
        cal_alto = cfg.get("marco_alto_cm", 10.0)
        rango_x = self.puente.x_max_limit - self.puente.x_min_limit
        rango_y = self.puente.y_max_limit - self.puente.y_min_limit
        kx = cal_ancho / rango_x if rango_x > 0 else 1.0
        ky = cal_alto / rango_y if rango_y > 0 else 1.0
        return (
            self.puente.ancho_base_cm / 2.0 + (x_hw - self.puente.centro_x) * kx,
            self.puente.alto_base_cm / 2.0 + (y_hw - self.puente.centro_y) * ky,
        )

    def _iniciar_feedback_ui(self):
        """connect feedback callback and probe hardware availability"""
        self._fb_cola = deque()
        self._fb_programado = False
        self.puente.on_feedback_cb = self._cb_feedback
        if self.puente.es_simulacion:
            self._aplicar_disponibilidad_feedback(False, "simulation")
            return

        def _sonda():
            disponible, clave = self.puente.is_feedback_supported()
            try:
                self.after(0, self._aplicar_disponibilidad_feedback, disponible, clave)
            except Exception:
                pass
        threading.Thread(target=_sonda, daemon=True).start()

    def _aplicar_disponibilidad_feedback(self, disponible: bool, clave: str):
        if getattr(self, '_cerrando', False):
            return
        self.barra_superior.set_feedback_disponible(disponible, clave)
        if not disponible:
            self.puente.set_feedback(False)
            self.panel_general.set_feedback_visible(False)

    def _on_feedback_toggle(self, activo: bool):
        """toggle feedback tracking from top bar selector"""
        if self.puente.is_running:
            self.barra_superior.forzar_feedback(self.puente.feedback_habilitado)
            return
        estado = self.puente.set_feedback(activo)
        if activo and not estado:
            self.barra_superior.set_feedback_disponible(False, "simulation")
        self.panel_general.set_feedback_visible(estado)
        if not estado:
            self.panel_derecho.limpiar_feedback()
        self.terminal.log(tr("log_feedback_on") if estado else tr("log_feedback_off"))

    def _cb_feedback(self, puntos_xy_mm):
        """queue measured points and schedule gui dispatch"""
        if getattr(self, '_cerrando', False):
            return
        self._fb_cola.append(puntos_xy_mm)
        if not self._fb_programado:
            self._fb_programado = True
            try:
                self.after(33, self._despachar_feedback_gui)
            except Exception:
                self._fb_programado = False

    def _despachar_feedback_gui(self):
        """flush accumulated measured points to canvas"""
        self._fb_programado = False
        if getattr(self, '_cerrando', False):
            self._fb_cola.clear()
            return
        if not self.puente.is_running or not self.puente.feedback_habilitado:
            self._fb_cola.clear()
            return
        pts_cm = []
        try:
            while self._fb_cola:
                for x_hw, y_hw in self._fb_cola.popleft():
                    pts_cm.append(self._hw_a_cm(x_hw, y_hw))
            if pts_cm:
                self.panel_general.agregar_puntos_feedback(pts_cm)
                self.panel_derecho.agregar_puntos_feedback(pts_cm)
        except Exception:
            pass

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
        """update coordinates gauges and canvas traces in real time"""
        if getattr(self, '_cerrando', False) or not self.puente.is_running:
            return
        try:
            cfg = HARDWARE_CONFIG.get(self.puente.hal_actual, HARDWARE_CONFIG["thorlabs_galvo"])
            cal_ancho = cfg.get("marco_ancho_cm", 10.0)
            cal_alto = cfg.get("marco_alto_cm", 10.0)
            rango_x = self.puente.x_max_limit - self.puente.x_min_limit
            rango_y = self.puente.y_max_limit - self.puente.y_min_limit
            kx = cal_ancho / rango_x if rango_x > 0 else 1.0
            ky = cal_alto / rango_y if rango_y > 0 else 1.0

            #verify pass change
            pass_en_curso = getattr(self.puente, "pass_actual", 1)
            if pass_en_curso > getattr(self, "_pass_actual", 1):
                self._on_nueva_pasada(pass_en_curso)

            cm_x_real = self.puente.ancho_base_cm / 2.0 + (x - self.puente.centro_x) * kx
            cm_y_real = self.puente.alto_base_cm / 2.0 + (y - self.puente.centro_y) * ky
            cm_x = round(cm_x_real, 2)
            cm_y = round(cm_y_real, 2)

            prev_x, prev_y = self.pos_laser_actual
            self.pos_laser_actual = (cm_x_real, cm_y_real)
            pos_actual = (cm_x_real, cm_y_real)

            #update laser pointer position on canvas
            self.panel_general.actualizar_puntero(cm_x_real, cm_y_real)

            trazos_cm = getattr(self.puente, 'trazos_fisicos_cm', None)
            ancla = getattr(self, '_ancla_trazo', None)
            ultimo_seg = getattr(self, '_ultimo_seg_activo', None)

            if not laser_on:
                #transition to g0 rapid travel
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
                #active g1 marking segment
                if trazos_cm and 0 <= trazo_idx < len(trazos_cm) and 1 <= pt_idx < len(trazos_cm[trazo_idx]):
                    ruta_actual = trazos_cm[trazo_idx]
                    v_ini = ruta_actual[pt_idx - 1]

                    if ultimo_seg is None:
                        #start new contour segment
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
                            #interpolate intermediate segments to vertex
                            for s in range(prev_pt, pt_idx):
                                s_ini = ruta_actual[s - 1]
                                s_fin = ruta_actual[s]
                                origen = ancla if s == prev_pt and ancla is not None else s_ini
                                if self.panel_general.agregar_segmento_completado(origen, s_fin, forzar=True):
                                    self.trazos_completados.append((origen, s_fin))
                            ancla = v_ini
                        else:
                            #contour change: complete previous path
                            if 0 <= prev_t < len(trazos_cm):
                                ruta_ant = trazos_cm[prev_t]
                                for s in range(prev_pt, len(ruta_ant)):
                                    s_ini = ruta_ant[s - 1]
                                    s_fin = ruta_ant[s]
                                    origen = ancla if s == prev_pt and ancla is not None else s_ini
                                    if self.panel_general.agregar_segmento_completado(origen, s_fin, forzar=True):
                                        self.trazos_completados.append((origen, s_fin))
                            #ensure initial segments of new contour
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
                    #safety fallback
                    if ancla is None:
                        ancla = (prev_x, prev_y)
                    if self.panel_general.agregar_segmento_completado(ancla, pos_actual):
                        self.trazos_completados.append((ancla, pos_actual))
                        ancla = pos_actual

            self._ancla_trazo = ancla

            #relative zoom scale
            escala_general = getattr(self.panel_general, '_escala_pixel', None)
            if escala_general:
                self.panel_derecho.escala_referencia_px_cm = escala_general
            self.panel_derecho.ancla_vivo = ancla if laser_on else None

            self.panel_derecho.actualizar_coordenadas(cm_x, cm_y)

            #thorlabs galvo deflection voltages
            if volt_x is not None and volt_y is not None:
                vx = max(-10.0, min(10.0, round(volt_x, 3)))
                vy = max(-10.0, min(10.0, round(volt_y, 3)))
            else:
                scale_v = getattr(self.puente, "escala_voltaje_v_mm", None) or get_volts_per_mm()
                vx = max(-10.0, min(10.0, round((x - self.puente.centro_x) * scale_v, 3)))
                vy = max(-10.0, min(10.0, round((y - self.puente.centro_y) * scale_v, 3)))
            self.panel_derecho.actualizar_voltajes(vx, vy, laser_on)

            #circular progress gauges
            self.panel_derecho.dibujar_gauges(trace_pct, total_pct)

            #redraw trace canvas
            self.panel_derecho.redibujar_trace(
                getattr(self.puente, 'trazos_fisicos_cm', self.puente.trazos_calibrados),
                self.trazos_completados,
                self.pos_laser_actual,
                self.trazos_pasadas_previas
            )
        except Exception:
            pass

    def _cb_log(self, mensaje: str):
        """log callback for floating terminal"""
        if getattr(self, '_cerrando', False):
            return
        try:
            self.after(0, self.terminal.log, mensaje)
        except Exception:
            pass

    def _cb_finalizado(self, estado: str, error_msg: str, duracion_s: float):
        """execution finished callback from worker thread"""
        if getattr(self, '_cerrando', False):
            return
        try:
            self.after(50, self._restaurar_ui_idle, estado, error_msg, duracion_s)
        except Exception:
            pass

    def _restaurar_ui_idle(self, estado: str, error_msg: str, duracion_s: float):
        """restore ui to idle state"""
        if getattr(self, '_cerrando', False):
            return
        es_framing = getattr(self, '_es_framing', False)
        self._es_framing = False
        try:
            self._set_bloqueo_edicion_ejecucion(False)
            self.panel_derecho.set_modo_idle()
            self.panel_derecho.actualizar_timer("0:00:00")

            #return laser pointer to home center
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
                #mark all trajectories complete on successful finish
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
                        self.pos_laser_actual,
                        self.trazos_pasadas_previas
                    )
            elif estado in ("DETENIDO", "ABORTADO", "ABORTED"):
                self.panel_derecho.set_estado_sistema("STOPPED")
                self.panel_general.ocultar_frame_dxf()
                self.panel_general.limpiar_completados()
                self.panel_derecho.limpiar_progreso()
                self.trazos_completados.clear()
                self.trazos_pasadas_previas.clear()
                self._pass_actual = 1
                self._ancla_trazo = None
                self._ultimo_seg_activo = None
                self._progreso_pendiente = None
            elif estado in ("ERROR", "FAILED"):
                self.panel_derecho.set_estado_sistema("STOPPED")
                self.panel_general.ocultar_frame_dxf()
                self.panel_general.limpiar_completados()
                self.panel_derecho.limpiar_progreso()
                self.trazos_completados.clear()
                self.trazos_pasadas_previas.clear()
                self._pass_actual = 1
                self._ancla_trazo = None
                self._ultimo_seg_activo = None
                self._progreso_pendiente = None
        except Exception:
            pass

        #show cycle result dialog
        def _mostrar_resultado():
            if getattr(self, '_cerrando', False) or es_framing:
                return
            try:
                if estado in ("COMPLETADO", "COMPLETED"):
                    messagebox.showinfo(tr("dlg_cycle_finished_title"), tr("dlg_cycle_finished_msg", dur=duracion_s))
                elif estado in ("DETENIDO", "ABORTADO", "ABORTED"):
                    messagebox.showwarning(tr("dlg_cycle_aborted_title"), tr("dlg_cycle_aborted_msg"))
                elif estado in ("ERROR", "FAILED"):
                    messagebox.showerror(tr("dlg_cycle_error_title"), tr("dlg_cycle_error_msg", err=error_msg))
            except Exception:
                pass

        try:
            self.after(100, _mostrar_resultado)
        except Exception:
            pass

    def _actualizar_timer_loop(self):
        """lcd execution timer loop"""
        if getattr(self, '_cerrando', False):
            return

        if self.puente.is_running and not self.puente.is_paused:
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
        """lock or unlock configurable controls during execution"""
        if hasattr(self, 'barra_superior') and hasattr(self.barra_superior, 'set_bloqueo_ejecucion'):
            self.barra_superior.set_bloqueo_ejecucion(bloqueado)
        if hasattr(self, 'panel_config') and hasattr(self.panel_config, 'set_bloqueo_ejecucion'):
            self.panel_config.set_bloqueo_ejecucion(bloqueado)
        if hasattr(self, 'panel_general') and hasattr(self.panel_general, 'set_bloqueo_ejecucion'):
            self.panel_general.set_bloqueo_ejecucion(bloqueado)
        if hasattr(self, 'panel_derecho') and hasattr(self.panel_derecho, 'set_bloqueo_ejecucion'):
            self.panel_derecho.set_bloqueo_ejecucion(bloqueado)
