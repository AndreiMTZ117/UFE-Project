# -*- coding: utf-8 -*-
"""central internationalization manager for english and czech"""

from typing import Callable, Dict, List, Any

#available languages
IDIOMA_EN = "EN"
IDIOMA_CS = "CS"
IDIOMAS_DISPONIBLES = [IDIOMA_EN, IDIOMA_CS]

#global state
_idioma_activo: str = IDIOMA_EN
_observadores: List[Callable[[], None]] = []

#translation dictionary
_TEXTOS: Dict[str, Dict[str, str]] = {
    #top bar
    "ports_scanning": {
        "EN": "Scanning ports...",
        "CS": "Skenování portů...",
    },
    "ports_scan": {
        "EN": "Scan...",
        "CS": "Skenovat...",
    },
    "dxf_loading": {
        "EN": "Loading...",
        "CS": "Načítání...",
    },
    "dxf_load_file": {
        "EN": "[ Load File... ]",
        "CS": "[ Načíst soubor... ]",
    },
    "btn_terminal": {
        "EN": "Terminal",
        "CS": "Terminál",
    },
    "tooltip_com": {
        "EN": "Communication interface with Thorlabs GVS112/M hardware.\nGreen LED = physical DAQ hardware active; Red LED = virtual simulation mode.\n'Scan...' refreshes hardware ports.",
        "CS": "Komunikační rozhraní s hardwarem Thorlabs GVS112/M.\nZelená LED = aktivní fyzický hardware DAQ; Červená LED = režim virtuální simulace.\n'Skenovat...' obnoví hardwarové porty.",
    },
    "tooltip_dxf": {
        "EN": "Active DXF file to trace. Choose from cached list or select '[ Load File... ]' to open from explorer.",
        "CS": "Aktivní DXF soubor k vykreslení. Vyberte ze seznamu nebo zvolte '[ Načíst soubor... ]' k otevření z průzkumníka.",
    },
    "tooltip_terminal": {
        "EN": "Toggle floating diagnostic terminal and event log view.",
        "CS": "Zobrazit/skrýt plovoucí diagnostický terminál a záznam událostí.",
    },
    "tooltip_lang": {
        "EN": "Interface language selector (English / Čeština).",
        "CS": "Výběr jazyka uživatelského rozhraní (English / Čeština).",
    },
    "feedback_toggle": {
        "EN": "HW Feedback",
        "CS": "HW zpětná vazba",
    },
    "tooltip_feedback_ok": {
        "EN": "Enable Hardware Feedback Tracking: reads the real mirror position from AI channels and draws it in magenta.",
        "CS": "Zapnout sledování zpětné vazby hardwaru: čte skutečnou polohu zrcadel z AI kanálů a vykresluje ji purpurově.",
    },
    "tooltip_feedback_simulation": {
        "EN": "Hardware Feedback Tracking is unavailable in simulation mode.",
        "CS": "Sledování zpětné vazby hardwaru není v simulačním režimu dostupné.",
    },
    "tooltip_feedback_no_driver": {
        "EN": "Hardware Feedback Tracking is unavailable: NI-DAQmx driver not found.",
        "CS": "Sledování zpětné vazby hardwaru není dostupné: ovladač NI-DAQmx nebyl nalezen.",
    },
    "tooltip_feedback_no_device": {
        "EN": "Hardware Feedback Tracking is unavailable: AI channels (ai0/ai1) could not be opened.",
        "CS": "Sledování zpětné vazby hardwaru není dostupné: AI kanály (ai0/ai1) nelze otevřít.",
    },
    "tooltip_feedback_checking": {
        "EN": "Checking Hardware Feedback availability...",
        "CS": "Kontroluje se dostupnost zpětné vazby hardwaru...",
    },
    "legend_measured": {
        "EN": "Measured (Feedback)",
        "CS": "Naměřeno (zpětná vazba)",
    },
    "legend_measured_desc": {
        "EN": "Real mirror position from AI monitor",
        "CS": "Skutečná poloha zrcadel z AI monitoru",
    },
    "log_feedback_on": {
        "EN": "[Feedback] Hardware Feedback Tracking enabled.",
        "CS": "[Feedback] Sledování zpětné vazby hardwaru zapnuto.",
    },
    "log_feedback_off": {
        "EN": "[Feedback] Hardware Feedback Tracking disabled.",
        "CS": "[Feedback] Sledování zpětné vazby hardwaru vypnuto.",
    },

    #left panel configuration and recipes
    "recipe_parameters": {
        "EN": "RECIPE & PARAMETERS",
        "CS": "RECEPTURA A PARAMETRY",
    },
    "btn_new_recipe": {
        "EN": "+ NEW",
        "CS": "+ NOVÁ",
    },
    "btn_save_recipe": {
        "EN": "💾 SAVE",
        "CS": "💾 ULOŽIT",
    },
    "btn_del_recipe": {
        "EN": "🗑",
        "CS": "🗑",
    },
    "tooltip_recipe": {
        "EN": "Active recipe: saved preset of cutting parameters (speeds, delays, tolerances).\nSelecting loads its values into the form.",
        "CS": "Aktivní receptura: uložená předvolba parametrů řezání (rychlosti, zpoždění, tolerance).\nVýběrem se hodnoty načtou do formuláře.",
    },
    "tooltip_btn_new": {
        "EN": "Create a new recipe preset in SQLite3 database.",
        "CS": "Vytvořit novou předvolbu receptury v databázi SQLite3.",
    },
    "tooltip_btn_save": {
        "EN": "Save current parameters to active recipe in database.",
        "CS": "Uložit aktuální parametry do aktivní receptury v databázi.",
    },
    "tooltip_btn_del": {
        "EN": "Delete active recipe from database.",
        "CS": "Smazat aktivní recepturu z databáze.",
    },

    #parameter dividers and labels
    "sec_kinematics": {
        "EN": "KINEMATICS",
        "CS": "KINEMATIKA",
    },
    "param_velocidad_trazado": {
        "EN": "Mark Speed",
        "CS": "Rychlost značení",
    },
    "param_velocidad_viaje": {
        "EN": "Travel Speed",
        "CS": "Rychlost přejezdu",
    },
    "param_duracion_min_segmento_ms": {
        "EN": "Min Mark Dwell",
        "CS": "Min. prodleva značení",
    },
    "param_duracion_min_viaje_ms": {
        "EN": "Min Jump Dwell",
        "CS": "Min. prodleva skoku",
    },

    "sec_optical_delays": {
        "EN": "OPTICAL DELAYS",
        "CS": "OPTICKÁ ZPOŽDĚNÍ",
    },
    "param_laser_on_delay_ms": {
        "EN": "Laser ON Delay",
        "CS": "Zpoždění sepnutí laseru",
    },
    "param_laser_off_delay_ms": {
        "EN": "Laser OFF Delay",
        "CS": "Zpoždění vypnutí laseru",
    },
    "param_mark_delay_ms": {
        "EN": "Mark Settling Delay",
        "CS": "Zpoždění po značení",
    },
    "param_jump_delay_ms": {
        "EN": "Jump Settling Delay",
        "CS": "Zpoždění po skoku",
    },

    "sec_process_passes": {
        "EN": "PROCESS & PASSES",
        "CS": "PROCES A PRŮCHODY",
    },
    "param_modo_proceso": {
        "EN": "Process Mode",
        "CS": "Režim procesu",
    },
    "mode_cutting": {
        "EN": "Cutting",
        "CS": "Řezání",
    },
    "mode_marking": {
        "EN": "Marking",
        "CS": "Značení",
    },
    "mode_welding": {
        "EN": "Welding",
        "CS": "Svařování",
    },
    "param_num_pasadas": {
        "EN": "Passes",
        "CS": "Počet průchodů",
    },
    "param_cooling_delay_s": {
        "EN": "Cooling Delay",
        "CS": "Prodleva chlazení",
    },

    "sec_cad_geometry": {
        "EN": "CAD GEOMETRY",
        "CS": "GEOMETRIE CAD",
    },
    "param_tolerancia_rdp": {
        "EN": "RDP Tolerance",
        "CS": "Tolerance RDP",
    },
    "param_tolerancia_union": {
        "EN": "Join Tolerance",
        "CS": "Tolerance spojení",
    },

    "sec_spatial_axes": {
        "EN": "SPATIAL & AXES",
        "CS": "PROSTOR A OSY",
    },
    "param_escala_dibujo": {
        "EN": "Scale",
        "CS": "Měřítko",
    },
    "param_rotacion_grados": {
        "EN": "Rotation",
        "CS": "Rotace",
    },
    "param_invert_x": {
        "EN": "Invert X",
        "CS": "Invertovat X",
    },
    "param_invert_y": {
        "EN": "Invert Y",
        "CS": "Invertovat Y",
    },
    "param_swap_xy": {
        "EN": "Swap XY",
        "CS": "Prohodit XY",
    },

    "sec_alignment": {
        "EN": "ALIGNMENT",
        "CS": "ZAROVNÁNÍ",
    },
    "btn_trace_box": {
        "EN": "TRACE BOX (FRAME)",
        "CS": "VYKRESLIT RÁM (RAMEC)",
    },
    "btn_framing_active": {
        "EN": "FRAMING ACTIVE (G0)",
        "CS": "OHRANIČENÍ AKTIVNÍ (G0)",
    },
    "btn_framing_stop": {
        "EN": "STOP",
        "CS": "ZASTAVIT",
    },
    "tooltip_btn_frame": {
        "EN": "Execute rapid perimeter check (laser gate strictly OFF) to verify workpiece alignment.",
        "CS": "Provést rychlou kontrolu obvodu rámečku (laser přísně vypnut) k ověření vyrovnání obrobku.",
    },

    #technical parameter tooltips
    "help_velocidad_trazado": {
        "EN": "Beam speed while laser is ON (marking).\nLower speed = higher energy per mm (deeper mark) and slower trajectory.",
        "CS": "Rychlost paprsku při zapnutém laseru (značení).\nNižší rychlost = vyšší hustota energie na mm (hlubší stopa) a pomalejší pohyb.",
    },
    "help_velocidad_viaje": {
        "EN": "Rapid travel speed between paths with laser OFF.\nHigher value reduces cycle time but increases mirror stress.",
        "CS": "Rychlost rychlopřejezdu mezi drahami s vypnutým laserem.\nVyšší hodnota zkracuje dobu cyklu, ale zvyšuje namáhání zrcadel.",
    },
    "help_duracion_min_segmento_ms": {
        "EN": "Minimum duration for each marking segment.\nVery short segments are extended to this duration to avoid excessive mirror acceleration.",
        "CS": "Minimální doba trvání každého segmentu značení.\nVelmi krátké segmenty se prodlouží na tuto hodnotu, aby se zamezilo přetížení zrcadel.",
    },
    "help_duracion_min_viaje_ms": {
        "EN": "Minimum duration for rapid travels with laser OFF.\nPrevents abrupt galvanometer jumps between nearby paths.",
        "CS": "Minimální doba trvání rychlých přejezdů s vypnutým laserem.\nZabraňuje trhavým skokům galvanometru mezi blízkými drahami.",
    },
    "help_laser_on_delay_ms": {
        "EN": "Turn-on delay: elapsed time between mirror motion onset and optical emission.\nCompensates for galvanometer inertia.",
        "CS": "Zpoždění sepnutí: doba mezi začátkem pohybu zrcadel a optickou emisí.\nKompenzuje setrvačnost galvanometru.",
    },
    "help_laser_off_delay_ms": {
        "EN": "Turn-off delay: duration laser remains active after completing a path,\npreventing unetched line ends.",
        "CS": "Zpoždění vypnutí: doba, po kterou zůstává laser aktivní po dokončení dráhy,\nzabraňuje nedořezání konců čar.",
    },
    "help_mark_delay_ms": {
        "EN": "Braking dwell time at the end of each marked path\nto allow mirrors to settle before moving.",
        "CS": "Doba ustálení na konci každé značené dráhy,\naby se zrcadla ustálila před dalším pohybem.",
    },
    "help_jump_delay_ms": {
        "EN": "Settling dwell after a rapid jump (laser off)\nbefore marking the next path.",
        "CS": "Doba ustálení po rychlém skoku (vypnutý laser)\npřed zahájením značení další dráhy.",
    },
    "help_modo_proceso": {
        "EN": "Process operation mode: Cutting, Welding, or Marking.\nStored as a first-class attribute within each recipe preset.",
        "CS": "Provozní režim procesu: Řezání, Svařování nebo Značení.\nUloženo jako primární atribut v každé předvolbě receptury.",
    },
    "help_num_pasadas": {
        "EN": "Number of repeated execution passes over the vector paths.\nUse multiple passes for cutting through thicker sheets.",
        "CS": "Počet opakovaných průchodů přes vektorové dráhy.\nVyužijte více průchodů pro prořezání silnějších materiálů.",
    },
    "help_cooling_delay_s": {
        "EN": "Inter-pass thermal cooling dwell in seconds with LASER OFF.\nAllows heat dissipation between consecutive cutting passes.",
        "CS": "Tepelné chlazení mezi průchody v sekundách s VYPNUTÝM LASEREM.\nUmožňuje odvod tepla mezi po sobě jdoucími řeznými průchody.",
    },
    "help_tolerancia_rdp": {
        "EN": "Ramer-Douglas-Peucker geometric simplification tolerance in mm.\nSet to 0.0 to disable simplification and preserve fine contours without deformation.\nHigher values reduce node count for smoother mirror motion.",
        "CS": "Geometrická tolerance zjednodušení Ramer-Douglas-Peucker v mm.\nNastavte 0.0 pro vypnutí zjednodušení a zachování jemných obrysů.\nVyšší hodnoty snižují počet uzlů pro plynulejší pohyb zrcadel.",
    },
    "help_tolerancia_union": {
        "EN": "Maximum distance between path endpoints to merge them\ninto a single continuous contour. Eliminates unnecessary jumps.",
        "CS": "Maximální vzdálenost mezi koncovými body drah pro jejich spojení\ndo jediné souvislé kontury. Eliminuje zbytečné skoky.",
    },
    "help_escala_dibujo": {
        "EN": "Fraction of available area occupied by drawing (1.0 = 100%).\nReduce to leave clearance around workpiece.",
        "CS": "Podíl dostupné plochy obsazené kresbou (1.0 = 100%).\nSnižte pro ponechání volného prostoru kolem obrobku.",
    },
    "help_rotacion_grados": {
        "EN": "Drawing rotation in degrees (0° to 360°).\nRotates all trajectories around the geometric center.",
        "CS": "Otočení kresby ve stupních (0° až 360°).\nOtočí všechny trajektorie kolem geometrického středu.",
    },
    "help_invert_x": {
        "EN": "Invert X: reflects horizontal coordinates across the center of workspace.",
        "CS": "Invertovat X: zrcadlí vodorovné souřadnice přes střed pracovní plochy.",
    },
    "help_invert_y": {
        "EN": "Invert Y: reflects vertical coordinates across the center of workspace.",
        "CS": "Invertovat Y: zrcadlí svislé souřadnice přes střed pracovní plochy.",
    },
    "help_swap_xy": {
        "EN": "Swap XY: interchanges X and Y coordinates ((x, y) -> (y, x)).",
        "CS": "Prohodit XY: zamění souřadnice X a Y ((x, y) -> (y, x)).",
    },

    #center panel canvas
    "canvas_title": {
        "EN": "VECTOR CANVAS (1:1 ISOMETRIC)",
        "CS": "VEKTOROVÉ PLÁTNO (1:1 IZOMETRICKÉ)",
    },
    "legend_guide": {
        "EN": "Target Vector (Guide)",
        "CS": "Cílový vektor (Vodítko)",
    },
    "legend_jump": {
        "EN": "Rapid Jump (G0, Laser OFF)",
        "CS": "Rychlý skok (G0, Laser VYPNUT)",
    },
    "legend_trace": {
        "EN": "Live Trace (G1, Laser ON)",
        "CS": "Živá trať (G1, Laser ZAPNUT)",
    },
    "legend_pointer": {
        "EN": "Beam Cursor",
        "CS": "Kurzor paprsku",
    },
    "legend_btn_guide": {
        "EN": "Guides",
        "CS": "Průvodce",
    },
    "legend_btn_tooltip": {
        "EN": "Show/hide toolpath line guide and color legend.",
        "CS": "Zobrazit/skrýt legendu a barevné vodítko drah.",
    },
    "legend_popup_title": {
        "EN": "TOOLPATH GUIDES",
        "CS": "PRŮVODCE DRÁHAMI",
    },
    "legend_guide_desc": {
        "EN": "Target CAD geometry to trace",
        "CS": "Cílová CAD geometrie ke zpracování",
    },
    "legend_jump_desc": {
        "EN": "Rapid traverse (laser strictly OFF)",
        "CS": "Rychlý přejezd (laser přísně VYPNUT)",
    },
    "legend_trace_desc": {
        "EN": "Laser processed toolpath",
        "CS": "Vypálená dráha laseru",
    },
    "legend_pointer_desc": {
        "EN": "Real-time beam focal position",
        "CS": "Okamžitá poloha ohniska paprsku",
    },
    "base_dim_title": {
        "EN": "BASE DIMENSIONS",
        "CS": "ROZMĚRY ZÁKLADNY",
    },
    "base_dim_width": {
        "EN": "WIDTH (CM)",
        "CS": "ŠÍŘKA (CM)",
    },
    "base_dim_height": {
        "EN": "HEIGHT (CM)",
        "CS": "VÝŠKA (CM)",
    },
    "btn_apply": {
        "EN": "APPLY",
        "CS": "POUŽÍT",
    },
    "btn_reset": {
        "EN": "RESET",
        "CS": "RESETOVAT",
    },
    "tooltip_canvas_edit": {
        "EN": "Click to edit work surface base dimensions (Width x Height).",
        "CS": "Kliknutím upravíte rozměry základny pracovní plochy (Šířka x Výška).",
    },

    #right panel telemetry and controls
    "gauge_trace": {
        "EN": "PATH TRACE",
        "CS": "PRŮBĚH TRASY",
    },
    "gauge_total": {
        "EN": "TOTAL WORK",
        "CS": "CELKOVÁ PRÁCE",
    },
    "dmm_x": {
        "EN": "X AXIS",
        "CS": "OSA X",
    },
    "dmm_y": {
        "EN": "Y AXIS",
        "CS": "OSA Y",
    },
    "view_trace": {
        "EN": "TRACE VIEW",
        "CS": "POHLED STOPY",
    },
    "btn_auto_center_tooltip": {
        "EN": "Center and lock view on laser beam (click & drag canvas to pan freely)",
        "CS": "Vycentrovat a uzamknout pohled na paprsek (tažením myši volný posun)",
    },
    "btn_start": {
        "EN": "START",
        "CS": "SPUSTIT",
    },
    "btn_pause": {
        "EN": "PAUSE",
        "CS": "PAUZA",
    },
    "btn_resume": {
        "EN": "RESUME",
        "CS": "POKRAČOVAT",
    },
    "btn_stop": {
        "EN": "STOP",
        "CS": "ZASTAVIT",
    },
    "btn_home_tooltip": {
        "EN": "Open/close calibration panel to define resting center (Home).",
        "CS": "Otevřít/zavřít panel kalibrace pro nastavení klidového středu (Home).",
    },
    "home_title": {
        "EN": "CALIBRATE HOME",
        "CS": "KALIBROVAT STŘED (HOME)",
    },
    "home_cx": {
        "EN": "CENTER X (CM)",
        "CS": "STŘED X (CM)",
    },
    "home_cy": {
        "EN": "CENTER Y (CM)",
        "CS": "STŘED Y (CM)",
    },
    "home_center_btn": {
        "EN": "CENTER",
        "CS": "VYCENTROVAT",
    },
    "status_ready": {
        "EN": "READY",
        "CS": "PŘIPRAVENO",
    },
    "status_executing": {
        "EN": "EXECUTING",
        "CS": "PROBÍHÁ",
    },
    "status_paused": {
        "EN": "PAUSED",
        "CS": "POZASTAVENO",
    },
    "status_stopped": {
        "EN": "STOPPED",
        "CS": "ZASTAVENO",
    },
    "status_completed": {
        "EN": "COMPLETED",
        "CS": "DOKONČENO",
    },

    #floating terminal and history table
    "term_history": {
        "EN": "📋 History",
        "CS": "📋 Historie",
    },
    "term_logs": {
        "EN": "◀ Logs",
        "CS": "◀ Záznamy",
    },
    "term_export": {
        "EN": "⬇ CSV",
        "CS": "⬇ CSV",
    },
    "col_num": {
        "EN": "#",
        "CS": "#",
    },
    "col_date": {
        "EN": "Date",
        "CS": "Datum",
    },
    "col_dxf": {
        "EN": "DXF",
        "CS": "DXF",
    },
    "col_recipe": {
        "EN": "Recipe",
        "CS": "Receptura",
    },
    "col_mode": {
        "EN": "Mode",
        "CS": "Režim",
    },
    "col_status": {
        "EN": "Status",
        "CS": "Stav",
    },
    "col_duration": {
        "EN": "Duration",
        "CS": "Trvání",
    },
    "hist_no_records": {
        "EN": "No production records found.",
        "CS": "Nebyly nalezeny žádné výrobní záznamy.",
    },
    "hist_export_title": {
        "EN": "Export Production History",
        "CS": "Exportovat historii výroby",
    },
    "hist_export_empty": {
        "EN": "[Export] No records found to export.",
        "CS": "[Export] Žádné záznamy k exportu.",
    },
    "hist_export_ok": {
        "EN": "[Export] History successfully exported to: {file} ({count} records)",
        "CS": "[Export] Historie byla úspěšně exportována do: {file} ({count} záznamů)",
    },
    "hist_export_err": {
        "EN": "[Export] Export error: {err}",
        "CS": "[Export] Chyba exportu: {err}",
    },

    #terminal commands and log messages
    "log_console_init": {
        "EN": "[UFE Laser Console Initialized]\nSystem ready.",
        "CS": "[Konzole laseru ÚFE inicializována]\nSystém připraven.",
    },
    "log_hw_connected": {
        "EN": "[HW] Thorlabs GVS112/M physically connected.",
        "CS": "[HW] Thorlabs GVS112/M fyzicky připojen.",
    },
    "log_hw_sim": {
        "EN": "[HW] Thorlabs GVS112/M not detected — VIRTUAL SIMULATION mode active.",
        "CS": "[HW] Thorlabs GVS112/M nedetekován — Aktivní režim VIRTUÁLNÍ SIMULACE.",
    },
    "log_hw_mode": {
        "EN": "[HW] Thorlabs GVS112/M — Mode: {mode}",
        "CS": "[HW] Thorlabs GVS112/M — Režim: {mode}",
    },
    "log_dxf_loading": {
        "EN": "Loading and parsing geometry, please wait...",
        "CS": "Načítání a zpracování geometrie, čekejte prosím...",
    },
    "log_dxf_loaded": {
        "EN": "[DXF] Loaded: {file} ({paths} paths, {points} points)",
        "CS": "[DXF] Načteno: {file} ({paths} drah, {points} bodů)",
    },
    "log_dxf_err": {
        "EN": "[DXF Error] Failed to load {file}: {err}",
        "CS": "[Chyba DXF] Načtení {file} se nezdařilo: {err}",
    },
    "log_recipe_sel": {
        "EN": "[Recipe] Selected: {name}",
        "CS": "[Receptura] Vybrána: {name}",
    },
    "log_recipe_saved": {
        "EN": "[Recipes] Recipe ID={id} ('{name}') saved to SQLite3.",
        "CS": "[Receptury] Receptura ID={id} ('{name}') uložena do SQLite3.",
    },
    "log_recipe_deleted": {
        "EN": "[Recipes] Recipe '{name}' deleted.",
        "CS": "[Receptury] Receptura '{name}' smazána.",
    },
    "log_home_set": {
        "EN": "[HOME] Manual center set to: ({x:.2f}, {y:.2f}) cm",
        "CS": "[HOME] Manuální střed nastaven na: ({x:.2f}, {y:.2f}) cm",
    },
    "log_base_set": {
        "EN": "[Base] Dimensions: {w:.1f} x {h:.1f} cm | Automatic center: ({cx:.2f}, {cy:.2f}) cm.",
        "CS": "[Základna] Rozměry: {w:.1f} x {h:.1f} cm | Automatický střed: ({cx:.2f}, {cy:.2f}) cm.",
    },
    "log_base_recalc": {
        "EN": "[Base] Dimensions: {w:.1f} x {h:.1f} cm | Automatic center: ({cx:.2f}, {cy:.2f}) cm. Paths recalculated.",
        "CS": "[Základna] Rozměry: {w:.1f} x {h:.1f} cm | Automatický střed: ({cx:.2f}, {cy:.2f}) cm. Dráhy přepočítány.",
    },
    "log_pause": {
        "EN": "[PAUSE] Execution paused. Laser turned off. Timer frozen.",
        "CS": "[PAUZA] Provádění pozastaveno. Laser vypnut. Časomíra zastavena.",
    },
    "log_resume": {
        "EN": "[RESUME] Execution resumed. Laser enabled. Timer active.",
        "CS": "[POKRAČOVAT] Provádění obnoveno. Laser povolen. Časomíra aktivní.",
    },
    "log_stop": {
        "EN": "[STOP] Emergency stop executed by operator.",
        "CS": "[STOP] Nouzové zastavení provedeno operátorem.",
    },
    "log_framing_start": {
        "EN": "[FRAMING] Tracing bounding box perimeter with LASER STRICTLY OFF (gate=0)...",
        "CS": "[FRAMING] Vykreslování obvodu rámečku s LASEREM PŘÍSNĚ VYPNUTÝM (gate=0)...",
    },
    "log_framing_done": {
        "EN": "[FRAMING] Framing perimeter check completed.",
        "CS": "[FRAMING] Kontrola obvodu rámečku dokončena.",
    },
    "log_framing_aborted": {
        "EN": "[FRAMING] Framing routine aborted by operator.",
        "CS": "[FRAMING] Rutina ohraničení přerušena operátorem.",
    },
    "log_framing_err": {
        "EN": "[FRAMING] Framing error: {err}",
        "CS": "[FRAMING] Chyba ohraničení: {err}",
    },
    "log_trace_header": {
        "EN": "=== TRACE STARTED: {file} ===",
        "CS": "=== ZAHÁJENÍ DRÁHY: {file} ===",
    },
    "log_trace_start": {
        "EN": "[EXEC] Starting process in mode: {mode} | Passes: {passes} | File: {file}",
        "CS": "[PROCES] Zahájení v režimu: {mode} | Průchody: {passes} | Soubor: {file}",
    },
    "log_trace_hw": {
        "EN": "Hardware: {hw} | Mode: {mode}",
        "CS": "Hardware: {hw} | Režim: {mode}",
    },
    "log_trace_paths": {
        "EN": "Paths: {paths} | Waypoints: {waypoints} | Passes: {passes}",
        "CS": "Dráhy: {paths} | Body: {waypoints} | Průchody: {passes}",
    },
    "log_trace_speeds": {
        "EN": "Mark speed: {mark} mm/s | Jump speed: {jump} mm/s",
        "CS": "Rychlost značení: {mark} mm/s | Rychlost skoku: {jump} mm/s",
    },
    "log_trace_delays": {
        "EN": "Delays: jump={jump:g} ms | mark={mark:g} ms | laser ON={on:g} ms | laser OFF={off:g} ms | cooling={cooling:g} s",
        "CS": "Zpoždění: skok={jump:g} ms | značení={mark:g} ms | laser ZAP={on:g} ms | laser VYP={off:g} ms | chlazení={cooling:g} s",
    },
    "log_lang_changed": {
        "EN": "[System] Language switched to English.",
        "CS": "[Systém] Jazyk přepnut na Češtinu.",
    },
    "log_framing_busy": {
        "EN": "[Framing] Execution engine is busy. Cannot start framing.",
        "CS": "[Framing] Prováděcí modul je zaneprázdněn. Nelze zahájit ohraničení.",
    },
    "log_framing_routine_start": {
        "EN": "=== FRAMING ROUTINE STARTED ({vueltas} lap{s}) ===",
        "CS": "=== ZAHÁJENA RUTINA OHRANIČENÍ ({vueltas} cyklů) ===",
    },
    "log_framing_bbox": {
        "EN": "[Framing] Bounding Box: X[{min_x:.2f}, {max_x:.2f}] mm | Y[{min_y:.2f}, {max_y:.2f}] mm",
        "CS": "[Framing] Ohraničující rámeček: X[{min_x:.2f}, {max_x:.2f}] mm | Y[{min_y:.2f}, {max_y:.2f}] mm",
    },
    "log_framing_speed": {
        "EN": "[Framing] Travel speed: {speed} mm/s | Laser Gate: STRICTLY 0 (OFF)",
        "CS": "[Framing] Rychlost přejezdu: {speed} mm/s | Hradlo laseru: PŘÍSNĚ 0 (VYP)",
    },
    "log_framing_stopped_op": {
        "EN": "[Framing] Stopped by operator.",
        "CS": "[Framing] Zastaveno operátorem.",
    },
    "log_framing_ok": {
        "EN": "[Framing] Routine completed successfully. Galvos safely at Home.",
        "CS": "[Framing] Rutina úspěšně dokončena. Galva bezpečně v pozici Home.",
    },
    "log_exec_processing": {
        "EN": "[EXEC] Processing CAD/DXF geometry inside worker thread...",
        "CS": "[PROCES] Zpracování CAD/DXF geometrie v pracovním vlákně...",
    },
    "log_exec_pass": {
        "EN": "[EXEC] Starting process in mode: {mode} | Pass {pass_idx}/{passes}",
        "CS": "[PROCES] Zahájení v režimu: {mode} | Průchod {pass_idx}/{passes}",
    },
    "log_stop_executed": {
        "EN": "[STOP] Emergency stop executed.",
        "CS": "[STOP] Nouzové zastavení provedeno.",
    },
    "log_stop_rest": {
        "EN": "[STOP] Laser off. System safely at rest.",
        "CS": "[STOP] Laser vypnut. Systém v bezpečném klidu.",
    },
    "log_work_completed": {
        "EN": "Work cycle completed successfully!",
        "CS": "Pracovní cyklus byl úspěšně dokončen!",
    },
    "log_db_recorded": {
        "EN": "[DB] Cycle recorded: Status={status}, Duration={dur}s",
        "CS": "[DB] Záznam cyklu uložen: Stav={status}, Doba={dur}s",
    },

    #dialogs and notices
    "dlg_hw_notice_title": {
        "EN": "Hardware Notice",
        "CS": "Upozornění na hardware",
    },
    "dlg_hw_notice_msg": {
        "EN": "The Thorlabs GVS112/M system is not physically connected.\n\nDo you want to start execution in VIRTUAL SIMULATION MODE?",
        "CS": "Systém Thorlabs GVS112/M není fyzicky připojen.\n\nChcete zahájit provádění v REŽIMU VIRTUÁLNÍ SIMULACE?",
    },
    "dlg_missing_dxf_title": {
        "EN": "Missing DXF",
        "CS": "Chybí soubor DXF",
    },
    "dlg_missing_dxf_msg": {
        "EN": "You must load a DXF file with valid paths before starting.",
        "CS": "Před spuštěním musíte načíst soubor DXF s platnými dráhami.",
    },
    "dlg_missing_geom_title": {
        "EN": "Missing Geometry",
        "CS": "Chybí geometrie",
    },
    "dlg_missing_geom_msg": {
        "EN": "You must load a DXF file before running framing.",
        "CS": "Před spuštěním ohraničení musíte načíst soubor DXF.",
    },
    "dlg_invalid_params_title": {
        "EN": "Invalid Parameters",
        "CS": "Neplatné parametry",
    },
    "dlg_invalid_params_msg": {
        "EN": "Kinematic speeds must be greater than zero.",
        "CS": "Kinematické rychlosti musí být větší než nula.",
    },
    "dlg_cancel_exec_title": {
        "EN": "Cancel Execution",
        "CS": "Zrušit provádění",
    },
    "dlg_cancel_exec_msg": {
        "EN": "Are you sure you want to cancel the current cutting process?",
        "CS": "Opravdu chcete zrušit aktuální proces řezání?",
    },
    "dlg_cancel_framing_title": {
        "EN": "Cancel Framing",
        "CS": "Zrušit ohraničení",
    },
    "dlg_cancel_framing_msg": {
        "EN": "Are you sure you want to stop the framing process?\n\nThe optical head will be safely realigned to resting center (Home).",
        "CS": "Opravdu chcete zastavit proces ohraničení?\n\nOptická hlava bude bezpečně vrácena do výchozího středu (Home).",
    },
    "dlg_cycle_finished_title": {
        "EN": "Cycle Finished",
        "CS": "Cyklus dokončen",
    },
    "dlg_cycle_finished_msg": {
        "EN": "Job successfully completed in {dur} seconds.",
        "CS": "Úloha byla úspěšně dokončena za {dur} sekund.",
    },
    "dlg_cycle_aborted_title": {
        "EN": "Cycle Aborted",
        "CS": "Cyklus přerušen",
    },
    "dlg_cycle_aborted_msg": {
        "EN": "The job was immediately aborted by the operator.\nThe laser has been turned off and the head returned to resting center.",
        "CS": "Úloha byla okamžitě přerušena operátorem.\nLaser byl vypnut a optická hlava vrácena do výchozího středu.",
    },
    "dlg_cycle_error_title": {
        "EN": "Cycle Error",
        "CS": "Chyba cyklu",
    },
    "dlg_cycle_error_msg": {
        "EN": "An error occurred during tracing:\n{err}",
        "CS": "Během vykreslování došlo k chybě:\n{err}",
    },

    #recipe dialogs
    "dlg_save_recipe_title": {
        "EN": "Save Parameters",
        "CS": "Uložit parametry",
    },
    "dlg_save_recipe_msg": {
        "EN": "Do you want to save the updated cutting parameters for '{name}'?",
        "CS": "Chcete uložit aktualizované parametry řezání pro '{name}'?",
    },
    "dlg_save_recipe_ok": {
        "EN": "Recipe '{name}' successfully updated.",
        "CS": "Receptura '{name}' byla úspěšně aktualizována.",
    },
    "dlg_new_recipe_prompt": {
        "EN": "Enter new recipe name:",
        "CS": "Zadejte název nové receptury:",
    },
    "dlg_new_recipe_title": {
        "EN": "New Recipe",
        "CS": "Nová receptura",
    },
    "dlg_new_recipe_ok": {
        "EN": "Recipe '{name}' successfully created.",
        "CS": "Receptura '{name}' byla úspěšně vytvořena.",
    },
    "dlg_protected_recipe_title": {
        "EN": "Protected Recipe",
        "CS": "Chráněná receptura",
    },
    "dlg_protected_recipe_msg": {
        "EN": "Recipe '{name}' is a factory preset and cannot be deleted.\n\nOnly custom recipes created by the user can be deleted.",
        "CS": "Receptura '{name}' je tovární předvolba a nelze ji smazat.\n\nSmazat lze pouze vlastní receptury vytvořené uživatelem.",
    },
    "dlg_del_recipe_title": {
        "EN": "Confirm Deletion",
        "CS": "Potvrdit smazání",
    },
    "dlg_del_recipe_msg": {
        "EN": "Delete recipe '{name}' from the database?",
        "CS": "Smazat recepturu '{name}' z databáze?",
    },
    "dlg_del_recipe_ok": {
        "EN": "Recipe '{name}' deleted.",
        "CS": "Receptura '{name}' byla smazána.",
    },
}


def tr(clave: str, **kwargs: Any) -> str:
    """get translated string for key in active language"""
    entrada = _TEXTOS.get(clave)
    if not entrada:
        return clave

    plantilla = entrada.get(_idioma_activo) or entrada.get(IDIOMA_EN) or clave
    if kwargs:
        try:
            return plantilla.format(**kwargs)
        except Exception:
            return plantilla
    return plantilla


def obtener_idioma() -> str:
    """get active language code en or cs"""
    return _idioma_activo


def cambiar_idioma(nuevo_idioma: str):
    """set active language and notify observers"""
    global _idioma_activo
    nuevo = nuevo_idioma.upper()
    if nuevo in IDIOMAS_DISPONIBLES and nuevo != _idioma_activo:
        _idioma_activo = nuevo
        for obs in list(_observadores):
            try:
                obs()
            except Exception as e:
                print(f"[i18n] Error al actualizar observador: {e}")


def registrar_observador(callback: Callable[[], None]):
    """register callback observer for language changes"""
    if callback not in _observadores:
        _observadores.append(callback)


def desregistrar_observador(callback: Callable[[], None]):
    """unregister language change observer"""
    if callback in _observadores:
        _observadores.remove(callback)
