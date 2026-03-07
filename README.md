# HoTanTai_224572_DoAn2 - Hệ thống Smart Home

## 📋 Mô tả dự án

Hệ thống nhà thông minh sử dụng ESP32 và ESP8266 để điều khiển và giám sát các thiết bị trong nhà.

## 🎯 Tính năng chính

### Cảm biến và Giám sát

- **DHT11**: Đo nhiệt độ và độ ẩm
- **Cảm biến Gas (MQ-2)**: Phát hiện khí gas độc hại
- **Cảm biến Mưa**: Phát hiện mưa
- **Cảm biến Lửa**: Phát hiện lửa/cháy
- **PIR Sensor**: Phát hiện chuyển động
- **RFID**: Nhận diện thẻ để mở cửa

### Điều khiển thiết bị

- **Cửa tự động**: Mở/đóng bằng RFID hoặc mật khẩu
- **Rèm/Mái che**: Tự động đóng khi có mưa
- **Quạt**: Tự động bật khi phát hiện gas
- **Buzzer**: Cảnh báo khi có lửa, gas, hoặc chuyển động
- **Đèn**: Điều khiển 3 đèn qua touch sensor

### Hiển thị

- **LCD 16x2**: Hiển thị thông tin chuyên nghiệp với 3 trang tự động chuyển
- **Web App**: Giao diện web đầy đủ để điều khiển và giám sát

## 🔧 Cài đặt

### Phần cứng

- ESP32 (main controller)
- ESP8266 (actuator controller)
- DHT11 sensor
- MQ-2 Gas sensor
- Rain sensor
- Flame sensor
- PIR sensor
- RFID reader (MFRC522)
- I2C Keypad
- Touch sensors
- LCD 16x2 (I2C)
- Servo motors (cửa và rèm)
- Fan
- Buzzer

### Phần mềm

#### 1. Cài đặt Arduino IDE

- Tải và cài đặt Arduino IDE
- Cài đặt board ESP32 và ESP8266
- Cài đặt các thư viện cần thiết:
  - LiquidCrystal_I2C
  - DHT sensor library
  - MFRC522
  - I2CKeyPad
  - PubSubClient (cho MQTT)
  - ArduinoJson

#### 2. Cài đặt Python Server

```bash
cd "code chuong trinh"
pip install -r requirements.txt
```

#### 3. Cài đặt MongoDB

- Tải và cài đặt MongoDB
- Khởi động MongoDB service

#### 4. Cài đặt MQTT Broker

- Cài đặt Mosquitto hoặc MQTT broker khác
- Chạy MQTT broker trên port 1883

## 📝 Cấu hình

### ESP32 Code

1. Mở file `esp32/esp32.ino`
2. Cấu hình WiFi (nếu dùng MQTT):
   ```cpp
   const char* ssid = "TenWiFi";
   const char* password = "MatKhauWiFi";
   const char* MQTT_BROKER = "3c5308fe02794486932d547731382984.s1.eu.hivemq.cloud";

   ```
3. Upload code lên ESP32

### ESP8266 Code

1. Mở file `esp8266/esp8266.ino`
2. Upload code lên ESP8266
3. Kết nối ESP8266 với ESP32 qua Serial (GPIO 13, 14)

### Server Python

1. Chỉnh sửa `server.py` nếu cần:
   - MongoDB connection string
2. Chạy server:
   ```bash
   python server.py
   ```
3. Mở trình duyệt: `http://localhost:5000`

## 🔐 Mật khẩu

- **Mật khẩu mở cửa**: `123456A`
- Nhập mật khẩu qua keypad và nhấn `#` để xác nhận
- RFID: Chỉ cần quẹt thẻ là tự động mở/đóng cửa

## 🎮 Sử dụng

### Điều khiển qua Keypad

- Nhập mật khẩu `123456A` và nhấn `#` để mở/đóng cửa
- Nhấn `*` để xóa ký tự
- Nhấn `B` để reset alarm

### Điều khiển qua Web App

1. Mở trình duyệt: `http://localhost:5000`
2. Xem trạng thái tất cả cảm biến
3. Điều khiển:
   - Cửa: Nhập mật khẩu và nhấn "Mở cửa"
   - Đèn: Bật/tắt qua switch
   - Quạt: Bật/tắt quạt
   - Rèm: Mở/đóng rèm

### Hiển thị LCD

LCD tự động chuyển 3 trang mỗi 5 giây:

- **Trang 1**: Nhiệt độ, độ ẩm, gas, trạng thái cửa
- **Trang 2**: Trạng thái cảm biến (lửa, gas, chuyển động, mưa, quạt)
- **Trang 3**: Tổng quan hệ thống
- Ngoài ra khi có sự kiện thì hiển thị ngay lập tức VD: Nhập mật khẩu, thông báo lửa, thông báo mưa,...

## ⚙️ Tự động hóa

### Mưa → Đóng rèm

Khi cảm biến mưa phát hiện mưa, hệ thống tự động đóng rèm/mái che.

### Gas → Bật quạt + Buzzer

Khi phát hiện gas vượt ngưỡng (>400), hệ thống tự động:

- Bật quạt
- Bật buzzer cảnh báo

### Lửa → Buzzer

Khi phát hiện lửa, buzzer báo động ngay lập tức.

### RFID → Mở cửa

Chỉ cần quẹt thẻ RFID, cửa tự động mở/đóng.

## AI Điều khiển qua giọng nói

Tự động nhận diện giọng nói khi gọi hệ thống "Nhà tôi ơi" hệ thống sẽ trả lời và người dùng sẽ yêu cầu và hệ thống đáp ứng .
Hoặc ấn vào mic để ra lệnh giọng nói.
Hệ thống AI tự học theo thói quen người dùng dự vào lịch sử sử dụng thiết bị được lưu trên MogoDB

## 📁 Cấu trúc thư mục

```
HoTanTai_224572_DoAn2/
├── code chuong trinh/
│   ├── esp32/
│   │   ├── esp32.ino              # Code ESP32 không dùng MQTT
│   │   └── esp32_runtoSever.ino   # Code ESP32 dùng MQTT
│   ├── esp8266/
│   │   └── esp8266.ino            # Code ESP8266 điều khiển actuator
│   ├── server.py                  # Python Flask server
│   ├── requirements.txt           # Python dependencies
│   └── templates/
│       └── index.html             # Web app interface
├── Noi day/
│   └── So_do_noi_day_ESP32_ESP8266_CHUAN_CUOI.docx
└── README.md
```

## 🔗 Tài liệu tham khảo

+ https://www.slideshare.net/slideshow/bo-co-n-tt-nghip-thit-k-nh-thng-minh/265010741
+ https://www.slideshare.net/slideshow/luan-van-he-thong-iot-dieu-khien-va-giam-sat-ngoi-nha-hay-9d/207011713
+ https://www.slideshare.net/slideshow/n-thit-k-ch-to-m-hinh-nh-thng-minh-s-dng-arduinodocx/256635836
+ https://www.slideshare.net/slideshow/bo-co-n-chuyn-ngnh-thit-k-nh-thng-minhdocx/267101938

## 👤 Tác giả

**Hồ Tấn Tài** - 224572

## 📄 License

Dự án đồ án
