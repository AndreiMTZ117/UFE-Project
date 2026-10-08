// =========================================================
// lectorESP32.ino — Firmware de Control Láser de Alta Precisión
// =========================================================
// Control directo de servomotores mediante temporizadores LEDC
// de 16 bits del ESP32 (resolución de 0.3 µs por paso).
//
// CONEXIONES RECOMENDADAS:
//   - Pin GPIO 18 -> Señal Servo X (Cable Amarillo/Naranja)
//   - Pin GPIO 19 -> Señal Servo Y (Cable Amarillo/Naranja)
//   - Pin GPIO 23 -> Señal Láser (Entrada circuito Darlington)
//   - Pin GND     -> Tierra común con la fuente de 5V de los servos
// =========================================================

#include <Arduino.h>

// =========================================================
// ASIGNACIÓN DE PINES GPIO
// =========================================================
#define PIN_SERVO_X  18   // GPIO para señal Servo X
#define PIN_SERVO_Y  19   // GPIO para señal Servo Y
#define PIN_LASER    23   // GPIO para control del láser (Darlington)

// Canales LEDC (para ESP32 Core v2.x)
#define CANAL_SERVO_X 0
#define CANAL_SERVO_Y 1

#define SERVO_FREQ_HZ 50       // 50 Hz estándar para servos (periodo = 20,000 µs)
#define PWM_RES_BITS  16       // 16 bits de resolución (0 a 65,535 niveles)

// Microsegundos para calibración de servos (0° a 180°)
// Calibrados para coincidir exactamente con los ángulos de la maqueta
#define US_MIN_X  537.0f         // Pulso mínimo X (~0° / ~537 µs, equivalente a PCA9685 tick 110)
#define US_MAX_X  2200.0f        // Pulso máximo X (~180° / ~2200 µs, equivalente a PCA9685 tick 450)
#define US_MIN_Y  537.0f         // Pulso mínimo Y (~0° / ~537 µs)
#define US_MAX_Y  2200.0f        // Pulso máximo Y (~180° / ~2200 µs)
#define US_MIN    537.0f         // Referencia genérica
#define US_MAX    2200.0f

// =========================================================
// CALIBRACIÓN: Límites y centro de la maqueta
// 1: Superior Izquierdo (55, 62)
// 2: Inferior Izquierdo (55, 39)
// 3: Inferior Derecho   (63, 39)
// 4: Superior Derecho   (63, 62)
// =========================================================
const float CENTRO_MAQUETA_X = 59.00f;
const float CENTRO_MAQUETA_Y = 50.50f;

// =========================================================
// COLA DE WAYPOINTS (LOOKAHEAD BUFFER)
// =========================================================
struct Waypoint {
  float x;
  float y;
  unsigned long duracion_ms;
  uint8_t estado_laser; // 0 = APAGADO, 1 = ENCENDIDO, 2 = SIN CAMBIO
};

#define BUFFER_SIZE 64
Waypoint colaWaypoints[BUFFER_SIZE];
volatile int colaHead = 0;
volatile int colaTail = 0;
volatile int colaCount = 0;

bool encolarWaypoint(float x, float y, unsigned long dur, uint8_t laser) {
  if (colaCount >= BUFFER_SIZE) return false;
  colaWaypoints[colaHead].x = x;
  colaWaypoints[colaHead].y = y;
  colaWaypoints[colaHead].duracion_ms = dur;
  colaWaypoints[colaHead].estado_laser = laser;
  colaHead = (colaHead + 1) % BUFFER_SIZE;
  colaCount++;
  return true;
}

bool desencolarWaypoint(Waypoint &wp) {
  if (colaCount <= 0) return false;
  wp = colaWaypoints[colaTail];
  colaTail = (colaTail + 1) % BUFFER_SIZE;
  colaCount--;
  return true;
}

void limpiarCola() {
  colaHead = 0;
  colaTail = 0;
  colaCount = 0;
}

// =========================================================
// VARIABLES DE ESTADO Y MOVIMIENTO
// =========================================================
float posX_actual = CENTRO_MAQUETA_X;
float posY_actual = CENTRO_MAQUETA_Y;

float segInicioX = CENTRO_MAQUETA_X;
float segInicioY = CENTRO_MAQUETA_Y;
float segDestinoX = CENTRO_MAQUETA_X;
float segDestinoY = CENTRO_MAQUETA_Y;
unsigned long segInicioTiempo = 0;
unsigned long segDuracion = 0;
bool enMovimiento = false;
volatile bool abortado = false;  // Flag de aborto: bloquea encolamiento de nuevos waypoints

uint32_t ultimoDutyX = 0;
uint32_t ultimoDutyY = 0;

// Buffer de recepción serie
char bufferSerie[64];
int indiceBuffer = 0;

// =========================================================
// CONTROL PWM DE ALTA RESOLUCIÓN (16 BITS / 0.3 µs)
// =========================================================
void setupPWM() {
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(PIN_SERVO_X, SERVO_FREQ_HZ, PWM_RES_BITS);
  ledcAttach(PIN_SERVO_Y, SERVO_FREQ_HZ, PWM_RES_BITS);
#else
  ledcSetup(CANAL_SERVO_X, SERVO_FREQ_HZ, PWM_RES_BITS);
  ledcAttachPin(PIN_SERVO_X, CANAL_SERVO_X);
  ledcSetup(CANAL_SERVO_Y, SERVO_FREQ_HZ, PWM_RES_BITS);
  ledcAttachPin(PIN_SERVO_Y, CANAL_SERVO_Y);
#endif

  pinMode(PIN_LASER, OUTPUT);
  digitalWrite(PIN_LASER, LOW);
}

inline void escribirServoX(uint32_t duty) {
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_SERVO_X, duty);
#else
  ledcWrite(CANAL_SERVO_X, duty);
#endif
}

inline void escribirServoY(uint32_t duty) {
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_SERVO_Y, duty);
#else
  ledcWrite(CANAL_SERVO_Y, duty);
#endif
}

inline uint32_t coordToDutyX(float coord) {
  float c = constrain(coord, 0.0f, 100.0f);
  float us = US_MIN_X + (c / 100.0f) * (US_MAX_X - US_MIN_X);
  float duty = (us / 20000.0f) * 65535.0f;
  return (uint32_t)roundf(duty);
}

inline uint32_t coordToDutyY(float coord) {
  float c = constrain(coord, 0.0f, 100.0f);
  float us = US_MIN_Y + (c / 100.0f) * (US_MAX_Y - US_MIN_Y);
  float duty = (us / 20000.0f) * 65535.0f;
  return (uint32_t)roundf(duty);
}

inline uint32_t coordToDuty(float coord) {
  return coordToDutyX(coord);
}

void setLaser(bool encender) {
  digitalWrite(PIN_LASER, encender ? HIGH : LOW);
}

void aplicarPosicion(float x, float y) {
  uint32_t dutyX = coordToDutyX(x);
  uint32_t dutyY = coordToDutyY(y);
  if (dutyX != ultimoDutyX) {
    escribirServoX(dutyX);
    ultimoDutyX = dutyX;
  }
  if (dutyY != ultimoDutyY) {
    escribirServoY(dutyY);
    ultimoDutyY = dutyY;
  }
}

// PERFIL DE MOVIMIENTO EN CURVA S (S-CURVE / SMOOTHSTEP)
// f(t) = 3*t^2 - 2*t^3  (Cubic S-Curve / Jerk-limited motion)
inline float curvaS(float t) {
  if (t <= 0.0f) return 0.0f;
  if (t >= 1.0f) return 1.0f;
  return t * t * (3.0f - 2.0f * t);
}


// MOTOR DE INTERPOLACIÓN CONTINUA EN TIEMPO REAL

void actualizarInterpolador() {
  unsigned long ahora = millis();

  if (enMovimiento) {
    unsigned long transcurrido = ahora - segInicioTiempo;

    if (transcurrido < segDuracion && segDuracion > 0) {
      float t = (float)transcurrido / (float)segDuracion;
      // Para segmentos continuos de alta densidad (<= 150ms), interpolación lineal
      // pura para mantener velocidad constante y evitar estancamiento en curvas discretizadas.
      // Para tramos largos (> 150ms, ej. traslados), usar curva S para arranque/parada suave.
      float s = (segDuracion <= 150) ? t : curvaS(t); 
      posX_actual = segInicioX + (segDestinoX - segInicioX) * s;
      posY_actual = segInicioY + (segDestinoY - segInicioY) * s;
    } else {
      posX_actual = segDestinoX;
      posY_actual = segDestinoY;
      enMovimiento = false;
    }

    aplicarPosicion(posX_actual, posY_actual);
  }

  // Si el tramo terminó y hay puntos en cola, pasar al siguiente instantáneamente
  if (!enMovimiento && colaCount > 0) {
    Waypoint siguiente;
    if (desencolarWaypoint(siguiente)) {
      segInicioX = posX_actual;
      segInicioY = posY_actual;
      segDestinoX = siguiente.x;
      segDestinoY = siguiente.y;
      segDuracion = siguiente.duracion_ms;
      segInicioTiempo = millis();
      enMovimiento = true;

      // Control del láser sincronizado con el tramo
      if (siguiente.estado_laser == 1) {
        setLaser(true);
      } else if (siguiente.estado_laser == 0) {
        setLaser(false);
      }

      aplicarPosicion(posX_actual, posY_actual);
    }
  }
}

// =========================================================
// PROCESADOR DE COMANDOS
// =========================================================
void procesarComando(char* cmd) {
  while (*cmd == ' ' || *cmd == '\t') cmd++;
  int len = strlen(cmd);
  while (len > 0 && (cmd[len - 1] == ' ' || cmd[len - 1] == '\t' || cmd[len - 1] == '\r' || cmd[len - 1] == '\n')) {
    cmd[--len] = '\0';
  }
  if (len == 0) return;

  // 1. MODO MANUAL: "X,Y" (Ej: "46,42" o "50.5,37.0")
  char* endptr1 = NULL;
  float x_dir = strtof(cmd, &endptr1);
  if (endptr1 != cmd) {
    while (*endptr1 == ' ') endptr1++;
    if (*endptr1 == ',') {
      char* ptr2 = endptr1 + 1;
      while (*ptr2 == ' ') ptr2++;
      char* endptr2 = NULL;
      float y_dir = strtof(ptr2, &endptr2);
      if (endptr2 != ptr2) {
        while (*endptr2 == ' ') endptr2++;
        if (*endptr2 == '\0') {
          limpiarCola();
          enMovimiento = false;
          posX_actual = x_dir;
          posY_actual = y_dir;
          segInicioX = x_dir; segInicioY = y_dir;
          segDestinoX = x_dir; segDestinoY = y_dir;
          aplicarPosicion(x_dir, y_dir);

          Serial.print("[Manual] Moviendo a X=");
          Serial.print(x_dir, 2);
          Serial.print(", Y=");
          Serial.println(y_dir, 2);
          Serial.println("OK");
          return;
        }
      }
    }
  }

  // 2. MODO TRAZADO: "P <x>,<y>,<duracion_ms>,<laser>"
  if (cmd[0] == 'P' && (cmd[1] == ' ' || cmd[1] == ':')) {
    char* ptr = cmd + 2;
    char* endptr = NULL;

    float x = strtof(ptr, &endptr);
    if (endptr == ptr || *endptr != ',') {
      Serial.println("ERR_PARSE_X");
      return;
    }
    ptr = endptr + 1;

    float y = strtof(ptr, &endptr);
    if (endptr == ptr || *endptr != ',') {
      Serial.println("ERR_PARSE_Y");
      return;
    }
    ptr = endptr + 1;

    unsigned long dur = strtoul(ptr, &endptr, 10);
    if (endptr == ptr) {
      Serial.println("ERR_PARSE_DUR");
      return;
    }

    int laser = 2;
    if (*endptr == ',') {
      ptr = endptr + 1;
      laser = (int)strtol(ptr, &endptr, 10);
    }

    // Si está abortado, rechazar inmediatamente sin encolar
    if (abortado) {
      Serial.println("ERR_ABORT");
      return;
    }

    // Esperar espacio en la cola si está llena
    while (colaCount >= BUFFER_SIZE) {
      if (abortado) {
        Serial.println("ERR_ABORT");
        return;
      }
      leerSerial();
      actualizarInterpolador();
      delay(1);
    }

    // Verificar de nuevo tras la espera (CLEAR pudo llegar durante el busy-wait)
    if (abortado) {
      Serial.println("ERR_ABORT");
      return;
    }

    encolarWaypoint(x, y, dur, (uint8_t)laser);
    Serial.println("OK");
  }
  // 3. COMANDOS DIRECTOS DE LÁSER
  else if (strcmp(cmd, "LASER_ON") == 0 || strcmp(cmd, "1") == 0) {
    setLaser(true);
    Serial.println("Laser encendido en GPIO 23");
    Serial.println("OK");
  }
  else if (strcmp(cmd, "LASER_OFF") == 0 || strcmp(cmd, "0") == 0) {
    setLaser(false);
    Serial.println("Laser apagado");
    Serial.println("OK");
  }
  else if (strcmp(cmd, "TEST_LASER") == 0) {
    Serial.println("Probando laser por 1 segundo...");
    setLaser(true);
    delay(1000);
    setLaser(false);
    Serial.println("OK");
  }
  // 4. POSICIONAMIENTO Y CONTROL
  else if (strcmp(cmd, "CENTER") == 0 || strcmp(cmd, "HOME") == 0) {
    limpiarCola();
    enMovimiento = false;
    posX_actual = CENTRO_MAQUETA_X;
    posY_actual = CENTRO_MAQUETA_Y;
    segInicioX = CENTRO_MAQUETA_X; segInicioY = CENTRO_MAQUETA_Y;
    segDestinoX = CENTRO_MAQUETA_X; segDestinoY = CENTRO_MAQUETA_Y;
    aplicarPosicion(CENTRO_MAQUETA_X, CENTRO_MAQUETA_Y);
    Serial.print("Regresado al centro: (");
    Serial.print(CENTRO_MAQUETA_X);
    Serial.print(", ");
    Serial.print(CENTRO_MAQUETA_Y);
    Serial.println(")");
    Serial.println("OK");
  }
  else if (strcmp(cmd, "WAIT") == 0) {
    while (!abortado && (enMovimiento || colaCount > 0)) {
      leerSerial();
      actualizarInterpolador();
      delay(1);
    }
    aplicarPosicion(posX_actual, posY_actual);
    Serial.println("OK");
  }
  else if (strcmp(cmd, "CLEAR") == 0) {
    abortado = true;
    limpiarCola();
    enMovimiento = false;
    setLaser(false);
    Serial.println("Cola vaciada y laser apagado");
    Serial.println("OK");
  }
  else if (strcmp(cmd, "RESUME") == 0) {
    abortado = false;
    Serial.println("Abort flag cleared, ready for new commands");
    Serial.println("OK");
  }
  else if (strcmp(cmd, "PING") == 0 || strcmp(cmd, "STATUS") == 0) {
    Serial.print("Posicion actual: X=");
    Serial.print(posX_actual);
    Serial.print(", Y=");
    Serial.print(posY_actual);
    Serial.print(" | Cola: ");
    Serial.print(colaCount);
    Serial.print(" | EnMovimiento: ");
    Serial.println(enMovimiento ? "SI" : "NO");
    Serial.println("OK");
  }
  else {
    Serial.print("Comando desconocido: ");
    Serial.println(cmd);
    Serial.println("ERR_CMD");
  }
}

void leerSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    if (c == '\n' || c == '\r') {
      if (indiceBuffer > 0) {
        bufferSerie[indiceBuffer] = '\0';
        procesarComando(bufferSerie);
        indiceBuffer = 0;
      }
    } else if (indiceBuffer < (int)sizeof(bufferSerie) - 1) {
      bufferSerie[indiceBuffer++] = c;
    }
  }
}

// =========================================================
// SETUP & LOOP
// =========================================================
void setup() {
  Serial.begin(115200);
  setupPWM();

  delay(50);
  setLaser(false);

  posX_actual = CENTRO_MAQUETA_X;
  posY_actual = CENTRO_MAQUETA_Y;
  segInicioX = CENTRO_MAQUETA_X;
  segInicioY = CENTRO_MAQUETA_Y;
  segDestinoX = CENTRO_MAQUETA_X;
  segDestinoY = CENTRO_MAQUETA_Y;

  aplicarPosicion(CENTRO_MAQUETA_X, CENTRO_MAQUETA_Y);

  Serial.println("\n[ESP32 Direct PWM 16-bit] Firmware listo.");
  Serial.println("Servos en GPIO 18 (X) y GPIO 19 (Y). Laser en GPIO 23.");
}

void loop() {
  leerSerial();
  actualizarInterpolador();
}
