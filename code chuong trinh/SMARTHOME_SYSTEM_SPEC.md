# Smart Home System - Đặc tả & Tổng hợp (Bản đầy đủ)

## 1. MQTT TOPOLOGY (PUBLISH / SUBSCRIBE)

### 1.1 Danh sách Topic chuẩn

| Topic                     | Bên publish | Bên subscribe | Mục đích                                                      |
| ------------------------- | ------------ | -------------- | ---------------------------------------------------------------- |
| `esp32/sensor`          | ESP32        | Flask Server   | Gửi telemetry cảm biến + trạng thái thiết bị định kỳ   |
| `esp32/events`          | ESP32        | Flask Server   | Gửi sự kiện tức thời (mưa, PIR, gas, buzzer, RFID scan...) |
| `esp32/control`         | Flask Server | ESP32          | Gửi lệnh điều khiển thiết bị                              |
| `esp32/password`        | ESP32        | Flask Server   | Gửi yêu cầu xác thực mật khẩu keypad (hash SHA256)        |
| `esp32/password/result` | Flask Server | ESP32          | Trả kết quả xác thực keypad (`OK` / `FAIL`)             |
| `esp32/rfid`            | ESP32        | Flask Server   | Gửi UID RFID để xác thực                                    |
| `esp32/rfid/result`     | Flask Server | ESP32          | Trả kết quả xác thực RFID (JSON chi tiết)                  |

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

| Field  | Type  | Mô tả                                     |
| ------ | ----- | ------------------------------------------- |
| temp   | float | Nhiệt độ (°C)                           |
| hum    | float | Độ ẩm (%)                                |
| gas    | int   | Giá trị cảm biến gas                    |
| rain   | bool  | `true` = có mưa                         |
| flame  | bool  | `true` = phát hiện lửa                 |
| pir    | bool  | `true` = phát hiện chuyển động       |
| door   | bool  | `true` = cửa mở                         |
| light1 | bool  | trạng thái đèn 1                        |
| light2 | bool  | trạng thái đèn 2                        |
| light3 | bool  | trạng thái đèn 3                        |
| light4 | bool  | trạng thái đèn 4 (đèn PIR automation) |
| fan    | bool  | trạng thái quạt                          |

- Chu kỳ gửi: 2 giây/lần

### 2.2 Topic `esp32/events` (ESP32 → Server)

Payload JSON chuẩn:

```json
{
        "event": "MOTION_DETECTED"
}
```

| Field  | Type   | Bắt buộc | Mô tả                                    |
| ------ | ------ | ---------- | ------------------------------------------ |
| event  | string | Có        | Mã sự kiện do ESP32 phát ra            |
| source | string | Không     | Nguồn phát sự kiện (ví dụ `esp32`) |
| uid    | string | Không     | UID RFID (nếu là sự kiện RFID)         |
| gas    | int    | Không     | Giá trị gas tại thời điểm sự kiện  |
| rain   | bool   | Không     | Trạng thái mưa nếu liên quan          |
| pir    | bool   | Không     | Trạng thái PIR nếu liên quan           |
| flame  | bool   | Không     | Trạng thái lửa nếu liên quan          |
| note   | string | Không     | Ghi chú bổ sung từ firmware             |

**Các `event` thường gặp từ ESP32:**

| Event                | Ý nghĩa                      |
| -------------------- | ------------------------------ |
| RFID_SCAN            | ESP32 vừa quét RFID          |
| RFID_GRANTED         | RFID hợp lệ                  |
| RFID_DENIED          | RFID không hợp lệ           |
| RFID_INIT            | Khởi tạo RFID lần đầu     |
| KEYPAD_OPEN          | Mở cửa từ keypad            |
| KEYPAD_CLOSE         | Đóng cửa từ keypad         |
| BUZZER_ALARM         | Kích hoạt còi cảnh báo    |
| MOTION_DETECTED      | PIR phát hiện chuyển động |
| MOTION_STOPPED       | PIR không còn chuyển động |
| ROOF_AUTO_CLOSE_RAIN | Mái tự đóng do mưa        |
| ROOF_AUTO_OPEN       | Mái tự mở khi hết mưa     |

### 2.3 Topic `esp32/control` (Server → ESP32)

Payload là plain text command (ví dụ: `DOOR_OPEN`, `LIGHT1_ON`, `FAN_OFF`...).

| Thành phần payload | Type                | Mô tả                                         |
| -------------------- | ------------------- | ----------------------------------------------- |
| command              | string (plain text) | Lệnh điều khiển duy nhất gửi xuống ESP32 |

| Command    | Nhóm | Thiết bị | Tác dụng                    |
| ---------- | ----- | ---------- | ----------------------------- |
| DOOR_OPEN  | Door  | Cửa       | Mở cửa                      |
| DOOR_CLOSE | Door  | Cửa       | Đóng cửa                   |
| LIGHT1_ON  | Light | Đèn 1    | Bật đèn 1                  |
| LIGHT1_OFF | Light | Đèn 1    | Tắt đèn 1                  |
| LIGHT2_ON  | Light | Đèn 2    | Bật đèn 2                  |
| LIGHT2_OFF | Light | Đèn 2    | Tắt đèn 2                  |
| LIGHT3_ON  | Light | Đèn 3    | Bật đèn 3                  |
| LIGHT3_OFF | Light | Đèn 3    | Tắt đèn 3                  |
| LIGHT4_ON  | Light | Đèn 4    | Bật đèn 4 (PIR automation) |
| LIGHT4_OFF | Light | Đèn 4    | Tắt đèn 4 (PIR automation) |
| FAN_ON     | Fan   | Quạt      | Bật quạt                    |
| FAN_OFF    | Fan   | Quạt      | Tắt quạt                    |
| ROOF_OPEN  | Roof  | Mái/rèm  | Mở mái                      |
| ROOF_CLOSE | Roof  | Mái/rèm  | Đóng mái                   |

### 2.4 Topic `esp32/password` (ESP32 → Server)

Payload JSON:

```json
{
        "type": "password_check",
        "hash": "<sha256_hex>"
}
```

| Field | Type   | Bắt buộc | Mô tả                                                  |
| ----- | ------ | ---------- | -------------------------------------------------------- |
| type  | string | Có        | Giá trị cố định:`password_check`                  |
| hash  | string | Có        | SHA256 hex của mật khẩu nhập từ keypad (64 ký tự) |

| Quy tắc validate | Chi tiết                                                                    |
| ----------------- | ---------------------------------------------------------------------------- |
| Độ dài hash    | 64 ký tự hex                                                               |
| Ký tự hợp lệ  | `[0-9a-fA-F]`                                                              |
| Sai format        | Server trả `FAIL` qua `esp32/password/result` và ghi `PASSWORD_FAIL` |

### 2.5 Topic `esp32/password/result` (Server → ESP32)

Payload plain text:

- `OK`
- `FAIL`

| Payload | Ý nghĩa                                  | Hành vi ESP32 kỳ vọng                       |
| ------- | ------------------------------------------ | ---------------------------------------------- |
| OK      | Mật khẩu keypad hợp lệ                 | Mở cửa hoặc thực hiện luồng mở cửa     |
| FAIL    | Mật khẩu không hợp lệ / lỗi validate | Từ chối mở cửa, có thể cảnh báo buzzer |

### 2.6 Topic `esp32/rfid` (ESP32 → Server)

Payload JSON:

```json
{
        "uid": "A1B2C3D4",
        "source": "esp32"
}
```

| Field  | Type   | Bắt buộc | Mô tả                                             |
| ------ | ------ | ---------- | --------------------------------------------------- |
| uid    | string | Có        | UID thẻ RFID (server sẽ normalize về hex chuẩn) |
| source | string | Không     | Nguồn gửi, mặc định là `esp32`              |

| Quy tắc xử lý UID      | Chi tiết                                  |
| ------------------------- | ------------------------------------------ |
| Chuẩn hóa               | Uppercase, bỏ ký tự ngoài `[0-9A-F]` |
| UID rỗng sau chuẩn hóa | Trả trạng thái `EMPTY`                |
| Chưa có thẻ active     | Khởi tạo thẻ đầu tiên (`INIT_OK`)  |
| UID khớp thẻ active     | Chấp nhận (`OK`)                       |
| UID không khớp          | Từ chối (`DENY`)                       |

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

| Field     | Type   | Bắt buộc | Mô tả                                      |
| --------- | ------ | ---------- | -------------------------------------------- |
| status    | string | Có        | Trạng thái xác thực RFID                 |
| message   | string | Có        | Nội dung mô tả ngắn cho firmware/UI      |
| uid       | string | Có        | UID đã xử lý                             |
| auto_open | bool   | Có        | `true` nếu server sẽ mở cửa tự động |

| status  | Nghĩa nghiệp vụ                       | auto_open |
| ------- | ---------------------------------------- | --------- |
| INIT_OK | Khởi tạo thẻ đầu tiên thành công | true      |
| OK      | Thẻ hợp lệ                            | true      |
| DENY    | Thẻ không hợp lệ                     | false     |
| EMPTY   | UID rỗng / lỗi đọc UID               | false     |

### 2.8 Chức năng cụ thể của từng Topic

| Topic                     | Chức năng cụ thể                                                        | Server xử lý chính                                                                                                                  | Kết quả đầu ra                                                                                     |
| ------------------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `esp32/sensor`          | Đồng bộ dữ liệu cảm biến + trạng thái thiết bị theo chu kỳ      | Parse payload, cập nhật `latest_data`, gọi `check_and_save_changes()`, lưu `sensor_data` định kỳ hoặc khi có thay đổi | API `/sensor/latest`, `/sensor/history` luôn có dữ liệu mới; phát hiện sự kiện tự động |
| `esp32/events`          | Gửi sự kiện tức thời từ firmware (RFID, keypad, motion, roof auto...) | Parse `event`, map mô tả, ghi `events` qua `save_event()`                                                                      | Tạo nhật ký sự kiện realtime, phục vụ UI lịch sử và thống kê                               |
| `esp32/control`         | Kênh điều khiển duy nhất từ server xuống ESP32                       | Server publish lệnh từ Web/App/AI/Automation                                                                                         | ESP32 thực thi relay/động cơ tương ứng và phản hồi trạng thái qua `esp32/sensor`         |
| `esp32/password`        | Xác thực mật khẩu keypad theo hash SHA256, không gửi plaintext        | Validate format hash, đối chiếu hash lưu DB, publish kết quả                                                                     | Trả `OK/FAIL` qua `esp32/password/result`, ghi event `PASSWORD_OK/PASSWORD_FAIL`                |
| `esp32/password/result` | Trả kết quả xác thực keypad về ESP32 ngay sau khi kiểm tra           | Server publish plain text `OK` hoặc `FAIL`                                                                                        | ESP32 quyết định mở/từ chối mở cửa và có thể kích hoạt cảnh báo                         |
| `esp32/rfid`            | Gửi UID thẻ để server xác thực tập trung                             | Normalize UID, so khớp thẻ active, xử lý init lần đầu hoặc deny                                                                | Publish JSON kết quả qua `esp32/rfid/result`, có thể mở cửa tự động                         |
| `esp32/rfid/result`     | Trả trạng thái xác thực RFID chi tiết để firmware/UI xử lý        | Server publish `status/message/uid/auto_open`                                                                                        | ESP32 hiển thị trạng thái, mở cửa khi `auto_open=true`, từ chối khi `DENY/EMPTY`           |

| Chuỗi chức năng liên topic                               | Mô tả                                                                 |
| ------------------------------------------------------------ | ----------------------------------------------------------------------- |
| `esp32/sensor` → `events`                               | Sensor tạo ngữ cảnh, server phát hiện thay đổi và ghi sự kiện |
| Client/API →`esp32/control` → `esp32/sensor`           | Điều khiển thiết bị xong sẽ phản ánh ngược về telemetry      |
| `esp32/password` ↔ `esp32/password/result`              | Handshake xác thực keypad an toàn theo hash                          |
| `esp32/rfid` ↔ `esp32/rfid/result` → `esp32/control` | Xác thực RFID xong có thể tự động mở/đóng cửa                |

---

## 3. MQTT COMMANDS (`esp32/control`)

| Command    | Mô tả                                   |
| ---------- | ----------------------------------------- |
| DOOR_OPEN  | Mở cửa                                  |
| DOOR_CLOSE | Đóng cửa                               |
| LIGHT1_ON  | Bật đèn 1                              |
| LIGHT1_OFF | Tắt đèn 1                              |
| LIGHT2_ON  | Bật đèn 2                              |
| LIGHT2_OFF | Tắt đèn 2                              |
| LIGHT3_ON  | Bật đèn 3                              |
| LIGHT3_OFF | Tắt đèn 3                              |
| LIGHT4_ON  | Bật đèn 4 (thường do PIR automation) |
| LIGHT4_OFF | Tắt đèn 4 (thường do PIR automation) |
| FAN_ON     | Bật quạt                                |
| FAN_OFF    | Tắt quạt                                |
| ROOF_OPEN  | Mở mái/rèm                             |
| ROOF_CLOSE | Đóng mái/rèm                          |

---

## 4. TẤT CẢ EVENT HỆ THỐNG

### 4.1 Event thiết bị (server suy ra từ `esp32/sensor`)

| Event       | Mô tả      |
| ----------- | ------------ |
| DOOR_OPENED | Cửa mở     |
| DOOR_CLOSED | Cửa đóng  |
| LIGHT1_ON   | Đèn 1 bật |
| LIGHT1_OFF  | Đèn 1 tắt |
| LIGHT2_ON   | Đèn 2 bật |
| LIGHT2_OFF  | Đèn 2 tắt |
| LIGHT3_ON   | Đèn 3 bật |
| LIGHT3_OFF  | Đèn 3 tắt |
| FAN_ON      | Quạt bật   |
| FAN_OFF     | Quạt tắt   |

### 4.2 Event cảm biến

| Event           | Mô tả                                |
| --------------- | -------------------------------------- |
| RAIN_DETECTED   | Phát hiện mưa                       |
| RAIN_STOPPED    | Hết mưa                              |
| MOTION_DETECTED | Phát hiện chuyển động (PIR)       |
| MOTION_STOPPED  | Không còn chuyển động             |
| FIRE_ALERT      | Cảnh báo lửa                        |
| GAS_ALERT       | Cảnh báo gas vượt ngưỡng         |
| GAS_NORMAL      | Gas trở về bình thường            |
| TEMP_CHANGE     | Nhiệt độ thay đổi vượt ngưỡng |
| HUMIDITY_CHANGE | Độ ẩm thay đổi vượt ngưỡng    |

### 4.3 Event đến từ topic `esp32/events`

| Event                | Mô tả                                      |
| -------------------- | -------------------------------------------- |
| RFID_SCAN            | Quét RFID                                   |
| BUZZER_ALARM         | Buzzer báo động                           |
| GAS_DETECTED         | ESP32 phát hiện gas                        |
| GAS_NORMAL           | ESP32 báo gas về bình thường            |
| MOTION_DETECTED      | ESP32 phát hiện chuyển động             |
| MOTION_STOPPED       | ESP32 không còn phát hiện chuyển động |
| ROOF_AUTO_CLOSE_RAIN | Mái tự động đóng do mưa               |
| ROOF_AUTO_OPEN       | Mái tự động mở khi hết mưa            |

### 4.4 Event do server xử lý xác thực

| Event                  | Mô tả                            |
| ---------------------- | ---------------------------------- |
| PASSWORD_OK            | Xác thực keypad thành công     |
| PASSWORD_FAIL          | Xác thực keypad thất bại       |
| RFID_INIT              | Khởi tạo thẻ RFID đầu tiên   |
| RFID_GRANTED           | RFID hợp lệ                      |
| RFID_DENIED            | RFID không hợp lệ               |
| RFID_EMPTY             | RFID rỗng/lỗi đọc UID          |
| DOOR_AUTO_CLOSE        | Server tự đóng cửa sau timeout |
| AUTO_LIGHT4_ON_BY_PIR  | Server tự bật đèn 4 theo PIR   |
| AUTO_LIGHT4_OFF_BY_PIR | Server tự tắt đèn 4 theo PIR   |

---

## 5. MONGODB COLLECTIONS

| Collection         | Khi nào lưu                                                |
| ------------------ | ------------------------------------------------------------ |
| sensor_data        | Định kỳ mỗi 2 phút hoặc khi có thay đổi quan trọng |
| events             | Khi gọi `save_event()`                                    |
| device_states      | Khi trạng thái thiết bị thay đổi                       |
| user_actions       | Khi user gửi lệnh từ web/voice/API                        |
| rfid_cards         | Lưu thẻ RFID đang active                                  |
| rfid_scans         | Lưu lịch sử quét RFID                                    |
| door_password      | Lưu hash mật khẩu cửa                                    |
| mobile_push_tokens | Token mobile để push cảnh báo                            |

---

## 6. LOG FORMAT

| Prefix        | Ý nghĩa                              |
| ------------- | -------------------------------------- |
| [EVENT]       | Sự kiện được lưu vào `events` |
| [SENSOR]      | Dữ liệu sensor / lưu định kỳ     |
| [MQTT]        | Kết nối, subscribe, publish MQTT     |
| [USER ACTION] | Hành động người dùng             |
| [PUSH]        | Gửi thông báo FCM                   |

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
