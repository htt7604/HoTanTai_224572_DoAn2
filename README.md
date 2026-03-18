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
- **Đèn**: Điều khiển 3 đèn thủ công + đèn 4 tự động theo PIR

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

- Dự án hỗ trợ MongoDB local hoặc MongoDB Atlas
- Cấu hình qua `.env` trong thư mục `code chuong trinh`:
   - `MONGO_URI=...`
   - `MONGO_DB_NAME=iot_db`

#### 4. Cài đặt MQTT Broker

- Dự án đang dùng HiveMQ Cloud (TLS)
- Port MQTT: `8883`
- Cấu hình `MQTT_USERNAME`, `MQTT_PASSWORD` trong file `.env` (thư mục `code chuong trinh`)

## 📝 Cấu hình

### ESP32 Code

1. Mở file `esp32/esp32.ino`
2. Cấu hình WiFi + MQTT:
   ```cpp
   const char* ssid = "TenWiFi";
   const char* password = "MatKhauWiFi";
   const char* mqtt_server = "3c5308fe02794486932d547731382984.s1.eu.hivemq.cloud";
   const int mqtt_port = 8883;
   ```
3. Upload code lên ESP32

### ESP8266 Code

1. Mở file `esp8266/esp8266.ino`
2. Upload code lên ESP8266
3. Kết nối ESP8266 với ESP32 qua Serial (GPIO 13, 14)

### Server Python

1. Tạo file `.env` trong thư mục `code chuong trinh` (nếu chưa có), tối thiểu gồm:
   - `MQTT_USERNAME=...`
   - `MQTT_PASSWORD=...`
   - `MONGO_URI=...`
   - `MONGO_DB_NAME=iot_db`
2. Chạy server:
   ```bash
   python server.py
   ```
3. Mở trình duyệt: `http://localhost:5000`

## 🔐 Mật khẩu

- Mật khẩu cửa được xác thực ở server bằng SHA256 hash (topic `esp32/password`)
- Kết quả xác thực trả về qua topic `esp32/password/result` (`OK` / `FAIL`)
- Có thể đổi mật khẩu trong web app (server lưu hash vào MongoDB)
- RFID được xác thực ở server qua topic `esp32/rfid`; nếu hợp lệ server mới gửi lệnh mở cửa

## 🎮 Sử dụng

### Điều khiển qua Keypad

- Nhập mật khẩu trên keypad và nhấn `#` để xác thực mở cửa
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

Khi phát hiện gas vượt ngưỡng (động theo baseline cảm biến), hệ thống tự động:

- Bật quạt
- Bật buzzer cảnh báo

### Lửa → Buzzer

Khi phát hiện lửa, buzzer báo động ngay lập tức.

### RFID → Mở cửa

ESP32 gửi UID RFID lên server để xác thực. Nếu hợp lệ, server publish `DOOR_OPEN` và tự động publish `DOOR_CLOSE` sau timeout.

## 📡 MQTT Topics

| Topic | Publish | Subscribe | Payload |
|------|---------|-----------|---------|
| `esp32/sensor` | ESP32 | Server | JSON cảm biến/trạng thái |
| `esp32/events` | ESP32 | Server | JSON event |
| `esp32/control` | Server | ESP32 | text command |
| `esp32/password` | ESP32 | Server | JSON `{type, hash}` |
| `esp32/password/result` | Server | ESP32 | `OK` / `FAIL` |
| `esp32/rfid` | ESP32 | Server | JSON `{uid, source}` |
| `esp32/rfid/result` | Server | ESP32 | JSON `{status, message, uid, auto_open}` |

Danh sách command/payload chi tiết xem thêm tại `code chuong trinh/SMARTHOME_SYSTEM_SPEC.md`.

## AI Điều khiển qua giọng nói

Tự động nhận diện giọng nói khi gọi hệ thống "Nhà tôi ơi" hệ thống sẽ trả lời và người dùng sẽ yêu cầu và hệ thống đáp ứng .
Hoặc ấn vào mic để ra lệnh giọng nói.
Hệ thống AI tự học theo thói quen người dùng dự vào lịch sử sử dụng thiết bị được lưu trên MogoDB

## 📁 Cấu trúc thư mục

```
HoTanTai_224572_DoAn2/
├── code chuong trinh/
│   ├── esp32/
│   │   └── esp32.ino              # Code ESP32 (MQTT + sensor + keypad + RFID)
│   ├── esp8266/
│   │   └── esp8266.ino            # Code ESP8266 điều khiển actuator
│   ├── server.py                  # Python Flask server
│   ├── esp32_simulator.py         # Giả lập ESP32 publish sensor qua MQTT
│   ├── SMARTHOME_SYSTEM_SPEC.md   # Đặc tả đầy đủ topic/payload/event
│   ├── requirements.txt           # Python dependencies
│   └── templates/
│       └── index.html             # Web app interface
├── Mobile/                         # Android app
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
