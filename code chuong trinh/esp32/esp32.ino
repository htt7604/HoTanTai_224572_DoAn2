#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <MFRC522.h>
#include <SPI.h>
// #include <I2CKeyPad.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "mbedtls/sha256.h"

// ================= CẤU HÌNH WIFI =================
const char* ssid = "P3.15";
const char* password = "namcanthoDNC";

// ================= CẤU HÌNH MQTT =================
const char* mqtt_server = "3c5308fe02794486932d547731382984.s1.eu.hivemq.cloud";
const int mqtt_port = 8883;
const char* mqtt_topic_sensor = "esp32/sensor";
const char* mqtt_topic_control = "esp32/control";
const char* mqtt_topic_events = "esp32/events";
const char* mqtt_topic_password = "esp32/password";
const char* mqtt_topic_password_result = "esp32/password/result";
const char* mqtt_client_id = "ESP32_SmartHome";
const char* mqtt_username = "esp32";
const char* mqtt_password = "Esp32123";

// CA certificate (Let's Encrypt ISRG Root X1) for HiveMQ Cloud TLS
const char* mqtt_root_ca = R"EOF(
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U
A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW
T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH
B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC
B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv
KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn
OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn
jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw
qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI
rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq
hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ
3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK
NFtY2PwByVS5uCbMiogziUwxw4wS1qoR+3zqDjj/6sB1TLHQ+7X9rJfF6dV5z5V1
0VvvXfPp8Mt3q4B0lXdwY6Dk4B8b4y8u+1Wr9m0d5Z8a1C+q+BDfQd9wM1s4bD1z
4k4D5Pm2doW1cU6X9P2YX3rT0X5ypTXD9V8pj7bFfR7tPPY0L0P1l35b0K3L1B8J
8zg7QK0wAoytgPpQ27r9N9BK4S7j/8nceT5EwD7z4luMHGQqt1hZb8INZZeQzgrI
cg3FDUb8PsG+MzbkBTaoLB7Q8V5aKyA6h6VsdqWQ4rQ6ONYWnxo7xG45LTNuXa0h
EK3y0tGQ5DA2rXfGcxph0Xo7yR3ZZ3YEMlV1N7Vv1o9scsZ/74H4g9P+q+8R3B0r
0pWQw7O0eR8NvfI5ZGBv1Vx4aF4Aqk/Na7GzQ4L8V5Wn2tDx3d5XQ8i8uCIpB4s=
-----END CERTIFICATE-----
)EOF";

// ================= MQTT CLIENT =================
WiFiClientSecure espClient;
PubSubClient client(espClient);

// ================= KHAI BÁO PIN =================
#define GAS_PIN 34
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
// I2CKeyPad keypad(0x20, &Wire1); 
#define KEYPAD_ADDR 0x20

char keypadMap[4][4] =
{
 {'1','2','3','A'},
 {'4','5','6','B'},
 {'7','8','9','C'},
 {'*','0','#','D'}
};

// ================= MẬT KHẨU =================
// const String PASSWORD = "123456A";
String inputPassword = "";
bool isEnteringPassword = false;
unsigned long lastKeyTime = 0;
unsigned long lastCharAddedTime = 0;  // Thời điểm nhập ký tự cuối (để hiển thị 300ms rồi đổi sang *)
const unsigned long PASSWORD_TIMEOUT = 10000; // 10 giây timeout
const unsigned long CHAR_DISPLAY_MS = 300;    // Hiển thị ký tự thật 300ms trước khi đổi thành *
bool waitingPasswordResult = false;

// ================= BIẾN TRẠNG THÁI =================
bool isDoorOpen = false;
bool lastRainState = false;
bool lastPirState = false;
bool lastGasState = false;
bool fanRunning = false;
bool light1State = false;
bool light2State = false;
bool light3State = false;
bool light4State = false;
bool passwordAuthSuccessPending = false;
unsigned long light4ManualOverrideUntil = 0;
const unsigned long LIGHT4_MANUAL_HOLD_MS = 30000;

// ===== LỌC TRUNG BÌNH CẢM BIẾN GAS =====
const int GAS_ALERT_THRESHOLD = 1200; // Ngưỡng tối thiểu tuyệt đối (ADC 0..4095)
const int GAS_ALERT_DELTA = 250;      // Độ lệch so với nền để coi là có gas
const int GAS_FILTER_SAMPLES = 10;
int gasSamples[GAS_FILTER_SAMPLES] = {0};
int gasSampleIndex = 0;
int gasSampleCount = 0;
long gasSampleSum = 0;
int gasAverageValue = 0;

unsigned long gasCalibStart = 0;
const unsigned long GAS_CALIBRATION_MS = 15000;
long gasCalibSum = 0;
int gasCalibCount = 0;
int gasBaseline = 0;
bool gasCalibrated = false;

byte lastTouchData = 0xFF;

unsigned long lastFireMsg = 0;
unsigned long lastLcdUpdate = 0;
unsigned long lastGasCheck = 0;
unsigned long lastSensorPublish = 0;
const unsigned long SENSOR_PUBLISH_INTERVAL = 2000; // 2 giây

// ===== CHỨC NĂNG BUZZER CẢNH BÁO =====
void shortBeep(unsigned int ms = 150) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(ms);
  digitalWrite(BUZZER_PIN, LOW);
}

// ===== LỌC TRUNG BÌNH CẢM BIẾN GAS =====
int updateGasAverage(int rawValue) {
  if (gasSampleCount < GAS_FILTER_SAMPLES) {
    gasSamples[gasSampleCount] = rawValue;
    gasSampleSum += rawValue;
    gasSampleCount++;
  } else {
    gasSampleSum -= gasSamples[gasSampleIndex];
    gasSamples[gasSampleIndex] = rawValue;
    gasSampleSum += rawValue;
    gasSampleIndex = (gasSampleIndex + 1) % GAS_FILTER_SAMPLES;
  }

  if (gasSampleCount > 0) {
    gasAverageValue = (int)(gasSampleSum / gasSampleCount);
  }
  return gasAverageValue;
}

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
    
    if (client.connect(mqtt_client_id, mqtt_username, mqtt_password)) {
      Serial.println("connected!");
      client.subscribe(mqtt_topic_control);
      client.subscribe(mqtt_topic_password_result);
      Serial.println("Subscribed to: esp32/control");
      Serial.println("Subscribed to: esp32/password/result");
      
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

// ===== BẮT ĐẦU CHỨC NĂNG HASH MẬT KHẨU =====
// ===== SỬA SHA256 CHO ESP32 =====
String sha256Hex(const String& text) {
  byte hash[32];
  mbedtls_sha256_context ctx;
  mbedtls_sha256_init(&ctx);
  mbedtls_sha256_starts(&ctx, 0);
  mbedtls_sha256_update(&ctx, (const unsigned char*)text.c_str(), text.length());
  mbedtls_sha256_finish(&ctx, hash);
  mbedtls_sha256_free(&ctx);

  char hex[65];
  for (int i = 0; i < 32; i++) {
    sprintf(&hex[i * 2], "%02x", hash[i]);
  }
  hex[64] = '\0';
  return String(hex);
}

void handlePasswordAuthResult(bool isOk) {
  waitingPasswordResult = false;

  if (isOk) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("MAT KHAU DUNG");
    lcd.setCursor(0, 1);
    lcd.print("CHO LENH SERVER");
    delay(2000);
    lcd.clear();

    isEnteringPassword = false;
    inputPassword = "";
    return;
  }

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("WRONG PASSWORD");
  lcd.setCursor(0, 1);
  lcd.print("THU LAI");
  digitalWrite(BUZZER_PIN, HIGH);
  delay(1000);
  digitalWrite(BUZZER_PIN, LOW);
  delay(1000);

  inputPassword = "";
  lastCharAddedTime = 0;
  lcd.clear();
  if (isEnteringPassword) {
    displayPasswordInput();
  }
}

void sendPasswordHashToServer(const String& rawPassword) {
  if (!client.connected()) {
    return;
  }

  String hashHex = sha256Hex(rawPassword);

  StaticJsonDocument<160> doc;
  doc["type"] = "password_check";
  doc["hash"] = hashHex;

  char jsonBuffer[160];
  serializeJson(doc, jsonBuffer);
  client.publish(mqtt_topic_password, jsonBuffer);

  waitingPasswordResult = true;
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("CHECKING...");

  Serial.print("Published password hash: ");
  Serial.println(hashHex);
}
// ===== KẾT THÚC CHỨC NĂNG HASH MẬT KHẨU =====

void callback(char* topic, byte* payload, unsigned int length) {
  String topicStr = String(topic);
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

  // ===== BẮT ĐẦU CHỨC NĂNG HASH MẬT KHẨU =====
  if (topicStr == mqtt_topic_password_result) {
    if (message == "OK") {
      passwordAuthSuccessPending = true;
      handlePasswordAuthResult(true);
    } else {
      passwordAuthSuccessPending = false;
      handlePasswordAuthResult(false);
    }
    return;
  }
  // ===== KẾT THÚC CHỨC NĂNG HASH MẬT KHẨU =====
  
  // Gửi lệnh cho ESP8266 qua Serial2 để thực hiện
  // Xử lý các lệnh từ server
  if (message == "DOOR_OPEN") {
    isDoorOpen = true;
    Serial2.println("DOOR_OPEN");  // Gửi cho ESP8266
    Serial.println("Command: DOOR_OPEN -> ESP8266");
    if (passwordAuthSuccessPending) {
      shortBeep();
      passwordAuthSuccessPending = false;
    }
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("DOOR: OPENED");
    delay(1000);
    lcd.clear();
  }
  else if (message == "DOOR_CLOSE") {
    isDoorOpen = false;
    passwordAuthSuccessPending = false;
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
  else if (message == "LIGHT4_ON") {
    light4State = true;
    light4ManualOverrideUntil = millis() + LIGHT4_MANUAL_HOLD_MS;
    Serial2.println("LIGHT4_ON");  // Gửi cho ESP8266
    Serial.println("Command: LIGHT4_ON -> ESP8266");
  }
  else if (message == "LIGHT4_OFF") {
    light4State = false;
    light4ManualOverrideUntil = millis() + LIGHT4_MANUAL_HOLD_MS;
    Serial2.println("LIGHT4_OFF");  // Gửi cho ESP8266
    Serial.println("Command: LIGHT4_OFF -> ESP8266");
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

// Gửi event lên server qua MQTT
void publishEvent(const char* eventName) {
  if (!client.connected()) return;
  StaticJsonDocument<128> doc;
  doc["event"] = eventName;
  char buf[128];
  serializeJson(doc, buf);
  client.publish(mqtt_topic_events, buf);
  Serial.print("Published event: ");
  Serial.println(eventName);
}

void publishSensorData() {
  if (!client.connected()) {
    return;
  }
  
  // Đọc cảm biến
  bool isRaining = (digitalRead(RAIN_PIN) == LOW);
  bool pirDetected = digitalRead(PIR_PIN);
  bool isFire = (digitalRead(FLAME_PIN) == LOW);
  int gasValue = gasAverageValue;
  
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
  doc["light4"] = light4State;
  doc["fan"] = fanRunning;
  
  char jsonBuffer[256];
  serializeJson(doc, jsonBuffer);
  
  client.publish(mqtt_topic_sensor, jsonBuffer);
  Serial.print("Published sensor data: ");
  Serial.println(jsonBuffer);
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, 13, 14);  // Giao tiếp với ESP8266

  analogReadResolution(12);
  analogSetPinAttenuation(GAS_PIN, ADC_11db);

  Wire.begin(32, 33);
  lcd.init();
  lcd.backlight();

  Wire1.begin(21, 22);
  // keypad.begin();

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
  // espClient.setCACert(mqtt_root_ca);
  espClient.setInsecure();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  
  // Kết nối MQTT
  reconnectMQTT();

  gasCalibStart = millis();
}
char readKeypad()
{
  for(int row=0; row<4; row++)
  {
    byte data = 0xFF;
    data &= ~(1 << row);

    Wire1.beginTransmission(KEYPAD_ADDR);
    Wire1.write(data);
    Wire1.endTransmission();

    delayMicroseconds(50);

    Wire1.requestFrom(KEYPAD_ADDR,1);

    if(Wire1.available())
    {
      byte colData = Wire1.read();

      for(int col=0; col<4; col++)
      {
        if(!(colData & (1 << (col+4))))
        {
          return keypadMap[row][col];
        }
      }
    }
  }

  return 0;
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

  // ===== ĐỌC CẢM BIẾN KHÁC =====
  bool isRaining   = (digitalRead(RAIN_PIN) == LOW);
  bool pirDetected = digitalRead(PIR_PIN);
  bool isFire      = (digitalRead(FLAME_PIN) == LOW);
  int  gasRawValue = analogRead(GAS_PIN);
  int  gasValue    = updateGasAverage(gasRawValue);
  if (!gasCalibrated) {
    gasCalibSum += gasValue;
    gasCalibCount++;
    if (millis() - gasCalibStart >= GAS_CALIBRATION_MS && gasCalibCount > 0) {
      gasBaseline = (int)(gasCalibSum / gasCalibCount);
      gasCalibrated = true;
      Serial.print("Gas baseline calibrated: ");
      Serial.println(gasBaseline);
    }
  }

  int gasDynamicThreshold = gasCalibrated ? max(GAS_ALERT_THRESHOLD, gasBaseline + GAS_ALERT_DELTA) : GAS_ALERT_THRESHOLD;

  // ===== GAS DETECTION VỚI HYSTERESIS =====
  // Bật khi gasValue > gasDynamicThreshold
  // Tắt khi gasValue < gasDynamicThreshold - 150
  bool gasDetected = lastGasState;
  if (gasCalibrated) {
    if (!lastGasState && gasValue > gasDynamicThreshold) {
      gasDetected = true;
    } else if (lastGasState && gasValue < (gasDynamicThreshold - 150)) {
      gasDetected = false;
    }
  } else {
    gasDetected = false;
  }

  // ===== PUBLISH SENSOR DATA MỖI 2 GIÂY =====
  // Đặt sau khi đã đọc/cập nhật gas để gửi giá trị mới nhất thay vì mẫu cũ.
  if (millis() - lastSensorPublish >= SENSOR_PUBLISH_INTERVAL) {
    publishSensorData();
    lastSensorPublish = millis();
  }

  // ===== XỬ LÝ MƯA - ĐÓNG RÈM TỰ ĐỘNG =====
  if (isRaining != lastRainState) {
    if (isRaining) {
      sendToESP8266("ROOF_CLOSE");
      publishEvent("ROOF_AUTO_CLOSE_RAIN");
      Serial.println("Mua phat hien - Dong rem");
    } else {
      sendToESP8266("ROOF_OPEN");
      publishEvent("ROOF_AUTO_OPEN");
      Serial.println("Het mua - Mo rem");
    }
    lastRainState = isRaining;
  }

  // ===== XỬ LÝ GAS - CHẠY QUẠT + BUZZER =====
  if (gasDetected != lastGasState) {
    if (gasDetected) {
      sendToESP8266("FAN_ON");
      fanRunning = true;
      publishEvent("GAS_DETECTED");
      Serial.println("Gas detected");
    } else {
      sendToESP8266("FAN_OFF");
      fanRunning = false;
      publishEvent("GAS_NORMAL");
      Serial.println("Gas normal");
    }
    lastGasState = gasDetected;
  }

  static unsigned long lastGasDebug = 0;
  if (millis() - lastGasDebug >= 500) {
    Serial.print("Gas value: ");
    Serial.print(gasRawValue);
    Serial.print(" | Avg: ");
    Serial.print(gasValue);
    Serial.print(" | Baseline: ");
    Serial.print(gasBaseline);
    Serial.print(" | Threshold: ");
    Serial.print(gasDynamicThreshold);
    Serial.print(" | Detected: ");
    Serial.println(gasDetected ? "YES" : "NO");
    lastGasDebug = millis();
  }

  // ===== CHỨC NĂNG BUZZER CẢNH BÁO =====
  if (isFire) {
    digitalWrite(BUZZER_PIN, HIGH);
    if (millis() - lastFireMsg > 3000) {
      sendToESP8266("FIRE_ALARM");
      publishEvent("BUZZER_ALARM");
      lastFireMsg = millis();
    }
  }
  else if (gasDetected) {
    digitalWrite(BUZZER_PIN, HIGH);
  }
  else {
    digitalWrite(BUZZER_PIN, LOW);
  }

  // ===== PIR - HUMAN DETECTED =====
  if (pirDetected != lastPirState) {
    sendToESP8266(pirDetected ? "HUMAN_DETECTED" : "HUMAN_LEFT");
    publishEvent(pirDetected ? "HUMAN_DETECTED" : "HUMAN_LEFT");

    // ===== TỰ ĐỘNG BẬT ĐÈN KHI PHÁT HIỆN NGƯỜI =====
    if (millis() > light4ManualOverrideUntil) {
      light4State = pirDetected;
      sendToESP8266(pirDetected ? "LIGHT4_ON" : "LIGHT4_OFF");
    }

    lastPirState = pirDetected;
  }

  // ===== LCD HIỂN THỊ CHUYÊN NGHIỆP =====
  unsigned long lcdInterval = isEnteringPassword ? 100 : 500;
  if (millis() - lastLcdUpdate >= lcdInterval) {
    displayLCD();
    lastLcdUpdate = millis();
  }

  // ===== RFID - TỰ ĐỘNG MỞ/ĐÓNG CỬA =====
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    isDoorOpen = !isDoorOpen;
    sendToESP8266(isDoorOpen ? "DOOR_OPEN" : "DOOR_CLOSE");
    publishEvent(isDoorOpen ? "RFID_OPEN" : "RFID_CLOSE");
    if (isDoorOpen) {
      shortBeep();
    }
    
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
  // char key = keypad.getKey();
  // if (key != 0) {
  //   handleKeypad(key);
  // }
  char key = readKeypad();
  if(key)
  {
    handleKeypad(key);
    delay(200); // chống dội phím
  }

  // Timeout mật khẩu
  if (isEnteringPassword && (millis() - lastKeyTime > PASSWORD_TIMEOUT)) {
    isEnteringPassword = false;
    inputPassword = "";
    lcd.clear();
  }

  delay(20);
}

// ===== HIỂN THỊ MÀN HÌNH NHẬP MẬT KHẨU (gọi từ displayLCD khi isEnteringPassword) =====
void displayPasswordInput() {
  lcd.setCursor(0, 0);
  lcd.print("Nhap mat khau  ");
  lcd.setCursor(0, 1);
  String disp = "";
  for (unsigned int i = 0; i < inputPassword.length(); i++) {
    if (i == inputPassword.length() - 1 && 
        (millis() - lastCharAddedTime < CHAR_DISPLAY_MS) &&
        lastCharAddedTime > 0) {
      disp += inputPassword[i];
    } else {
      disp += '*';
    }
  }
  lcd.print(disp);
  for (int i = disp.length(); i < 16; i++) lcd.print(" ");
}

// ===== XỬ LÝ KEYPAD =====
void handleKeypad(char key) {
  if (waitingPasswordResult) {
    return;
  }

  lastKeyTime = millis();

  // Phím B - Tắt buzzer và quạt (luôn xử lý)
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
    return;
  }

  // Bắt đầu nhập mật khẩu khi nhấn phím số đầu tiên (không phải A,B,C,D)
  // if (!isEnteringPassword && key != 'A' && key != 'C' && key != 'D') {
  if (!isEnteringPassword) {
    if (key == '*' || key == '#') {
      return;
    }
    isEnteringPassword = true;
    inputPassword = "";
    lastCharAddedTime = 0;
    lcd.clear();
  }

  if (isEnteringPassword) {
    if (key == '*') {
      if (inputPassword.length() > 0) {
        inputPassword = inputPassword.substring(0, inputPassword.length() - 1);
        lastCharAddedTime = 0;
        displayPasswordInput();
      }
    } else if (key == '#') {
      if (inputPassword.length() > 0) {
        // ===== BẮT ĐẦU CHỨC NĂNG HASH MẬT KHẨU =====
        sendPasswordHashToServer(inputPassword);
        // ===== KẾT THÚC CHỨC NĂNG HASH MẬT KHẨU =====
      }
    // } else if (key != 'A' && key != 'C' && key != 'D') {
    }else{
      if (inputPassword.length() < 16) {
        inputPassword += key;
        lastCharAddedTime = millis();
        displayPasswordInput();
      }
    }
  }
}

// ===== HIỂN THỊ LCD CHUYÊN NGHIỆP =====
void displayLCD() {
  if (isEnteringPassword) {
    displayPasswordInput();
    return;
  }

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
  int gasValue = gasAverageValue;
  bool gasDetected = (gasValue > GAS_ALERT_THRESHOLD);

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
