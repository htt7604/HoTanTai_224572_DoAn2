#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <MFRC522.h>
#include <SPI.h>

// ================= WIFI + MQTT =================
const char* ssid = "Thuong";
const char* password = "12345678";
const char* mqtt_server = "192.168.1.5";  // ⚠ SỬA IP NẾU CẦN

#define TOPIC_SENSOR  "esp32/sensor"
#define TOPIC_CONTROL "esp32/control"

WiFiClient espClient;
PubSubClient mqtt(espClient);

// ================= PIN =================
#define GAS_PIN    34
#define RAIN_PIN   35
#define FLAME_PIN  27
#define BUZZER_PIN 15
#define PIR_PIN    17

#define SS_PIN     5
#define RST_PIN    4
MFRC522 rfid(SS_PIN, RST_PIN);

// ================= DHT =================
#define DHTPIN   25
#define DHTTYPE  DHT11
DHT dht(DHTPIN, DHTTYPE);

// ================= LCD =================
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ================= STATE =================
bool isDoorOpen = false;

float dhtTemp = NAN;
float dhtHum  = NAN;

unsigned long lastDhtRead  = 0;
unsigned long lastMqttSend = 0;
unsigned long lastLcdUpdate = 0;

// ================= MQTT CALLBACK =================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String cmd = "";
  for (int i = 0; i < length; i++) cmd += (char)payload[i];

  Serial.print("MQTT CMD: ");
  Serial.println(cmd);

  if (cmd == "DOOR_OPEN")  isDoorOpen = true;
  if (cmd == "DOOR_CLOSE") isDoorOpen = false;
}

// ================= MQTT CONNECT =================
void reconnectMQTT() {
  while (!mqtt.connected()) {
    Serial.println("Connecting MQTT...");
    if (mqtt.connect("ESP32_CLIENT")) {
      Serial.println("MQTT connected!");
      mqtt.subscribe(TOPIC_CONTROL);
    } else {
      Serial.print("MQTT failed, rc=");
      Serial.println(mqtt.state());
      delay(2000);
    }
  }
}

// ================= WIFI CONNECT =================
void connectWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi connected!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
}

// ================= SETUP =================
void setup() {

  Serial.begin(115200);

  pinMode(RAIN_PIN, INPUT);
  pinMode(FLAME_PIN, INPUT);
  pinMode(PIR_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  Wire.begin(32, 33);
  lcd.init();
  lcd.backlight();

  dht.begin();

  SPI.begin();
  rfid.PCD_Init();

  lcd.print("SYSTEM READY");
  delay(1500);
  lcd.clear();

  connectWiFi();

  mqtt.setServer(mqtt_server, 1883);
  mqtt.setCallback(mqttCallback);
}

// ================= LOOP =================
void loop() {

  if (!mqtt.connected()) reconnectMQTT();
  mqtt.loop();

  // ===== DHT (2s) =====
  if (millis() - lastDhtRead >= 2000) {

    float t = dht.readTemperature();
    float h = dht.readHumidity();

    if (!isnan(t) && !isnan(h)) {
      dhtTemp = t;
      dhtHum  = h;
    } else {
      Serial.println("DHT read failed");
    }

    lastDhtRead = millis();
  }

  bool isRain = (digitalRead(RAIN_PIN) == LOW);
  bool isPir  = digitalRead(PIR_PIN);
  bool isFire = (digitalRead(FLAME_PIN) == LOW);
  int gasVal  = analogRead(GAS_PIN);

  // ===== BUZZER =====
  if (isFire || gasVal > 400 || isPir)
    digitalWrite(BUZZER_PIN, HIGH);
  else
    digitalWrite(BUZZER_PIN, LOW);

  // ===== LCD =====
  if (millis() - lastLcdUpdate >= 500) {

    lcd.setCursor(0,0);
    lcd.print("T:");
    lcd.print(isnan(dhtTemp) ? 0 : (int)dhtTemp);
    lcd.print("C H:");
    lcd.print(isnan(dhtHum) ? 0 : (int)dhtHum);
    lcd.print("%   ");

    lcd.setCursor(0,1);

    if (isFire)            lcd.print(">> FIRE ALERT <<");
    else if (gasVal > 400) lcd.print("GAS OVER LIMIT ");
    else if (isPir)        lcd.print("MOTION DETECTED");
    else if (isRain)       lcd.print("RAIN DETECTED  ");
    else                   lcd.print("SAFE SYSTEM    ");

    lastLcdUpdate = millis();
  }

  // ===== MQTT SEND (2s) =====
  if (millis() - lastMqttSend >= 2000) {

    StaticJsonDocument<512> doc;

    doc["temp"]  = isnan(dhtTemp) ? 0 : dhtTemp;
    doc["hum"]   = isnan(dhtHum) ? 0 : dhtHum;

    doc["gas"]   = gasVal;
    doc["rain"]  = isRain;
    doc["flame"] = isFire;
    doc["pir"]   = isPir;

    doc["door"]  = isDoorOpen ? "OPEN" : "CLOSE";

    doc["light1"] = false;
    doc["light2"] = false;
    doc["light3"] = false;

    char buffer[512];
    serializeJson(doc, buffer);

    if (mqtt.publish(TOPIC_SENSOR, buffer)) {
      Serial.println("MQTT SENT:");
      Serial.println(buffer);
    } else {
      Serial.println("MQTT SEND FAILED");
    }

    lastMqttSend = millis();
  }

  delay(10);
}
