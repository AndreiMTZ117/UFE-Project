; Test G-code para Thorlabs GVS112/M
; Generado para validación de LectorGcode y GeneradorMatrizTemporal
G21 ; Unidades en mm
G90 ; Coordenadas absolutas
M5  ; Láser apagado

; Viaje al punto de inicio (esquina inferior izquierda)
G0 X-10.0 Y-10.0 F12000

; Iniciar corte cuadrado de 20x20 mm
M3 S255 ; Láser ON potencia 100%
G1 X10.0 Y-10.0 F600
G1 X10.0 Y10.0 F600
G1 X-10.0 Y10.0 F600
G1 X-10.0 Y-10.0 F600
M5 ; Láser OFF

; Viaje al centro
G0 X0.0 Y0.0 F12000
M3 S128 ; Láser ON potencia 50%
G1 X0.0 Y5.0 F400
G1 X5.0 Y0.0 F400
G1 X0.0 Y-5.0 F400
G1 X-5.0 Y0.0 F400
G1 X0.0 Y5.0 F400
M5 ; Láser OFF

; Retorno a reposo
G0 X0.0 Y0.0 F12000
M2 ; Fin de programa
