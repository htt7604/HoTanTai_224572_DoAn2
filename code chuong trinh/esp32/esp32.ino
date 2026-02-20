#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <MFRC522.h>
#include <SPI.h>
#include <I2CKeyPad.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ================= CẤU HÌNH WIFI =================
const char* ssid = "Thuong";
const char* password = "12345678";

// ================= CẤU HÌNH MQTT =================
const char* mqtt_server = "192.168.1.6";  // Thay bằng IP LAN của máy tính
const int mqtt_port = 1883;
const char* mqtt_topic_sensor = "esp32/sensor";
const char* mqtt_topic_control = "esp32/control";
const char* mqtt_client_id = "ESP32_SmartHome";

// ================= MQTT CLIENT =================
WiFiClient espClient;
PubSubClient client(espClient);

// ================= KHAI BÁO PIN =================
#define GAS_PIN    34 
#define RAIN_PIN   35 
#define FLAME_PIN  27 
#define BUZZER_PIN 15 
#define PIR_PIN    17   // PIR

#define SS_PIN     5
#define RST_PIN    4
MFRC522 rfid(SS_PIN, RST_PIN);

// ===== DHT11 =====
#define DHTPIN   25
#define DHTTYPE  DHT11
DHT dht(DHTPIN, DHTTYPE);

// ================= I2C =================
LiquidCrystal_I2C lcd(0x27, 16, 2);
I2CKeyPad keypad(0x20, &Wire1); 

// ================= MẬT KHẨU =================
const String PASSWORD = "123456A";
String inputPassword = "";
bool isEnteringPassword = false;
unsigned long lastKeyTime = 0;
const unsigned long PASSWORD_TIMEOUT = 10000; // 10 giây timeout

// ================= BIẾN TRẠNG THÁI =================
bool isDoorOpen = false;
bool lastRainState = false;
bool lastPirState = false;
bool lastGasState = false;
bool fanRunning = false;
bool light1State = false;
bool light2State = false;
bool light3State = false;

byte lastTouchData = 0xFF;

unsigned long lastFireMsg = 0;
unsigned long lastLcdUpdate = 0;
unsigned long lastGasCheck = 0;
unsigned long lastSensorPublish = 0;
const unsigned long SENSOR_PUBLISH_INTERVAL = 2000; // 2 giây

// ===== BIẾN DHT11 =====
float dhtTemp = NAN;
float dhtHum  = NAN;
unsigned long lastDhtRead = 0;

// ===== BIẾN HIỂN THỊ LCD =====
int displayPage = 0;
unsigned long lastPageChange = 0;
const unsigned long PAGE_CHANGE_INTERVAL = 5000; // Đổi trang mỗi 5 giây

// ================= WIFI & MQTT FUNCTIONS =================

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Connecting WiFi");
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    lcd.setCursor(attempts % 16, 1);
    lcd.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("");
    Serial.println("WiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("WiFi Connected!");
    lcd.setCursor(0, 1);
    lcd.print(WiFi.localIP());
    delay(2000);
  } else {
    Serial.println("WiFi connection failed!");
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("WiFi FAILED!");
    delay(2000);
  }
}

void reconnectMQTT() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Connecting MQTT");
    
    if (client.connect(mqtt_client_id)) {
      Serial.println("connected!");
      client.subscribe(mqtt_topic_control);
      Serial.println("Subscribed to: esp32/control");
      
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("MQTT Connected!");
      delay(2000);
      lcd.clear();
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("MQTT Failed!");
      lcd.setCursor(0, 1);
      lcd.print("Retry in 5s...");
      delay(5000);
    }
  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  // Loại bỏ ký tự xuống dòng và khoảng trắng
  message.trim();
  
  Serial.print("Message received [");
  Serial.print(topic);
  Serial.print("]: ");
  Serial.println(message);
  
  // Gửi lệnh cho ESP8266 qua Serial2 để thực hiện
  // Xử lý các lệnh từ server
  if (message == "DOOR_OPEN") {
    isDoorOpen = true;
    Serial2.println("DOOR_OPEN");  // Gửi cho ESP8266
    Serial.println("Command: DOOR_OPEN -> ESP8266");
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("DOOR: OPENED");
    delay(1000);
    lcd.clear();
  }
  else if (message == "DOOR_CLOSE") {
    isDoorOpen = false;
    Serial2.println("DOOR_CLOSE");  // Gửi cho ESP8266
    Serial.println("Command: DOOR_CLOSE -> ESP8266");
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("DOOR: CLOSED");
    delay(1000);
    lcd.clear();
  }
  else if (message == "LIGHT1_ON") {
    light1State = true;
    Serial2.println("LIGHT1_ON");  // Gửi cho ESP8266
    Serial.println("Command: LIGHT1_ON -> ESP8266");
  }
  else if (message == "LIGHT1_OFF") {
    light1State = false;
    Serial2.println("LIGHT1_OFF");  // Gửi cho ESP8266
    Serial.println("Command: LIGHT1_OFF -> ESP8266");
  }
  else if (message == "LIGHT2_ON") {
    light2State = true;
    Serial2.println("LIGHT2_ON");  // Gửi cho ESP8266
    Serial.println("Command: LIGHT2_ON -> ESP8266");
  }
  else if (message == "LIGHT2_OFF") {
    light2State = false;
    Serial2.println("LIGHT2_OFF");  // Gửi cho ESP8266
    Serial.println("Command: LIGHT2_OFF -> ESP8266");
  }
  else if (message == "LIGHT3_ON") {
    light3State = true;
    Serial2.println("LIGHT3_ON");  // Gửi cho ESP8266
    Serial.println("Command: LIGHT3_ON -> ESP8266");
  }
  else if (message == "LIGHT3_OFF") {
    light3State = false;
    Serial2.println("LIGHT3_OFF");  // Gửi cho ESP8266
    Serial.println("Command: LIGHT3_OFF -> ESP8266");
  }
  else if (message == "FAN_ON") {
    fanRunning = true;
    Serial2.println("FAN_ON");  // Gửi cho ESP8266
    Serial.println("Command: FAN_ON -> ESP8266");
  }
  else if (message == "FAN_OFF") {
    fanRunning = false;
    Serial2.println("FAN_OFF");  // Gửi cho ESP8266
    Serial.println("Command: FAN_OFF -> ESP8266");
  }
  else if (message == "ROOF_OPEN") {
    Serial2.println("ROOF_OPEN");  // Gửi cho ESP8266
    Serial.println("Command: ROOF_OPEN -> ESP8266");
  }
  else if (message == "ROOF_CLOSE") {
    Serial2.println("ROOF_CLOSE");  // Gửi cho ESP8266
    Serial.println("Command: ROOF_CLOSE -> ESP8266");
  }
  else {
    Serial.print("Unknown command: ");
    Serial.println(message);
  }
}

// Hàm gửi lệnh cho ESP8266 qua Serial2 (thay thế Serial2.println cũ)
void sendToESP8266(const char* command) {
  Serial2.println(command);  // Gửi cho ESP8266 để thực hiện
  Serial.print("Sent to ESP8266: ");
  Serial.println(command);
}

void publishSensorData() {
  if (!client.connected()) {
    return;
  }
  
  // Đọc cảm biến
  bool isRaining = (digitalRead(RAIN_PIN) == LOW);
  bool pirDetected = digitalRead(PIR_PIN);
  bool isFire = (digitalRead(FLAME_PIN) == LOW);
  int gasValue = analogRead(GAS_PIN);
  
  // Tạo JSON
  StaticJsonDocument<256> doc;
  doc["temp"] = isnan(dhtTemp) ? 0.0 : dhtTemp;
  doc["hum"] = isnan(dhtHum) ? 0.0 : dhtHum;
  doc["gas"] = gasValue;
  doc["rain"] = isRaining;
  doc["flame"] = isFire;
  doc["pir"] = pirDetected;
  doc["door"] = isDoorOpen;
  doc["light1"] = light1State;
  doc["light2"] = light2State;
  doc["light3"] = light3State;
  
  char jsonBuffer[256];
  serializeJson(doc, jsonBuffer);
  
  client.publish(mqtt_topic_sensor, jsonBuffer);
  Serial.print("Published sensor data: ");
  Serial.println(jsonBuffer);
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, 13, 14);  // Giao tiếp với ESP8266

  Wire.begin(32, 33);
  lcd.init();
  lcd.backlight();

  Wire1.begin(21, 22);
  keypad.begin();

  Wire1.beginTransmission(0x21);
  Wire1.write(0xFF);
  Wire1.endTransmission();

  dht.begin();

  pinMode(RAIN_PIN, INPUT);
  pinMode(FLAME_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(PIR_PIN, INPUT);

  SPI.begin();
  rfid.PCD_Init();

  lcd.setCursor(0, 0);
  lcd.print(" SMART HOME v1.0");
  lcd.setCursor(0, 1);
  lcd.print("  Initializing...");
  delay(2000);
  lcd.clear();

  // Kết nối WiFi
  connectWiFi();
  
  // Cấu hình MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  
  // Kết nối MQTT
  reconnectMQTT();
}

void loop() {
  // Kiểm tra và reconnect MQTT nếu cần
  if (!client.connected()) {
    reconnectMQTT();
  }
  client.loop();

  // Kiểm tra WiFi
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  // ===== ĐỌC DHT11 (>= 2 GIÂY / LẦN) =====
  if (millis() - lastDhtRead >= 2000) {
    dhtTemp = dht.readTemperature();
    dhtHum  = dht.readHumidity();
    lastDhtRead = millis();

    if (isnan(dhtTemp) || isnan(dhtHum)) {
      Serial.println("Loi: Khong doc duoc DHT11");
    }
  }

  // ===== PUBLISH SENSOR DATA MỖI 2 GIÂY =====
  if (millis() - lastSensorPublish >= SENSOR_PUBLISH_INTERVAL) {
    publishSensorData();
    lastSensorPublish = millis();
  }

  // ===== ĐỌC CẢM BIẾN KHÁC =====
  bool isRaining   = (digitalRead(RAIN_PIN) == LOW);
  bool pirDetected = digitalRead(PIR_PIN);
  bool isFire      = (digitalRead(FLAME_PIN) == LOW);
  int  gasValue    = analogRead(GAS_PIN);
  bool gasDetected = (gasValue > 400);

  // ===== XỬ LÝ MƯA - ĐÓNG RÈM =====
  if (isRaining != lastRainState) {
    if (isRaining) {
      sendToESP8266("ROOF_CLOSE");
      Serial.println("Mua phat hien - Dong rem");
    } else {
      sendToESP8266("ROOF_OPEN");
      Serial.println("Het mua - Mo rem");
    }
    lastRainState = isRaining;
  }

  // ===== XỬ LÝ GAS - CHẠY QUẠT + BUZZER =====
  if (gasDetected != lastGasState) {
    if (gasDetected) {
      sendToESP8266("FAN_ON");
      fanRunning = true;
      Serial.println("Gas phat hien - Bat quat + Buzzer");
    } else {
      sendToESP8266("FAN_OFF");
      fanRunning = false;
      Serial.println("Gas binh thuong - Tat quat");
    }
    lastGasState = gasDetected;
    lastGasCheck = millis();
  }

  // Kiểm tra gas liên tục khi đang phát hiện
  if (gasDetected && (millis() - lastGasCheck >= 1000)) {
    sendToESP8266("FAN_ON"); // Đảm bảo quạt vẫn chạy
    lastGasCheck = millis();
  }

  // ===== BUZZER =====
  if (isFire) {
    digitalWrite(BUZZER_PIN, HIGH);
    if (millis() - lastFireMsg > 3000) {
      sendToESP8266("FIRE_ALARM");
      lastFireMsg = millis();
    }
  }
  else if (gasDetected || pirDetected) {
    digitalWrite(BUZZER_PIN, HIGH);
  }
  else {
    digitalWrite(BUZZER_PIN, LOW);
  }

  // ===== PIR =====
  if (pirDetected != lastPirState) {
    sendToESP8266(pirDetected ? "HUMAN_DETECTED" : "HUMAN_LEFT");
    lastPirState = pirDetected;
  }

  // ===== LCD HIỂN THỊ CHUYÊN NGHIỆP =====
  if (millis() - lastLcdUpdate >= 500) {
    displayLCD();
    lastLcdUpdate = millis();
  }

  // ===== RFID - TỰ ĐỘNG MỞ CỬA =====
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    isDoorOpen = !isDoorOpen;
    sendToESP8266(isDoorOpen ? "DOOR_OPEN" : "DOOR_CLOSE");
    
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("RFID DETECTED");
    lcd.setCursor(0, 1);
    lcd.print(isDoorOpen ? "DOOR: OPENED" : "DOOR: CLOSED");
    delay(2000);
    lcd.clear();
    
    rfid.PICC_HaltA();
  }

  // ===== TOUCH =====
  Wire1.requestFrom(0x21, (uint8_t)1);
  if (Wire1.available()) {
    byte touchData = Wire1.read();
    if (touchData != lastTouchData) {

      if (!(touchData & 1) && (lastTouchData & 1)) {
        light1State = !light1State;
        sendToESP8266(light1State ? "LIGHT1_ON" : "LIGHT1_OFF");
      }
      if (!(touchData & 2) && (lastTouchData & 2)) {
        light2State = !light2State;
        sendToESP8266(light2State ? "LIGHT2_ON" : "LIGHT2_OFF");
      }
      if (!(touchData & 4) && (lastTouchData & 4)) {
        light3State = !light3State;
        sendToESP8266(light3State ? "LIGHT3_ON" : "LIGHT3_OFF");
      }

      lastTouchData = touchData;
    }
  }

  // ===== KEYPAD - MẬT KHẨU =====
  char key = keypad.getKey();
  if (key != 0) {
    handleKeypad(key);
  }

  // Timeout mật khẩu
  if (isEnteringPassword && (millis() - lastKeyTime > PASSWORD_TIMEOUT)) {
    isEnteringPassword = false;
    inputPassword = "";
    lcd.clear();
  }

  delay(20);
}

// ===== XỬ LÝ KEYPAD =====
void handleKeypad(char key) {
  lastKeyTime = millis();

  // Bắt đầu nhập mật khẩu khi nhấn phím đầu tiên
  if (!isEnteringPassword && key != 'A' && key != 'B' && key != 'C' && key != 'D') {
    isEnteringPassword = true;
    inputPassword = "";
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("ENTER PASSWORD:");
    lcd.setCursor(0, 1);
  }

  if (isEnteringPassword) {
    if (key == '*') {
      // Xóa ký tự cuối
      if (inputPassword.length() > 0) {
        inputPassword = inputPassword.substring(0, inputPassword.length() - 1);
        lcd.setCursor(inputPassword.length(), 1);
        lcd.print(" ");
        lcd.setCursor(inputPassword.length(), 1);
      }
    } else if (key == '#') {
      // Xác nhận mật khẩu
      if (inputPassword == PASSWORD) {
        isDoorOpen = !isDoorOpen;
        sendToESP8266(isDoorOpen ? "DOOR_OPEN" : "DOOR_CLOSE");
        
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("PASSWORD OK!");
        lcd.setCursor(0, 1);
        lcd.print(isDoorOpen ? "DOOR: OPENED" : "DOOR: CLOSED");
        delay(2000);
        lcd.clear();
      } else {
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("WRONG PASSWORD!");
        lcd.setCursor(0, 1);
        lcd.print("ACCESS DENIED");
        delay(2000);
        lcd.clear();
      }
      isEnteringPassword = false;
      inputPassword = "";
    } else if (key != 'A' && key != 'B' && key != 'C' && key != 'D') {
      // Thêm ký tự vào mật khẩu
      if (inputPassword.length() < 16) {
        inputPassword += key;
        lcd.setCursor(inputPassword.length() - 1, 1);
        lcd.print("*");
      }
    }
  }

  // Phím B - Tắt buzzer và quạt
  if (key == 'B') {
    digitalWrite(BUZZER_PIN, LOW);
    if (fanRunning) {
      sendToESP8266("FAN_OFF");
      fanRunning = false;
    }
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("ALARM RESET");
    delay(1000);
    lcd.clear();
  }
}

// ===== HIỂN THỊ LCD CHUYÊN NGHIỆP =====
void displayLCD() {
  // Đổi trang mỗi 5 giây
  if (millis() - lastPageChange >= PAGE_CHANGE_INTERVAL) {
    displayPage = (displayPage + 1) % 3;
    lastPageChange = millis();
    lcd.clear();
  }

  // Đọc cảm biến
  bool isRaining = (digitalRead(RAIN_PIN) == LOW);
  bool pirDetected = digitalRead(PIR_PIN);
  bool isFire = (digitalRead(FLAME_PIN) == LOW);
  int gasValue = analogRead(GAS_PIN);
  bool gasDetected = (gasValue > 400);

  switch (displayPage) {
    case 0: // Trang 1: Nhiệt độ & Độ ẩm
      lcd.setCursor(0, 0);
      lcd.print("T:");
      if (!isnan(dhtTemp)) {
        lcd.print(dhtTemp, 1);
      } else {
        lcd.print("--");
      }
      lcd.print("C H:");
      if (!isnan(dhtHum)) {
        lcd.print(dhtHum, 1);
      } else {
        lcd.print("--");
      }
      lcd.print("%");
      
      lcd.setCursor(0, 1);
      lcd.print("Gas:");
      lcd.print(gasValue);
      lcd.print(" Door:");
      lcd.print(isDoorOpen ? "OPEN" : "CLOSE");
      break;

    case 1: // Trang 2: Trạng thái cảm biến
      lcd.setCursor(0, 0);
      if (isFire) {
        lcd.print(">> FIRE ALERT! <<");
      } else if (gasDetected) {
        lcd.print(">> GAS DETECTED! ");
      } else if (pirDetected) {
        lcd.print("MOTION DETECTED ");
      } else {
        lcd.print("SYSTEM: NORMAL  ");
      }
      
      lcd.setCursor(0, 1);
      lcd.print("Rain:");
      lcd.print(isRaining ? "YES" : "NO ");
      lcd.print(" Fan:");
      lcd.print(fanRunning ? "ON " : "OFF");
      break;

    case 2: // Trang 3: Tổng quan
      lcd.setCursor(0, 0);
      lcd.print("SMART HOME v1.0");
      lcd.setCursor(0, 1);
      if (WiFi.status() == WL_CONNECTED && client.connected()) {
        lcd.print("WiFi+MQTT: OK");
      } else if (WiFi.status() == WL_CONNECTED) {
        lcd.print("WiFi: OK MQTT:--");
      } else {
        lcd.print("WiFi: -- MQTT:--");
      }
      if (isFire || gasDetected) {
        lcd.setCursor(0, 1);
        lcd.print("WARNING ACTIVE!");
      }
      break;
  }
}
