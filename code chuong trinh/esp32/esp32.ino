#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <MFRC522.h>
#include <SPI.h>
#include <I2CKeyPad.h>

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

// ================= BIẾN TRẠNG THÁI =================
bool isDoorOpen = false;
bool lastRainState = false;
bool lastPirState = false;

byte lastTouchData = 0xFF;

unsigned long lastFireMsg = 0;
unsigned long lastLcdUpdate = 0;

// ===== BIẾN DHT11 =====
float dhtTemp = NAN;
float dhtHum  = NAN;
unsigned long lastDhtRead = 0;

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, 13, 14);

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

  lcd.print("SYSTEM READY");
  delay(1500);
  lcd.clear();
}

void loop() {

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
  int  gasValue    = analogRead(GAS_PIN);

  // ===== BUZZER + ESP8266 =====
  if (isFire) {
    digitalWrite(BUZZER_PIN, HIGH);
    if (millis() - lastFireMsg > 3000) {
      Serial2.println("FIRE_ALARM");
      lastFireMsg = millis();
    }
  }
  else if (gasValue > 400 || pirDetected) {
    digitalWrite(BUZZER_PIN, HIGH);
  }
  else {
    digitalWrite(BUZZER_PIN, LOW);
  }

  if (pirDetected != lastPirState) {
    Serial2.println(pirDetected ? "HUMAN_DETECTED" : "HUMAN_LEFT");
    lastPirState = pirDetected;
  }

  // ===== LCD (500ms) =====
  if (millis() - lastLcdUpdate >= 500) {

    lcd.setCursor(0, 0);
    lcd.print("T:");
    if (!isnan(dhtTemp)) lcd.print((int)dhtTemp);
    else lcd.print("--");
    lcd.print("C ");

    lcd.print("H:");
    if (!isnan(dhtHum)) lcd.print((int)dhtHum);
    else lcd.print("--");
    lcd.print("%   ");

    lcd.setCursor(0, 1);
    if (isFire)            lcd.print(">> FIRE ALERT <<");
    else if (gasValue>400) lcd.print("GAS OVER LIMIT ");
    else if (pirDetected)  lcd.print("MOTION DETECTED");
    else if (isRaining)    lcd.print("RAIN DETECTED  ");
    else                   lcd.print("SAFE SYSTEM   ");

    lastLcdUpdate = millis();
  }

  // ===== MƯA =====
  if (isRaining != lastRainState) {
    Serial2.println(isRaining ? "RAIN_ON" : "RAIN_OFF");
    lastRainState = isRaining;
  }

  // ===== RFID =====
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    isDoorOpen = !isDoorOpen;
    Serial2.println(isDoorOpen ? "DOOR_OPEN" : "DOOR_CLOSE");
    lcd.clear();
    lcd.print("RFID DETECTED");
    lcd.setCursor(0, 1);
    lcd.print(isDoorOpen ? "OPENING DOOR" : "CLOSING DOOR");
    delay(1000);
    rfid.PICC_HaltA();
  }

  // ===== TOUCH =====
  Wire1.requestFrom(0x21, (uint8_t)1);
  if (Wire1.available()) {
    byte touchData = Wire1.read();
    if (touchData != lastTouchData) {

      if (!(touchData & 1) && (lastTouchData & 1)) Serial2.println("LIGHT1_TOGGLE");
      if (!(touchData & 2) && (lastTouchData & 2)) Serial2.println("LIGHT2_TOGGLE");
      if (!(touchData & 4) && (lastTouchData & 4)) Serial2.println("LIGHT3_TOGGLE");

      lastTouchData = touchData;
    }
  }

  // ===== KEYPAD =====
  char key = keypad.getKey();
  if (key == 'A') {
    isDoorOpen = !isDoorOpen;
    Serial2.println(isDoorOpen ? "DOOR_OPEN" : "DOOR_CLOSE");
  }
  else if (key == 'B') {
    digitalWrite(BUZZER_PIN, LOW);
    Serial2.println("FAN_OFF");
  }

  delay(20);
}
