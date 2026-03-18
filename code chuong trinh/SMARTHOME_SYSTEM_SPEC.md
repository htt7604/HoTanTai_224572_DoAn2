# Smart Home System - Đặc tả & Tổng hợp (Bản đầy đủ)

## 1. MQTT TOPOLOGY (PUBLISH / SUBSCRIBE)

### 1.1 Danh sách Topic chuẩn
| Topic | Bên publish | Bên subscribe | Mục đích |
|------|-------------|---------------|----------|
| `esp32/sensor` | ESP32 | Flask Server | Gửi telemetry cảm biến + trạng thái thiết bị định kỳ |
| `esp32/events` | ESP32 | Flask Server | Gửi sự kiện tức thời (mưa, PIR, gas, buzzer, RFID scan...) |
| `esp32/control` | Flask Server | ESP32 | Gửi lệnh điều khiển thiết bị |
| `esp32/password` | ESP32 | Flask Server | Gửi yêu cầu xác thực mật khẩu keypad (hash SHA256) |
| `esp32/password/result` | Flask Server | ESP32 | Trả kết quả xác thực keypad (`OK` / `FAIL`) |
| `esp32/rfid` | ESP32 | Flask Server | Gửi UID RFID để xác thực |
| `esp32/rfid/result` | Flask Server | ESP32 | Trả kết quả xác thực RFID (JSON chi tiết) |

### 1.2 Broker & bảo mật
- Broker: `3c5308fe02794486932d547731382984.s1.eu.hivemq.cloud`
- Port: `8883` (TLS)
- Auth: username/password MQTT

---

## 2. CHUẨN PAYLOAD MQTT

### 2.1 Topic `esp32/sensor` (ESP32 → Server)

```json
{
        "temp": 28.5,
        "hum": 70.0,
        "gas": 280,
        "rain": false,
        "flame": false,
        "pir": false,
        "door": false,
        "light1": false,
        "light2": false,
        "light3": false,
        "light4": false,
        "fan": false
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| temp | float | Nhiệt độ (°C) |
| hum | float | Độ ẩm (%) |
| gas | int | Giá trị cảm biến gas |
| rain | bool | `true` = có mưa |
| flame | bool | `true` = phát hiện lửa |
| pir | bool | `true` = phát hiện chuyển động |
| door | bool | `true` = cửa mở |
| light1 | bool | trạng thái đèn 1 |
| light2 | bool | trạng thái đèn 2 |
| light3 | bool | trạng thái đèn 3 |
| light4 | bool | trạng thái đèn 4 (đèn PIR automation) |
| fan | bool | trạng thái quạt |

- Chu kỳ gửi: 2 giây/lần

### 2.2 Topic `esp32/events` (ESP32 → Server)
Payload JSON chuẩn:

```json
{
        "event": "MOTION_DETECTED"
}
```

### 2.3 Topic `esp32/control` (Server → ESP32)
Payload là plain text command (ví dụ: `DOOR_OPEN`, `LIGHT1_ON`, `FAN_OFF`...).

### 2.4 Topic `esp32/password` (ESP32 → Server)
Payload JSON:

```json
{
        "type": "password_check",
        "hash": "<sha256_hex>"
}
```

### 2.5 Topic `esp32/password/result` (Server → ESP32)
Payload plain text:
- `OK`
- `FAIL`

### 2.6 Topic `esp32/rfid` (ESP32 → Server)
Payload JSON:

```json
{
        "uid": "A1B2C3D4",
        "source": "esp32"
}
```

### 2.7 Topic `esp32/rfid/result` (Server → ESP32)
Payload JSON:

```json
{
        "status": "OK",
        "message": "RFID hop le - mo cua",
        "uid": "A1B2C3D4",
        "auto_open": true
}
```

`status` có thể là: `INIT_OK`, `OK`, `DENY`, `EMPTY`.

---

## 3. MQTT COMMANDS (`esp32/control`)

| Command | Mô tả |
|---------|-------|
| DOOR_OPEN | Mở cửa |
| DOOR_CLOSE | Đóng cửa |
| LIGHT1_ON | Bật đèn 1 |
| LIGHT1_OFF | Tắt đèn 1 |
| LIGHT2_ON | Bật đèn 2 |
| LIGHT2_OFF | Tắt đèn 2 |
| LIGHT3_ON | Bật đèn 3 |
| LIGHT3_OFF | Tắt đèn 3 |
| LIGHT4_ON | Bật đèn 4 (thường do PIR automation) |
| LIGHT4_OFF | Tắt đèn 4 (thường do PIR automation) |
| FAN_ON | Bật quạt |
| FAN_OFF | Tắt quạt |
| ROOF_OPEN | Mở mái/rèm |
| ROOF_CLOSE | Đóng mái/rèm |

---

## 4. TẤT CẢ EVENT HỆ THỐNG

### 4.1 Event thiết bị (server suy ra từ `esp32/sensor`)
| Event | Mô tả |
|-------|-------|
| DOOR_OPENED | Cửa mở |
| DOOR_CLOSED | Cửa đóng |
| LIGHT1_ON | Đèn 1 bật |
| LIGHT1_OFF | Đèn 1 tắt |
| LIGHT2_ON | Đèn 2 bật |
| LIGHT2_OFF | Đèn 2 tắt |
| LIGHT3_ON | Đèn 3 bật |
| LIGHT3_OFF | Đèn 3 tắt |
| FAN_ON | Quạt bật |
| FAN_OFF | Quạt tắt |

### 4.2 Event cảm biến
| Event | Mô tả |
|-------|-------|
| RAIN_DETECTED | Phát hiện mưa |
| RAIN_STOPPED | Hết mưa |
| MOTION_DETECTED | Phát hiện chuyển động (PIR) |
| MOTION_STOPPED | Không còn chuyển động |
| FIRE_ALERT | Cảnh báo lửa |
| GAS_ALERT | Cảnh báo gas vượt ngưỡng |
| GAS_NORMAL | Gas trở về bình thường |
| TEMP_CHANGE | Nhiệt độ thay đổi vượt ngưỡng |
| HUMIDITY_CHANGE | Độ ẩm thay đổi vượt ngưỡng |

### 4.3 Event đến từ topic `esp32/events`
| Event | Mô tả |
|-------|-------|
| RFID_SCAN | Quét RFID |
| BUZZER_ALARM | Buzzer báo động |
| GAS_DETECTED | ESP32 phát hiện gas |
| GAS_NORMAL | ESP32 báo gas về bình thường |
| MOTION_DETECTED | ESP32 phát hiện chuyển động |
| MOTION_STOPPED | ESP32 không còn phát hiện chuyển động |
| ROOF_AUTO_CLOSE_RAIN | Mái tự động đóng do mưa |
| ROOF_AUTO_OPEN | Mái tự động mở khi hết mưa |

### 4.4 Event do server xử lý xác thực
| Event | Mô tả |
|-------|-------|
| PASSWORD_OK | Xác thực keypad thành công |
| PASSWORD_FAIL | Xác thực keypad thất bại |
| RFID_INIT | Khởi tạo thẻ RFID đầu tiên |
| RFID_GRANTED | RFID hợp lệ |
| RFID_DENIED | RFID không hợp lệ |
| RFID_EMPTY | RFID rỗng/lỗi đọc UID |
| DOOR_AUTO_CLOSE | Server tự đóng cửa sau timeout |
| AUTO_LIGHT4_ON_BY_PIR | Server tự bật đèn 4 theo PIR |
| AUTO_LIGHT4_OFF_BY_PIR | Server tự tắt đèn 4 theo PIR |

---

## 5. MONGODB COLLECTIONS

| Collection | Khi nào lưu |
|------------|-------------|
| sensor_data | Định kỳ mỗi 2 phút hoặc khi có thay đổi quan trọng |
| events | Khi gọi `save_event()` |
| device_states | Khi trạng thái thiết bị thay đổi |
| user_actions | Khi user gửi lệnh từ web/voice/API |
| rfid_cards | Lưu thẻ RFID đang active |
| rfid_scans | Lưu lịch sử quét RFID |
| door_password | Lưu hash mật khẩu cửa |
| mobile_push_tokens | Token mobile để push cảnh báo |

---

## 6. LOG FORMAT

| Prefix | Ý nghĩa |
|--------|---------|
| [EVENT] | Sự kiện được lưu vào `events` |
| [SENSOR] | Dữ liệu sensor / lưu định kỳ |
| [MQTT] | Kết nối, subscribe, publish MQTT |
| [USER ACTION] | Hành động người dùng |
| [PUSH] | Gửi thông báo FCM |

---

## 7. LUỒNG HỆ THỐNG

### 7.1 Telemetry + Event

```text
ESP32
        ├─ publish esp32/sensor (2s/lần)
        └─ publish esp32/events (khi có sự kiện)
                         ↓
Flask Server (on_message)
        ├─ parse payload
        ├─ save_event / check_and_save_changes
        ├─ lưu MongoDB
        └─ cập nhật latest_data cho API
```

### 7.2 Luồng điều khiển thiết bị

```text
Web/Voice/AI/API
        → Flask Server
        → publish esp32/control (command)
        → ESP32 callback()
        → Serial2 → ESP8266 thực thi relay/động cơ
```

### 7.3 Luồng keypad

```text
ESP32 keypad
        → publish esp32/password ({type:"password_check", hash})
        → Server xác thực hash
        → publish esp32/password/result (OK/FAIL)
        → ESP32 xử lý phản hồi
```

### 7.4 Luồng RFID

```text
ESP32 RFID scan
        → publish esp32/rfid ({uid, source})
        → Server kiểm tra thẻ active
        → publish esp32/rfid/result (INIT_OK/OK/DENY/EMPTY)
        → nếu hợp lệ: Server publish esp32/control (DOOR_OPEN)
        → sau timeout: Server publish esp32/control (DOOR_CLOSE)
```
