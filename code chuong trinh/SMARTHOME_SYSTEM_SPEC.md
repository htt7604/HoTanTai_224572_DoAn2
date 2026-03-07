# Smart Home System - Đặc tả & Tổng hợp

## PHẦN 7 — OUTPUT

### 1. TẤT CẢ EVENT HỆ THỐNG

#### Event thiết bị (từ sensor data)
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

#### Event cảm biến
| Event | Mô tả |
|-------|-------|
| RAIN_DETECTED | Phát hiện mưa |
| RAIN_STOPPED | Hết mưa |
| MOTION_DETECTED | Phát hiện chuyển động (PIR) |
| MOTION_STOPPED | Không còn chuyển động |
| FIRE_ALERT | Cảnh báo lửa |
| GAS_ALERT | Cảnh báo gas vượt ngưỡng |
| GAS_NORMAL | Gas trở về bình thường |
| TEMP_CHANGE | Nhiệt độ thay đổi > 2°C |
| HUMIDITY_CHANGE | Độ ẩm thay đổi > 5% |

#### Event từ ESP32 (topic esp32/events)
| Event | Mô tả |
|-------|-------|
| RFID_OPEN | RFID mở cửa |
| RFID_CLOSE | RFID đóng cửa |
| KEYPAD_OPEN | Keypad mở cửa (mật khẩu đúng) |
| KEYPAD_CLOSE | Keypad đóng cửa |
| BUZZER_ALARM | Buzzer báo động (khi lửa) |
| HUMAN_DETECTED | Phát hiện người (PIR) |
| HUMAN_LEFT | Không còn phát hiện người |
| ROOF_AUTO_CLOSE_RAIN | Mái tự động đóng do mưa |
| ROOF_AUTO_OPEN | Mái tự động mở khi hết mưa |

---

### 2. JSON SENSOR CHUẨN (esp32/sensor)

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
  "fan": false
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| temp | float | Nhiệt độ (°C) |
| hum | float | Độ ẩm (%) |
| gas | int | Giá trị cảm biến gas |
| rain | bool | true = có mưa |
| flame | bool | true = phát hiện lửa |
| pir | bool | true = phát hiện chuyển động |
| door | bool | true = cửa mở |
| light1 | bool | true = đèn 1 bật |
| light2 | bool | true = đèn 2 bật |
| light3 | bool | true = đèn 3 bật |
| fan | bool | true = quạt bật |

- **Chu kỳ gửi:** 2 giây  
- **Topic:** `esp32/sensor`

---

### 3. MQTT COMMANDS (esp32/control)

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
| FAN_ON | Bật quạt |
| FAN_OFF | Tắt quạt |
| ROOF_OPEN | Mở mái/rèm |
| ROOF_CLOSE | Đóng mái/rèm |

---

### 4. MONGODB COLLECTIONS

| Collection | Khi nào lưu |
|------------|-------------|
| sensor_data | Định kỳ mỗi 2 phút, HOẶC khi có sự kiện |
| events | Khi có event (save_event) |
| device_states | Khi trạng thái thiết bị thay đổi |
| user_actions | Khi user gửi lệnh (voice, API, web) |

---

### 5. LOG FORMAT

| Prefix | Ý nghĩa |
|--------|---------|
| [EVENT] | Sự kiện được lưu vào events |
| [SENSOR] | Dữ liệu sensor / lưu định kỳ |
| [MQTT] | Kết nối / gửi command |
| [USER ACTION] | Hành động người dùng |

---

### 6. LUỒNG HỆ THỐNG

```
ESP32 (cảm biến, RFID, Keypad, PIR...)
    │
    ├── publish "esp32/sensor" (JSON, mỗi 2s)
    └── publish "esp32/events" (RFID, KEYPAD, BUZZER, ROOF_AUTO...)
            │
            ▼
    Flask Server (on_message)
            │
            ├── check_and_save_changes() → events, device_states
            ├── Lưu sensor_data (định kỳ 2 phút hoặc khi có event)
            └── latest_data (API /dashboard)
            │
            ▼
    MongoDB (sensor_data, events, device_states, user_actions)
            │
            ▼
    Web Dashboard (API /sensor/latest, /events, /states/latest)
```

User điều khiển:
```
Web/Voice/AI → Server → mqtt_client.publish("esp32/control", command)
                            │
                            ▼
                    ESP32 callback() → Serial2 → ESP8266 (thực thi)
```
