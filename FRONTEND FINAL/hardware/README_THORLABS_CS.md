# INTEGRAČNÍ MANUÁL PRO THORLABS GVS112/M A NI PXI-6229
**Projekt:** Řídicí software vláknového laseru pro zpracování polymerů  
**Hostitelská instituce:** Ústav fotoniky a elektroniky AV ČR (ÚFE AV ČR), Praha  
**Autor / Vývojář:** Andrei Martínez Bahena (Residente Profesional TecNM / ÚFE AV ČR)  
**Verze:** 1.0.0 (Produkční vydání)  
**Cílový hardware:** Šasi NI PXIe-1073, DAQ karta NI PXI-6229, dvouosá galvanometrická hlava Thorlabs GVS112/M  
**Optika:** F-Théta skenovací objektiv (f = 163 mm, pracovní pole 100 × 100 mm, thuliový vláknový laser 1940–2050 nm)

---

## 1. Přehled systému a architektura balíčku

Aplikace pro řízení laserového svazku je strukturována jako modulární balíček v jazyce Python s přísným oddělením grafického uživatelského rozhraní (HMI), algoritmů plánování trajektorií (CAM), relační databáze a deterministické vrstvy abstrakce hardwaru (HAL).

```text
FRONTEND FINAL/
│
├── iniciar_interfaz.py            # Hlavní vstupní bod aplikace (Cyber-Brutalist HMI v CustomTkinter)
├── test_system_full.py            # 8fázová integrační testovací sada celého systému
├── setup_environment.ps1          # Automatizovaný instalační skript pro PowerShell
├── requirements.txt               # Přesně specifikované závislosti balíčků v Pythonu
├── visualizar_comparativa.py      # Diagnostický nástroj pro srovnání CAD vs. CAM
│
├── core/
│   ├── CADConverter.py            # Automatická konverze DXF na G-kód (wrapper pro FreeCAD CLI)
│   ├── GCodeParser.py             # Interpret G-kódu dle normy ISO 6983 a generátor TrajectoryBlock
│   ├── PathOptimizer.py           # Optimalizace drah pomocí RDP a heuristického řešiče 2-Opt TSP
│   ├── GalvoSignalGenerator.py    # Deterministická syntéza vlnových průběhů (100 kS/s) a optických zpoždění
│   ├── NIDaqController.py         # Hardwarem řízené FIFO streamování pro NI-DAQmx a simulační smyčka
│   ├── config_loader.py           # Centralizovaný zavaděč konfigurace hardwaru a záložních hodnot
│   ├── generador_trayectorias.py  # Geometrické funkce pro tvorbu trajektorií
│   └── lector_dxf.py              # Rekurzivní čtení vektorových entit z DXF pomocí ezdxf
│
├── hardware/
│   ├── hardware_config.json       # Kanonická konfigurace kanálů DAQ, kalibrace (0.200 V/mm) a limity
│   ├── config_galvo.py            # Kinematické limity galva, skenovací pole a výchozí zpoždění
│   ├── controlador_thorlabs.py    # Hardwarová abstrakce pro ovladač Thorlabs GVS112/M
│   ├── simulador_thorlabs.py      # Vysoce věrný virtuální simulační engine kinematiky
│   ├── README_THORLABS.md         # Uživatelská a hardwarová příručka (anglicky)
│   └── README_THORLABS_CS.md      # Uživatelská a hardwarová příručka (česky)
│
├── database/
│   ├── gestor_db.py               # SQLite3 databáze s režimem Write-Ahead Logging (WAL) a migracemi
│   ├── recetas.py                 # Správa a ukládání receptur pro polymery (PMMA, PC, Nylon, PEEK)
│   ├── trazabilidad.py            # Protokolování historie výroby a auditní záznamy (historial_produccion)
│   └── laser_system.db            # Trvalý soubor databáze SQLite3
│
├── interfaz/
│   ├── interfaz_app.py            # Hlavní aplikační okno CustomTkinter a koordinátor životního cyklu
│   ├── barra_superior.py          # Stavový řádek, volič režimů a systémové hodiny
│   ├── panel_general.py           # Levý ovládací panel (tlačítka spuštění, manuální krokování)
│   ├── panel_configuracion.py     # Panel pro nastavení kinematiky, optických zpoždění a laseru
│   ├── panel_derecho.py           # Pravý panel se správou receptur a auditním protokolem
│   ├── renderizado_dual.py        # Vektorové plátno náhledu (původní CAD vs. výstupní prostor galva)
│   ├── terminal_flotante.py       # Plovoucí diagnostická a záznamová konzole
│   ├── conexion_interfaz.py       # Asynchronní vláknové propojení (PuenteLaser) mezi GUI a HAL
│   ├── constantes.py              # Barevná paleta, typografické styly a konstanty rozhraní
│   ├── i18n.py                    # Vícejazyčná podpora (španělština, angličtina, čeština)
│   └── fonts/                     # Vložená typografie (BrunoAce-Regular, Teachers-Regular)
│
├── dxf/                           # Produkční vektorové návrhy DXF (testovací geometrie)
└── gcode/                         # Předkompilované trajektorie G-kódu ISO 6983
```

---

## 2. Automatizovaná příprava prostředí a závislosti

Řídicí počítač v laserové laboratoři ÚFE vyžaduje 64bitové prostředí Windows (Windows 10/11) s nainstalovaným ovladačem NI-DAQmx Runtime verze 21.0 nebo vyšší.

### 2.1 Automatizované nasazení (PowerShell)
Spusťte terminál PowerShell jako správce (Run as Administrator), přejděte do kořenového adresáře projektu a spusťte:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\setup_environment.ps1
```

Skript provede následující čtyřfázový validační proces:
1. **Ověření CLI rozhraní FreeCAD:** Vyhledá `FreeCADcmd.exe` v systémové proměnné `PATH`. Pokud chybí, prohledá standardní instalační složky (`%LOCALAPPDATA%`, `%ProgramFiles%`, `%ProgramFiles(x86)%`) a trvale zaregistruje složku do uživatelské proměnné `PATH`.
2. **Kontrola běhového prostředí Python:** Ověří přítomnost 64bitové instalace Python verze 3.10 nebo vyšší.
3. **Instalace závislostí:** Automaticky aktualizuje nástroj `pip` a nainstaluje balíčky ze souboru `requirements.txt`.
4. **Diagnostická sebekontrola:** Zkontroluje výstup hlavičky FreeCAD CLI a spustí automatizovaný importní test modulů (`ezdxf`, `numpy`, `scipy`, `nidaqmx`, `customtkinter`).

### 2.2 Seznam závislostí (`requirements.txt`)
```text
# Grafické uživatelské rozhraní (Cyber-Brutalist HMI)
customtkinter>=5.2.0

# Numerické výpočty a prostorová diskretizace CAM
numpy>=1.24.0
scipy>=1.10.0

# Vektorové zpracování CAD geometrie (DXF)
ezdxf>=1.1.0

# Přístrojové řízení a synchronizovaný sběr dat DAQ (National Instruments)
nidaqmx>=0.9.0
```

> [!NOTE]
> Zastaralé balíčky (`matplotlib`, `pyqtgraph`, `PyQt5`, `pyserial`, `Pillow`) byly zcela odstraněny. Vektorové vykreslování probíhá na nativních plátnech CustomTkinter a přenos signálů DAQ komunikuje přímo přes nízkoúrovňovou dynamickou knihovnu C ovladače NI-DAQmx (`nicaiu.dll`).

---

## 3. Zapojení hardwaru a mapování pinů DAQ

Systém využívá multifunkční I/O kartu **NI PXI-6229** umístěnou v šasi **NI PXIe-1073**. Signály jsou vyvedeny přes dvojitě stíněný kabel **NI SHC68-68-EPM** do nízkošumové svorkovnice **NI SCB-68A**.

```text
+-------------------+      NI SHC68-68-EPM      +------------------+
|    NI PXI-6229    | =======================> |    NI SCB-68A    |
| (Slot 2, PXIe-10) |   Stíněný 68pinový kabel | Svorkovnice      |
+-------------------+                           +--------+---------+
                                                         |
         +-----------------------------------------------+
         |
         |--> Pin 22 (PXI1Slot5/ao0) --------> Ovladač Thorlabs X: Řídicí vstup (+) [Pin 1]
         |--> Pin 55 (AO GND) ----------> Ovladač Thorlabs X: Řídicí vstup (-) [Pin 2]
         |
         |--> Pin 21 (PXI1Slot5/ao1) --------> Ovladač Thorlabs Y: Řídicí vstup (+) [Pin 1]
         |--> Pin 54 (AO GND) ----------> Ovladač Thorlabs Y: Řídicí vstup (-) [Pin 2]
         |
         |--> Pin 52 (PXI1Slot5/port0/line0) -> Hradlový oddělovač / optočlen laseru (+)
         |--> Pin 53 (DGND) ------------> Zpětný vodič modulace laseru (-)
         |
         | [Volitelná zpětná vazba polohy zrcadel přes diferenciální AI]
         |--> Pin 68 (PXI1Slot5/ai0+) -------> Ovladač Thorlabs X: Monitor polohy (+) [Pin 3]
         |--> Pin 34 (PXI1Slot5/ai8 / ai0-) -> Ovladač Thorlabs X: Monitor polohy (-) [Pin 4]
         |--> Pin 33 (PXI1Slot5/ai1+) -------> Ovladač Thorlabs Y: Monitor polohy (+) [Pin 3]
         +--> Pin 66 (PXI1Slot5/ai9 / ai1-) -> Ovladač Thorlabs Y: Monitor polohy (-) [Pin 4]
```

### 3.1 Tabulka zapojení svorkovnice SCB-68A

| Svorka SCB-68A | Název signálu | Popis signálu | Připojení Thorlabs GVS112/M / Laser |
| :--- | :--- | :--- | :--- |
| **Pin 22** | `PXI1Slot5/ao0` | Analogový výstup 0 (výchylka osy X) | Ovladač X, konektor J4 Pin 1: Řídicí vstup (+) |
| **Pin 55** | `AO GND` | Analogová zem (reference pro AO0) | Ovladač X, konektor J4 Pin 2: Řídicí vstup (-) |
| **Pin 21** | `PXI1Slot5/ao1` | Analogový výstup 1 (výchylka osy Y) | Ovladač Y, konektor J4 Pin 1: Řídicí vstup (+) |
| **Pin 54** | `AO GND` | Analogová zem (reference pro AO1) | Ovladač Y, konektor J4 Pin 2: Řídicí vstup (-) |
| **Pin 52** | `PXI1Slot5/port0/line0` | Digitální výstup (řízené hradlování laseru) | Vstup modulace laseru (TTL 5V = ZAP, 0V = VYP) |
| **Pin 53** | `DGND` | Digitální zem | Společná signálová zem modulace laseru (-) |
| **Pin 68** | `PXI1Slot5/ai0` (+) | Analogový vstup 0 kladný (monitor polohy X) | Ovladač X, konektor J4 Pin 3: Výstup polohy (+) |
| **Pin 34** | `PXI1Slot5/ai8` / `ai0` (-) | Analogový vstup 0 záporný (diferenciální návrat) | Ovladač X, konektor J4 Pin 4: Výstup polohy (-) |
| **Pin 33** | `PXI1Slot5/ai1` (+) | Analogový vstup 1 kladný (monitor polohy Y) | Ovladač Y, konektor J4 Pin 3: Výstup polohy (+) |
| **Pin 66** | `PXI1Slot5/ai9` / `ai1` (-) | Analogový vstup 1 záporný (diferenciální návrat) | Ovladač Y, konektor J4 Pin 4: Výstup polohy (-) |
| **Svorník šasi** | `SHIELD` | Vnější stínění kabelu | Centrální zemnicí bod (star ground) šasi |

### 3.2 Konfigurace servozesilovačů Thorlabs
Každá deska ovladače GVS112/M je z výroby přesně naladěna pro příslušný galvanometrický motor. Dbejte na následující nastavení:
- **Vstupní režim:** Diferenciální konfigurace (konektor J4 Pin 1 = Signál +, Pin 2 = Signál -). **Nepropojujte Pin 2 s lokální zemí na desce ovladače**; referenční zem musí vést přímo na svorku `AO GND` bloku NI SCB-68A, aby nevznikaly zemní smyčky.
- **Napájecí zdroj:** Použijte lineární regulovaný stejnosměrný zdroj ±15.0 V schopný dodat proud ≥ 3.0 A na kanál. Zkontrolujte, že zvlnění nepřesahuje 10 mV RMS.
- **Chlazení:** Obě desky ovladačů musí být pevně přišroubovány k hliníkovému chladiči. Při překročení teploty chladiče 70 °C zareaguje tepelná ochrana a odpojí pohon.

---

## 4. Optická kalibrace a konfigurace (`hardware_config.json`)

Matematický přepočet mezi metrickými souřadnicemi (mm) a řídicím napětím (V) je dán efektivní ohniskovou vzdáleností telecentrického F-Théta objektivu (**f = 163 mm**, pracovní pole **100 × 100 mm**, odpovídající rozsahu **-50 mm až +50 mm** v obou osách).

Jmenovitý rozsah výstupního napětí DAQ karty NI PXI-6229 je **±10.0 V**. Kanonický prostorový převodní koeficient je proto:

> **k = 10.0 V / 50.0 mm = 0.200 V/mm**

Pro zadanou souřadnici *s* (v mm) je generováno napětí:

> **V(s) = s × k = s × 0.200 V/mm**

Při dané optické geometrii (f = 163 mm) odpovídá optický úhel vychýlení svazku:

> **θ_opt = s / f**

Příslušné mechanické natočení zrcadla galva je:

> **θ_mech = θ_opt / 2 = s / (2 × f)**

Jelikož optický odraz zdvojnásobuje úhlovou výchylku dopadajícího svazku (2 × θ_mech = θ_opt), tento vztah přesně odpovídá továrně kalibrované citlivosti desky ovladače Thorlabs GVS112/M (0.5 rad/V optické výchylky na řídicí volt).

### 4.1 Struktura konfiguračního souboru (`hardware/hardware_config.json`)

```json
{
  "volts_per_mm": 0.200,
  "voltage_limits": {
    "min": -10.0,
    "max": 10.0
  },
  "daq": {
    "device_name": "PXI1Slot5",
    "analog_channels": [
      "PXI1Slot5/ao0",
      "PXI1Slot5/ao1"
    ],
    "laser_gate_channel": "PXI1Slot5/port0/line0",
    "ai_channels": [
      "PXI1Slot5/ai0",
      "PXI1Slot5/ai1"
    ],
    "ai_terminal_config": "DIFF",
    "sample_rate_hz": 100000.0,
    "sync_clock": "/PXI1Slot5/ao/SampleClock",
    "feedback_sign_x": 1,
    "feedback_sign_y": 1,
    "feedback_offset_x_v": 0.0,
    "feedback_offset_y_v": 0.0
  },
  "cad_cam": {
    "freecad_cmd": "FreeCADcmd",
    "timeout_seconds": 30,
    "rdp_tolerance": 0.0
  }
}
```

### 4.2 Dynamická zpoždění galva (časová kompenzace setrvačnosti)
Pro kompenzaci mechanické setrvačnosti zrcadel a reakčních časů laseru jsou generátorem signálu `GalvoSignalGenerator` vkládána deterministická zpoždění:
- `jump_delay_us` (výchozí: 100–150 µs): Čas pro mechanické ustálení polohy po rychlém přejezdu s vypnutým laserem (G0).
- `mark_delay_us` (výchozí: 20–50 µs): Zpoždění pro ustálení na konci pracovního vektoru (G1) před změnou směru nebo skokem.
- `laser_on_delay_us` (výchozí: 20–50 µs): Předstih zapnutí laseru umožňující dosáhnout cílovou rychlost ještě před zahájením emise.
- `laser_off_delay_us` (výchozí: 20–30 µs): Zpoždění vypnutí laseru před zpomalením zrcadel, eliminující propaly na koncích drah.

---

## 5. Uvádění do provozu a bezpečnostní protokol

Před zapnutím vysokovýkonného thuliového vláknového laseru dodržujte tento přesný postup:

```text
[Krok 1: Vizuální kontrola] ---> [Krok 2: Automatizovaný 8fázový test] ---> [Krok 3: Napájení ovladačů]
                                                                                   |
[Krok 6: Zahájení výroby]   <--- [Krok 5: Seřízení pilotního laseru]   <--- [Krok 4: Kontrola osciloskopem]
```

### Krok 1: Vizuální a mechanická kontrola
1. Ověřte, že je z objektivu F-Théta sejmuta ochranná krytka.
2. Zkontrolujte funkčnost odsávacího systému spalin umístěného pod pracovní plochou laserové komory.
3. Ujistěte se, že bezpečnostní zámky (interlocky) dvířek ochranného krytu jsou sepnuty a aktivní.

### Krok 2: Automatizovaný 8fázový systémový test
Spusťte kompletní validační baterii z kořenového adresáře projektu:

```powershell
python test_system_full.py
```

**Kontrolní seznam výsledků (všech 8 fází musí skončit stavem [OK] / [PASS]):**
- **Fáze 1 (Prostředí):** Ověření běhového prostředí Python, CustomTkinter a dostupnosti NI-DAQmx.
- **Fáze 2 (CAD Ingesce):** Automatická konverze DXF na G-kód pomocí `CADConverter` a `GCodeParser`.
- **Fáze 3 (Optimalizace):** Zachování geometrie algoritmem RDP a minimalizace přejezdů pomocí 2-Opt TSP.
- **Fáze 4 (Vlnové průběhy):** Diskretizace na frekvenci 100 kS/s (Δt = 10.0 µs), napěťové omezení v mezích [-10.0 V, +10.0 V] a přesný výpočet střídy laseru.
- **Fáze 5 (Hardware a E-STOP):** Konfigurace FIFO vyrovnávací paměti, zápis dat a bezpečné okamžité parkování na 0.0 V při nouzovém zastavení.
- **Fáze 6 (Databáze):** Prověření zápisu SQLite3 v režimu WAL (`PRAGMA journal_mode=WAL;`), tabulky receptur a auditního protokolu.
- **Fáze 7 (Vlákna a telemetrie):** Nezávislý běh pracovního vlákna na pozadí (`PuenteLaser`) a příjem telemetrických dat v reálném čase.
- **Fáze 8 (Integrita):** Bezpečné smazání všech dočasných souborů a uvolnění systémových prostředků.

*Očekávaný výstup:*
```text
STATUS: ALL SYSTEM CRITICAL MODULES OPERATIONAL AND HARDENED.
```

### Krok 3: Postup zapnutí napájení ovladačů galva
1. Zapněte lineární regulovaný stejnosměrný zdroj ±15.0 V.
2. Zkontrolujte, zda se na obou deskách Thorlabs trvale rozsvítily zelené stavové LED diody.
3. Ověřte, že se obě zrcadla okamžitě nastavila do středové výchozí polohy (0.000 V).
4. Lehce se dotkněte těl motorů galva; nesmí vykazovat žádné vysokofrekvenční oscilace, bzučení ani nadměrné zahřívání.

### Krok 4: Testování trajektorie s osciloskopem
Připojte sondy osciloskopu ke svorkám `PXI1Slot5/ao0` (kanál 1), `PXI1Slot5/ao1` (kanál 2) a `PXI1Slot5/port0/line0` (kanál 3) na bloku SCB-68A. Spusťte testovací cyklus:

```powershell
python test_system_full.py
```

**Kritéria ověření:**
- Vzorkovací perioda signálu odpovídá Δt = 10.0 µs (100 kS/s).
- Přechody v rozích jsou čisté bez překmitů (overshoot) a zvonění.
- Signál modulace laseru (`PXI1Slot5/port0/line0`) spolehlivě padá na 0.0 V (úroveň TTL LOW) během všech přejezdů naprázdno (G0).

### Krok 5: Seřízení polohy pomocí červeného zaměřovacího laseru
1. Zapněte červenou zaměřovací diodu (635 nm).
2. Spusťte testovací čtvercový vzor (50.0 × 50.0 mm) na termocitlivý terč.
3. Změřte skutečné rozměry vypáleného nebo ozářeného čtverce přesným posuvným měřidlem.
4. Pokud rozměrová odchylka překročí ±0.05 mm, upravte hodnotu `volts_per_mm` v `hardware_config.json`:

> **k_nové = k_stávající × (Požadovaná délka / Naměřená délka)**

### Krok 6: Povolení produkčního provozu
Spusťte produkční grafické rozhraní:

```powershell
python iniciar_interfaz.py
```

1. V rozevíracím seznamu zvolte ověřenou recepturu pro daný polymer (např. `Acrylic – Standard`, `Polycarbonate – High Precision` nebo `Nylon – Fast Cutting`).
2. Načtěte cílový vektorový výkres DXF (nebo zadejte G-kód).
3. Na duálním plátnu zkontrolujte, zda trajektorie leží bezpečně uvnitř zeleně vyznačeného pracovního pole.
4. Stiskněte **START (EJECUTAR)** pro zahájení hardwarem časovaného procesu. V případě jakékoliv anomálie stiskněte **NOUZOVÉ ZASTAVENÍ (PARADA DE EMERGENCIA)** pro okamžité zhasnutí paprsku a odstavení zrcadel.

---

## 6. Technická podpora a systémová diagnostika

- **Autor / vývojář:** Andrei Martínez Bahena (Residente Profesional TecNM / Ústav fotoniky a elektroniky AV ČR).
- **Hostitelská instituce:** Ústav fotoniky a elektroniky AV ČR, v. v. i. (ÚFE AV ČR), Praha.
- **Oddělení:** Oddělení vláknových laserů a nelineární optiky.
- **Adresa pracoviště:** Chaberská 1014/57, 182 00 Praha 8, Česká republika.
- **Referenční dokumentace:** Schémata systémové architektury, migrace databáze a diagramy jsou popsány v systémové dokumentaci a sadách jednotkových testů.
