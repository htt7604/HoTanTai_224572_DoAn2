#include <Servo.h>

/* ========== SERVO & PIN ========== */
// Theo sơ đồ nối dây ESP8266 (So_do_noi_day_ESP32_ESP8266_CHUAN_CUOI.docx):
// Servo cửa → D2 (GPIO4) | 150° đóng – 80° mở
// Servo mái che → D4 (GPIO2) | 0° đóng – 120° mở
// Quạt (relay) → D1 (GPIO5)
#define DOOR_SERVO_PIN 4   // D2 (GPIO4) - Servo cửa
#define ROOF_SERVO_PIN 2   // D4 (GPIO2) - Servo mái che/rèm
#define FAN_PIN        5   // D1 (GPIO5) - Quạt relay

/* ========== PIN ĐÈN ========== */
// Theo sơ đồ nối dây ESP8266:
// Đèn 1 → D5 (GPIO14)
// Đèn 2 → D6 (GPIO12)
// Đèn 3 → D7 (GPIO13)
// Đèn 4 → D8 (GPIO15) - Có thể thêm nếu cần
#define LIGHT1_PIN     14  // D5 (GPIO14)
#define LIGHT2_PIN     12  // D6 (GPIO12)
#define LIGHT3_PIN     13  // D7 (GPIO13)
// #define LIGHT4_PIN     15  // D8 (GPIO15) - Chưa sử dụng

/* ========== GÓC SERVO CHUẨN ========== */
#define DOOR_CLOSE_ANGLE 150 
#define DOOR_OPEN_ANGLE  80  
#define ROOF_CLOSE_ANGLE 0   
#define ROOF_OPEN_ANGLE  120 

Servo doorServo;
Servo roofServo;

String command = "";

/* ========== TRẠNG THÁI ========== */
bool doorState = false;
bool roofState = false;
bool fanState = false;
bool light1State = false;
bool light2State = false;
bool light3State = false;

/* ========== SETUP ========== */
void setup() {
  Serial.begin(9600); // Tốc độ UART đồng bộ với ESP32

  // Khởi tạo Servo
  doorServo.attach(DOOR_SERVO_PIN);
  roofServo.attach(ROOF_SERVO_PIN);

  // Khởi tạo các chân OUTPUT
  pinMode(FAN_PIN, OUTPUT);
  pinMode(LIGHT1_PIN, OUTPUT);
  pinMode(LIGHT2_PIN, OUTPUT);
  pinMode(LIGHT3_PIN, OUTPUT);

  // Trạng thái ban đầu - TẤT CẢ TẮT
  digitalWrite(FAN_PIN, LOW);
  digitalWrite(LIGHT1_PIN, LOW);
  digitalWrite(LIGHT2_PIN, LOW);
  digitalWrite(LIGHT3_PIN, LOW);
  
  doorServo.write(DOOR_CLOSE_ANGLE);
  roofServo.write(ROOF_CLOSE_ANGLE);
  
  doorState = false;
  roofState = false;
  fanState = false;
  light1State = false;
  light2State = false;
  light3State = false;

  delay(500);
  
  Serial.println("ESP8266 initialized!");
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
  Serial.print("Received command: ");
  Serial.println(cmd);
  
  // ===== CỬA =====
  if (cmd == "DOOR_OPEN") {
    doorServo.write(DOOR_OPEN_ANGLE);
    doorState = true;
    Serial.println("Door: OPENED");
    delay(500);
  }
  else if (cmd == "DOOR_CLOSE") {
    doorServo.write(DOOR_CLOSE_ANGLE);
    doorState = false;
    Serial.println("Door: CLOSED");
    delay(500);
  }
  
  // ===== MÁI CHE / RÈM - Đóng khi mưa =====
  else if (cmd == "ROOF_OPEN") {
    roofServo.write(ROOF_OPEN_ANGLE);
    roofState = true;
    Serial.println("Roof: OPENED");
    delay(500);
  }
  else if (cmd == "ROOF_CLOSE") {
    roofServo.write(ROOF_CLOSE_ANGLE);
    roofState = false;
    Serial.println("Roof: CLOSED");
    delay(500);
  }
  
  // ===== QUẠT - Bật khi có gas =====
  else if (cmd == "FAN_ON") {
    digitalWrite(FAN_PIN, HIGH);
    fanState = true;
    Serial.println("Fan: ON");
  }
  else if (cmd == "FAN_OFF") {
    digitalWrite(FAN_PIN, LOW);
    fanState = false;
    Serial.println("Fan: OFF");
  }
  
  // ===== ĐÈN 1 =====
  else if (cmd == "LIGHT1_ON") {
    digitalWrite(LIGHT1_PIN, HIGH);
    light1State = true;
    Serial.println("Light1: ON");
  }
  else if (cmd == "LIGHT1_OFF") {
    digitalWrite(LIGHT1_PIN, LOW);
    light1State = false;
    Serial.println("Light1: OFF");
  }
  
  // ===== ĐÈN 2 =====
  else if (cmd == "LIGHT2_ON") {
    digitalWrite(LIGHT2_PIN, HIGH);
    light2State = true;
    Serial.println("Light2: ON");
  }
  else if (cmd == "LIGHT2_OFF") {
    digitalWrite(LIGHT2_PIN, LOW);
    light2State = false;
    Serial.println("Light2: OFF");
  }
  
  // ===== ĐÈN 3 =====
  else if (cmd == "LIGHT3_ON") {
    digitalWrite(LIGHT3_PIN, HIGH);
    light3State = true;
    Serial.println("Light3: ON");
  }
  else if (cmd == "LIGHT3_OFF") {
    digitalWrite(LIGHT3_PIN, LOW);
    light3State = false;
    Serial.println("Light3: OFF");
  }
  
  // ===== LỆNH KHÔNG HỢP LỆ =====
  else {
    Serial.print("Unknown command: ");
    Serial.println(cmd);
  }
}
