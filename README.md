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

### Server Python (đã triển khai cloud)

- Server đã chạy trên máy chủ cloud, không cần chạy `python server.py` trên máy cá nhân.
- Truy cập trực tiếp web tại: `https://hotantai.id.vn`

## 🔐 Mật khẩu

- Mật khẩu cửa được xác thực ở server bằng SHA256 hash (topic `esp32/password`)
- Kết quả xác thực trả về qua topic `esp32/password/result` (`OK` / `FAIL`)
- Có thể đổi mật khẩu trong web app (server lưu hash vào MongoDB)
- RFID được xác thực ở server qua topic `esp32/rfid`; nếu hợp lệ server mới gửi lệnh mở cửa

## 🎮 Sử dụng

## 👨‍🏫 Hướng dẫn sử dụng hệ thống cho thầy (demo nhanh)

### 1) Chuẩn bị trước khi demo

- Server đã được triển khai trên cloud.
- Link truy cập web: `https://hotantai.id.vn`
- Chỉ cần chuẩn bị:
   - Trình duyệt web để demo.
   - Điện thoại Android (nếu demo app APK).

### 2) Chạy hệ thống

#### Cách A - Demo có phần cứng thật (ESP32/ESP8266)

1. Cấp nguồn ESP32 + ESP8266, kiểm tra đã kết nối WiFi/MQTT.
2. Mở web tại: `https://hotantai.id.vn`

#### Cách B - Demo không có phần cứng (dùng simulator)

1. Mở terminal, chạy giả lập ESP32 để publish dữ liệu lên MQTT:
   ```bash
   cd "code chuong trinh"
   python esp32_simulator.py
   ```
2. Mở web để theo dõi dữ liệu cảm biến/events: `https://hotantai.id.vn`

### 3) Tài khoản đăng nhập demo

- Đăng nhập web/app bằng **tài khoản và mật khẩu** đã tạo trong hệ thống.
- Server tự tạo tài khoản mặc định nếu chưa có:
  - `username: admin`
  - `password: 123`

### 4) Ứng dụng Android demo (APK)

- Dự án có sẵn file APK để cài trực tiếp và demo trên điện thoại.
- File APK: `APK Demo app/app-debug.apk`
- Cách dùng nhanh:
  1. Chép file APK vào điện thoại Android.
  2. Cài đặt ứng dụng (cho phép cài từ nguồn ngoài nếu được yêu cầu).
  3. Mở app và đăng nhập bằng tài khoản/mật khẩu của hệ thống.

### 5) Luồng demo đề xuất cho buổi chấm

1. **Đăng nhập** vào web/app bằng tài khoản `admin`.
2. **Xem dữ liệu cảm biến realtime** ở màn hình chính.
3. **Điều khiển thiết bị**: cửa, đèn, quạt, mái che.
4. **Kiểm tra AI**:
   - Gửi lệnh text/giọng nói (ví dụ: bật đèn phòng khách).
   - Quan sát server publish lệnh MQTT và thiết bị đổi trạng thái.
5. **Kiểm tra bảo mật cửa**:
   - Quét RFID hợp lệ/không hợp lệ.
   - Nhập mật khẩu cửa đúng/sai.
6. **Xem lịch sử** tại trang history (sự kiện, cảnh báo, hành động người dùng).

### 6) Điểm nhấn cần trình bày với thầy

- Kiến trúc 3 lớp: **Thiết bị IoT ↔ Server Flask/MQTT ↔ Web/Mobile App**.
- Cảnh báo an toàn: **lửa, gas, chuyển động** + push notification.
- AI có khả năng:
  - Dạy intent/alias/rule mới.
  - Học từ lịch sử thao tác để tự tạo rule.
  - Retrain mô hình intent theo dữ liệu mới.

### 7) Xử lý nhanh lỗi thường gặp khi demo

- Không có dữ liệu cảm biến: kiểm tra ESP32 hoặc chạy `esp32_simulator.py`.
- Lỗi MQTT: kiểm tra `MQTT_USERNAME`, `MQTT_PASSWORD`, internet.
- Lỗi MongoDB: kiểm tra `MONGO_URI`, trạng thái MongoDB Atlas/local.
- Mở web không được: kiểm tra domain `https://hotantai.id.vn` và kết nối internet.

### Điều khiển qua Keypad

- Nhập mật khẩu trên keypad và nhấn `#` để xác thực mở cửa
- Nhấn `*` để xóa ký tự
- Nhấn `B` để reset alarm

### Điều khiển qua Web App

1. Mở trình duyệt: `https://hotantai.id.vn`
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

| Topic                     | Publish | Subscribe | Payload                                    |
| ------------------------- | ------- | --------- | ------------------------------------------ |
| `esp32/sensor`          | ESP32   | Server    | JSON cảm biến/trạng thái               |
| `esp32/events`          | ESP32   | Server    | JSON event                                 |
| `esp32/control`         | Server  | ESP32     | text command                               |
| `esp32/password`        | ESP32   | Server    | JSON `{type, hash}`                      |
| `esp32/password/result` | Server  | ESP32     | `OK` / `FAIL`                          |
| `esp32/rfid`            | ESP32   | Server    | JSON `{uid, source}`                     |
| `esp32/rfid/result`     | Server  | ESP32     | JSON `{status, message, uid, auto_open}` |

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

## 👤 Tác giả

**Hồ Tấn Tài** - 224572

## 📄 License

Dự án đồ án
