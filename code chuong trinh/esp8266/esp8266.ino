#if __has_include(<ESP8266Servo.h>)
#include <ESP8266Servo.h>
#else
#include <Servo.h>
#endif
#include <Wire.h>

/* ========== SERVO & PIN ========== */
// Theo sơ đồ nối dây ESP8266 (So_do_noi_day_ESP32_ESP8266_CHUAN_CUOI.docx):
// Servo cửa → D2 (GPIO4) | 150° đóng – 80° mở
// Servo mái che → D7 (GPIO13) | 0° đóng – 120° mở
// Quạt (relay) → D1 (GPIO5)
#define DOOR_SERVO_PIN 4   // D2 (GPIO4) - Servo cửa
#define ROOF_SERVO_PIN 13  // D7 (GPIO13) - Servo mái che/rèm
#define FAN_PIN        5   // D1 (GPIO5) - Quạt relay

/* ========== PCF8574 (ĐÈN) ========== */
// Theo sơ đồ nối dây mới:
// ESP8266 -> PCF8574(3): SDA -> D6, SCL -> D5
// PCF8574(3) -> ULN2803A: P0->IN1, P1->IN2, P2->IN3, P3->IN4
// ULN2803A -> Đèn: OUT1->Đèn1, OUT2->Đèn2, OUT3->Đèn3, OUT4->Đèn4
#define I2C_SDA_PIN     12  // D6 (GPIO12)
#define I2C_SCL_PIN     14  // D5 (GPIO14)
#define PCF8574_ADDR 0x20

// ULN2803A thường kích mức HIGH ở chân IN (HIGH = đèn ON).
// Nếu phần cứng thực tế bị đảo mức, đổi thành 0.
#define ULN_ACTIVE_HIGH 1

/* ========== GÓC SERVO CHUẨN ========== */
#define DOOR_CLOSE_ANGLE 80 
#define DOOR_OPEN_ANGLE  150  
#define ROOF_CLOSE_ANGLE 120 
#define ROOF_OPEN_ANGLE  0 

Servo doorServo;
Servo roofServo;

String command = "";
const uint8_t COMMAND_MAX_LEN = 40;

/* ========== TRẠNG THÁI ========== */
bool doorState = false;
bool roofState = false;
bool fanState = false;
bool light1State = false;
bool light2State = false;
bool light3State = false;
bool light4State = false;

uint8_t pcfState = 0x00;
bool pcfFound = false;

bool updatePcfLights() {
  pcfState = 0x00;

  // Chỉ dùng 4 bit thấp P0..P3 theo đúng mapping relay:
  // Light1 -> 0x01, Light2 -> 0x02, Light3 -> 0x04, Light4 -> 0x08
  if (light1State) pcfState |= 0x01;
  if (light2State) pcfState |= 0x02;
  if (light3State) pcfState |= 0x04;
  if (light4State) pcfState |= 0x08;

  pcfState &= 0x0F; // đảm bảo chỉ ghi P0..P3

  Wire.beginTransmission(PCF8574_ADDR);
  Wire.write(pcfState);
  return (Wire.endTransmission() == 0);
}

/* ========== SETUP ========== */
void setup() {
  Serial.begin(9600); // Tốc độ UART đồng bộ với ESP32

  // Khởi tạo Servo
  doorServo.attach(DOOR_SERVO_PIN);
  roofServo.attach(ROOF_SERVO_PIN);

  // Khởi tạo các chân OUTPUT
  pinMode(FAN_PIN, OUTPUT);

  // Khởi tạo I2C cho PCF8574 điều khiển đèn
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.beginTransmission(PCF8574_ADDR);
  pcfFound = (Wire.endTransmission() == 0);

  // Trạng thái ban đầu - TẤT CẢ TẮT
  digitalWrite(FAN_PIN, LOW);
  
  doorServo.write(DOOR_CLOSE_ANGLE);
  roofServo.write(ROOF_CLOSE_ANGLE);
  
  doorState = false;
  roofState = false;
  fanState = false;
  light1State = false;
  light2State = false;
  light3State = false;
  light4State = false;

  if (!updatePcfLights()) {
    Serial.println("Warning: PCF8574 write failed in setup");
  }

  delay(500);
  
  Serial.println("ESP8266 initialized!");
  Serial.print("PCF8574 address: 0x");
  Serial.println(PCF8574_ADDR, HEX);
  Serial.print("PCF8574 found: ");
  Serial.println(pcfFound ? "YES" : "NO");
}

/* ========== LOOP ========== */
void loop() {
  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      command.trim();
      if (command.length() > 0) {
        handleCommand(command);
      }
      command = "";
    } else if (isPrintable(c)) {
      if (command.length() < COMMAND_MAX_LEN) {
        command += c;
      } else {
        command = "";
      }
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
    if (!light1State) {
      light1State = true;
      if (!updatePcfLights()) Serial.println("PCF write failed: LIGHT1_ON");
      Serial.println("Light1: ON");
    } else {
      Serial.println("Light1: ALREADY ON");
    }
  }
  else if (cmd == "LIGHT1_OFF") {
    if (light1State) {
      light1State = false;
      if (!updatePcfLights()) Serial.println("PCF write failed: LIGHT1_OFF");
      Serial.println("Light1: OFF");
    } else {
      Serial.println("Light1: ALREADY OFF");
    }
  }
  
  // ===== ĐÈN 2 =====
  else if (cmd == "LIGHT2_ON") {
    if (!light2State) {
      light2State = true;
      if (!updatePcfLights()) Serial.println("PCF write failed: LIGHT2_ON");
      Serial.println("Light2: ON");
    } else {
      Serial.println("Light2: ALREADY ON");
    }
  }
  else if (cmd == "LIGHT2_OFF") {
    if (light2State) {
      light2State = false;
      if (!updatePcfLights()) Serial.println("PCF write failed: LIGHT2_OFF");
      Serial.println("Light2: OFF");
    } else {
      Serial.println("Light2: ALREADY OFF");
    }
  }
  
  // ===== ĐÈN 3 =====
  else if (cmd == "LIGHT3_ON") {
    if (!light3State) {
      light3State = true;
      if (!updatePcfLights()) Serial.println("PCF write failed: LIGHT3_ON");
      Serial.println("Light3: ON");
    } else {
      Serial.println("Light3: ALREADY ON");
    }
  }
  else if (cmd == "LIGHT3_OFF") {
    if (light3State) {
      light3State = false;
      if (!updatePcfLights()) Serial.println("PCF write failed: LIGHT3_OFF");
      Serial.println("Light3: OFF");
    } else {
      Serial.println("Light3: ALREADY OFF");
    }
  }

  // ===== ĐÈN 4 =====
  else if (cmd == "LIGHT4_ON") {
    if (!light4State) {
      light4State = true;
      if (!updatePcfLights()) Serial.println("PCF write failed: LIGHT4_ON");
      Serial.println("Light4: ON");
    } else {
      Serial.println("Light4: ALREADY ON");
    }
  }
  else if (cmd == "LIGHT4_OFF") {
    if (light4State) {
      light4State = false;
      if (!updatePcfLights()) Serial.println("PCF write failed: LIGHT4_OFF");
      Serial.println("Light4: OFF");
    } else {
      Serial.println("Light4: ALREADY OFF");
    }
  }
  
  // ===== LỆNH KHÔNG HỢP LỆ =====
  else {
    Serial.print("Unknown command: ");
    Serial.println(cmd);
  }
}
