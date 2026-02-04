#include <Servo.h>

/* ========== SERVO & PIN ========== */
// Theo sơ đồ: Servo cửa D2 (GPIO4), Servo mái D4 (GPIO2), Quạt D1 (GPIO5)
#define DOOR_SERVO_PIN 4   // D2 
#define ROOF_SERVO_PIN 2   // D4 
#define FAN_PIN        5   // D1

/* ========== GÓC SERVO CHUẨN ========== */
#define DOOR_CLOSE_ANGLE 150 
#define DOOR_OPEN_ANGLE  80  
#define ROOF_CLOSE_ANGLE 0   
#define ROOF_OPEN_ANGLE  120 

Servo doorServo;
Servo roofServo;

String command = "";

/* ========== SETUP ========== */
void setup() {
  Serial.begin(9600); // Tốc độ UART đồng bộ với ESP32

  doorServo.attach(DOOR_SERVO_PIN);
  roofServo.attach(ROOF_SERVO_PIN);

  pinMode(FAN_PIN, OUTPUT);
  digitalWrite(FAN_PIN, LOW);

  // Trạng thái ban đầu 
  doorServo.write(DOOR_CLOSE_ANGLE);
  roofServo.write(ROOF_CLOSE_ANGLE);
}

/* ========== LOOP ========== */
void loop() {
  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n') {
      command.trim();
      handleCommand(command);
      command = "";
    } else {
      command += c;
    }
  }
}

/* ========== XỬ LÝ LỆNH TỪ ESP32 ========== */
void handleCommand(String cmd) {
  // Cửa [cite: 65]
  if (cmd == "DOOR_OPEN") {
    doorServo.write(DOOR_OPEN_ANGLE);
  }
  else if (cmd == "DOOR_CLOSE") {
    doorServo.write(DOOR_CLOSE_ANGLE);
  }
  // Mái che [cite: 66]
  else if (cmd == "ROOF_OPEN") {
    roofServo.write(ROOF_OPEN_ANGLE);
  }
  else if (cmd == "ROOF_CLOSE") {
    roofServo.write(ROOF_CLOSE_ANGLE);
  }
  // Quạt [cite: 67]
  else if (cmd == "FAN_ON") {
    digitalWrite(FAN_PIN, HIGH);
  }
  else if (cmd == "FAN_OFF") {
    digitalWrite(FAN_PIN, LOW);
  }
}