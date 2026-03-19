from flask import Flask, jsonify, request, render_template, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from pymongo import MongoClient
import paho.mqtt.client as mqtt
import json
from datetime import datetime, timedelta
import ssl
import os
import threading
import time
from ai_engine import SmartHomeAI
import re
import hashlib
import secrets
try:
    import certifi
except Exception:
    certifi = None
try:
    import requests
except Exception:
    requests = None
try:
    import speech_recognition as sr
except Exception:
    sr = None
try:
    import pyttsx3
except Exception:
    pyttsx3 = None

# ================== ENV FILE ==================
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")


def load_env_file(path):
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as e:
        print(f"Failed to load env file: {e}")


load_env_file(ENV_FILE)

# ================== MONGODB ==================
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/").strip()
mongo_db_name = os.getenv("MONGO_DB_NAME", "iot_db").strip() or "iot_db"
mongo_options = {
    "serverSelectionTimeoutMS": int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "30000")),
    "connectTimeoutMS": int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "20000")),
    "socketTimeoutMS": int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", "20000"))
}

if mongo_uri.startswith("mongodb+srv://") and certifi is not None:
    mongo_options["tlsCAFile"] = certifi.where()

mongo = MongoClient(mongo_uri, **mongo_options)
db = mongo[mongo_db_name]
collection_sensor = db["sensor_data"]  # Dữ liệu cảm biến định kỳ
collection_events = db["events"]  # Sự kiện quan trọng
collection_states = db["device_states"]  # Trạng thái thiết bị
collection_user_actions = db["user_actions"]  # Lịch sử điều khiển thiết bị
collection_ai_alias = db["ai_alias"]  # Alias người dùng đặt cho thiết bị
collection_device_names = db["device_names"]  # Tên hiển thị thiết bị do người dùng đặt
collection_mobile_push_tokens = db["mobile_push_tokens"]  # Token FCM từ mobile
collection_users = db["users"]  # Tài khoản đăng nhập app
collection_password_resets = db["password_resets"]  # Token quên mật khẩu cho web/app
collection_rfid_cards = db["rfid_cards"]  # Thẻ RFID hợp lệ để mở cửa
collection_rfid_scans = db["rfid_scans"]  # Lịch sử quét RFID
collection_door_password = db["door_password"]  # Mật khẩu mở cửa

# Tạo index cho truy vấn nhanh hơn
collection_sensor.create_index("timestamp")
collection_events.create_index("timestamp")
collection_events.create_index("event_type")
collection_user_actions.create_index("timestamp")
collection_mobile_push_tokens.create_index("token", unique=True)
collection_users.create_index("username", unique=True)
collection_password_resets.create_index("token_hash", unique=True)
collection_password_resets.create_index("expires_at")
collection_rfid_cards.create_index("slot", unique=True)
collection_rfid_scans.create_index("timestamp")
collection_rfid_scans.create_index("uid")
collection_door_password.create_index("slot", unique=True)

print(f"MongoDB connected: {mongo_db_name}")
try:
    mongo.admin.command("ping")
    print("MongoDB ping: OK")
except Exception as e:
    print(f"MongoDB ping failed: {e}")


def _sha256_hex(raw_text: str):
    return hashlib.sha256((raw_text or "").encode("utf-8")).hexdigest()


def _is_valid_sha256_hex(value: str):
    if not value:
        return False
    text = value.strip().lower()
    return bool(re.fullmatch(r"[0-9a-f]{64}", text))


def _normalize_rfid_uid(value: str):
    raw = (value or "").strip().upper()
    if not raw:
        return ""
    return re.sub(r"[^0-9A-F]", "", raw)


def _get_active_rfid_card():
    return collection_rfid_cards.find_one({"slot": "main"})


def _upsert_active_rfid_card(uid: str, source: str = "manual"):
    collection_rfid_cards.update_one(
        {"slot": "main"},
        {
            "$set": {
                "uid": uid,
                "source": source,
                "updated_at": datetime.now()
            },
            "$setOnInsert": {
                "created_at": datetime.now()
            }
        },
        upsert=True
    )


def _record_rfid_scan(uid: str, status: str, source: str = "esp32", data=None):
    collection_rfid_scans.insert_one({
        "timestamp": datetime.now(),
        "uid": uid,
        "status": status,
        "source": source,
        "data": data or {}
    })


def _publish_rfid_result(status: str, message: str, uid: str, auto_open=False):
    if not mqtt_client:
        return
    payload = {
        "status": status,
        "message": message,
        "uid": uid,
        "auto_open": bool(auto_open)
    }
    mqtt_client.publish(MQTT_TOPIC_RFID_RESULT, json.dumps(payload, ensure_ascii=False))


def _get_door_password_hash():
    doc = collection_door_password.find_one({"slot": "main"})
    if not doc:
        return None
    value = doc.get("pwd_sha256") or doc.get("password_hash")
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if _is_valid_sha256_hex(normalized):
        return normalized
    return None


def _set_door_password_hash(hash_value: str, source: str = "manual"):
    hash_value = (hash_value or "").strip().lower()
    collection_door_password.update_one(
        {"slot": "main"},
        {
            "$set": {
                "pwd_sha256": hash_value,
                "source": source,
                "updated_at": datetime.now()
            },
            "$setOnInsert": {
                "created_at": datetime.now()
            }
        },
        upsert=True
    )


def _open_door_with_auto_close(reason: str, extra_data=None):
    global rfid_auto_close_timer
    if not mqtt_client:
        return

    mqtt_client.publish(MQTT_TOPIC_CONTROL, "DOOR_OPEN")

    with rfid_auto_close_lock:
        if rfid_auto_close_timer:
            try:
                rfid_auto_close_timer.cancel()
            except Exception:
                pass

        def _close_later():
            try:
                if mqtt_client:
                    mqtt_client.publish(MQTT_TOPIC_CONTROL, "DOOR_CLOSE")
                    data = {
                        "reason": reason,
                        "delay_seconds": RFID_AUTO_CLOSE_SECONDS
                    }
                    if extra_data:
                        data.update(extra_data)
                    save_event(
                        "DOOR_AUTO_CLOSE",
                        f"Tự động đóng cửa sau {RFID_AUTO_CLOSE_SECONDS} giây",
                        data
                    )
            except Exception as e:
                print(f"[DOOR] Auto close error: {e}")

        rfid_auto_close_timer = threading.Timer(RFID_AUTO_CLOSE_SECONDS, _close_later)
        rfid_auto_close_timer.daemon = True
        rfid_auto_close_timer.start()


def _open_door_with_rfid_auto_close(uid: str, mode: str):
    _open_door_with_auto_close("rfid", {"uid": uid, "mode": mode})


def _handle_rfid_scan(payload: str):
    incoming_uid = ""
    source = "esp32"
    try:
        data = json.loads(payload)
        incoming_uid = _normalize_rfid_uid(data.get("uid"))
        source = (data.get("source") or "esp32").strip().lower() or "esp32"
    except Exception:
        incoming_uid = _normalize_rfid_uid(payload)
        data = {"raw": payload}

    if not incoming_uid:
        _record_rfid_scan("", "empty", source, data)
        save_event("RFID_EMPTY", "Quét RFID rỗng hoặc lỗi đọc UID", {"source": source})
        _publish_rfid_result("EMPTY", "UID RFID rong", "", auto_open=False)
        return

    active = _get_active_rfid_card()
    active_uid = _normalize_rfid_uid((active or {}).get("uid"))

    if not active_uid:
        _upsert_active_rfid_card(incoming_uid, source="first_scan")
        _record_rfid_scan(incoming_uid, "initialized", source, data)
        save_event("RFID_INIT", "Khởi tạo thẻ RFID đầu tiên", {"uid": incoming_uid, "source": source})
        _publish_rfid_result("INIT_OK", "Da khoi tao the dau tien", incoming_uid, auto_open=True)
        _open_door_with_rfid_auto_close(incoming_uid, "init")
        return

    if incoming_uid == active_uid:
        _record_rfid_scan(incoming_uid, "granted", source, data)
        save_event("RFID_GRANTED", "Xác thực RFID thành công", {"uid": incoming_uid, "source": source})
        _publish_rfid_result("OK", "RFID hop le - mo cua", incoming_uid, auto_open=True)
        _open_door_with_rfid_auto_close(incoming_uid, "granted")
        return

    _record_rfid_scan(incoming_uid, "denied", source, data)
    save_event("RFID_DENIED", "Cảnh báo: RFID không hợp lệ", {
        "uid": incoming_uid,
        "expected_uid": active_uid,
        "source": source
    })
    _publish_rfid_result("DENY", "RFID sai - tu choi", incoming_uid, auto_open=False)
    send_mobile_push_alert(
        "🚫 CẢNH BÁO RFID",
        f"Phát hiện thẻ RFID không hợp lệ: {incoming_uid}",
        {"event_type": "RFID_DENIED", "uid": incoming_uid}
    )


def ensure_default_admin_user():
    username = "admin"
    default_password_hash = _sha256_hex("123")

    existing = collection_users.find_one({"username": username})
    if existing:
        return

    collection_users.insert_one({
        "username": username,
        "pwd_sha256": default_password_hash,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "is_default": True
    })
    print("[AUTH] Created default admin account")


def ensure_default_door_password():
    existing = _get_door_password_hash()
    if existing:
        return

    print("[DOOR] Door password is not initialized yet")


ensure_default_admin_user()
ensure_default_door_password()

# ================== AI ENGINE ==================
ai_engine = SmartHomeAI(db)

# ================== FLASK ==================
app = Flask(__name__, template_folder='templates')
CORS(app)  # Cho phép CORS để web app có thể gọi API
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.getenv("APP_SECRET_KEY", "change-this-in-production"))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "1") == "1"

# ================== MQTT ==================
MQTT_BROKER = "3c5308fe02794486932d547731382984.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_TOPIC_SENSOR = "esp32/sensor"
MQTT_TOPIC_CONTROL = "esp32/control"
MQTT_TOPIC_EVENTS = "esp32/events"
MQTT_TOPIC_PASSWORD = "esp32/password"
MQTT_TOPIC_PASSWORD_RESULT = "esp32/password/result"
MQTT_TOPIC_RFID = "esp32/rfid"
MQTT_TOPIC_RFID_RESULT = "esp32/rfid/result"

latest_data = {}
mqtt_client = None
last_esp32_seen = None
ESP32_OFFLINE_SECONDS = int(os.getenv("ESP32_OFFLINE_SECONDS", "10"))
RFID_AUTO_CLOSE_SECONDS = int(os.getenv("RFID_AUTO_CLOSE_SECONDS", "10"))
rfid_auto_close_timer = None
rfid_auto_close_lock = threading.Lock()

# ================== VOICE CONTROL ==================
VOICE_ENABLED = os.getenv("VOICE_ENABLED", "1") == "1"
VOICE_LANGUAGE = os.getenv("VOICE_LANGUAGE", "vi-VN")
WAKE_WORD = "nhà ơi"
tts_engine = None
tts_lock = threading.Lock()
wake_thread_started = False
voice_priority_event = threading.Event()
wake_word_detected = False
wake_word_text = ""
wake_session_active = False
wake_response_ready = False
wake_response_text = ""

# ================== THEO DÕI TRẠNG THÁI ==================
# Lưu trạng thái trước đó để phát hiện thay đổi
previous_state = {
    "door": False,
    "light1": False,
    "light2": False,
    "light3": False,
    "fan": False,
    "rain": False,
    "flame": False,
    "pir": False,
    "gas": 0,
    "temp": 0.0,
    "hum": 0.0
}

# Thời gian lưu định kỳ
PERIODIC_SAVE_INTERVAL = 120  # 2 phút (120 giây)
last_periodic_save = datetime.now()

# Ngưỡng thay đổi để coi là sự kiện quan trọng
TEMP_CHANGE_THRESHOLD = 2.0  # Nhiệt độ thay đổi > 2°C
HUM_CHANGE_THRESHOLD = 5.0   # Độ ẩm thay đổi > 5%
GAS_CHANGE_THRESHOLD = 50    # Gas thay đổi > 50
GAS_ALERT_THRESHOLD = int(os.getenv("GAS_ALERT_THRESHOLD", "1200"))
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "").strip()
FCM_SEND_URL = "https://fcm.googleapis.com/fcm/send"
CONFIG_EVENTS_REQUIRE_ESP32 = frozenset({
    "RFID_CARD_INITIALIZED",
    "RFID_CARD_CHANGED",
    "DOOR_PASSWORD_INITIALIZED",
    "DOOR_PASSWORD_CHANGED"
})

# ===== BẮT ĐẦU CHỨC NĂNG HASH MẬT KHẨU =====
PASSWORD_HASH_COLLECTION_CANDIDATES = [
    "auth",
    "passwords",
    "settings",
    "config"
]


def _normalize_hash(value):
    if value is None:
        return None
    return str(value).strip().lower()


def _find_stored_password_hash():
    door_hash = _get_door_password_hash()
    if door_hash:
        return door_hash

    # Tìm password_hash ở các collection thường dùng trước.
    for coll_name in PASSWORD_HASH_COLLECTION_CANDIDATES:
        doc = db[coll_name].find_one({"password_hash": {"$exists": True}})
        if doc and doc.get("password_hash"):
            return _normalize_hash(doc.get("password_hash"))

    # Fallback: quét toàn bộ collection để tìm trường password_hash.
    for coll_name in db.list_collection_names():
        doc = db[coll_name].find_one({"password_hash": {"$exists": True}})
        if doc and doc.get("password_hash"):
            return _normalize_hash(doc.get("password_hash"))
    return None


def _handle_password_hash_check(payload):
    if not mqtt_client:
        return

    try:
        data = json.loads(payload)
    except Exception:
        mqtt_client.publish(MQTT_TOPIC_PASSWORD_RESULT, "FAIL")
        return

    if data.get("type") != "password_check":
        mqtt_client.publish(MQTT_TOPIC_PASSWORD_RESULT, "FAIL")
        return

    incoming_hash = _normalize_hash(data.get("hash"))
    if not _is_valid_sha256_hex(incoming_hash):
        mqtt_client.publish(MQTT_TOPIC_PASSWORD_RESULT, "FAIL")
        save_event("PASSWORD_FAIL", "Hash mật khẩu keypad không hợp lệ", {"source": "esp32/password"})
        return

    stored_hash = _find_stored_password_hash()
    is_valid = bool(incoming_hash and stored_hash and incoming_hash == stored_hash)

    mqtt_client.publish(MQTT_TOPIC_PASSWORD_RESULT, "OK" if is_valid else "FAIL")
    if is_valid:
        _open_door_with_auto_close("keypad", {"source": "esp32/password"})
    save_event(
        "PASSWORD_OK" if is_valid else "PASSWORD_FAIL",
        "Xác thực mật khẩu keypad thành công" if is_valid else "Xác thực mật khẩu keypad thất bại",
        {"source": "esp32/password"}
    )
# ===== KẾT THÚC CHỨC NĂNG HASH MẬT KHẨU =====

def on_connect(client, userdata, flags, rc):
    print("[MQTT] Connected:", rc)
    client.subscribe(MQTT_TOPIC_SENSOR)
    client.subscribe(MQTT_TOPIC_EVENTS)
    client.subscribe(MQTT_TOPIC_PASSWORD)
    client.subscribe(MQTT_TOPIC_RFID)

def save_event(event_type, description, data=None):
    """Lưu sự kiện quan trọng vào MongoDB"""
    if event_type in CONFIG_EVENTS_REQUIRE_ESP32:
        esp32 = get_esp32_status()
        if not esp32.get("connected", False):
            print(f"[EVENT] Skip save {event_type} (ESP32 offline)")
            return False

    event = {
        "timestamp": datetime.now(),
        "event_type": event_type,
        "description": description,
        "data": data or {}
    }
    collection_events.insert_one(event)
    print(f"[EVENT] {event_type}: {description}")
    return True


def _get_mobile_push_tokens():
    docs = list(
        collection_mobile_push_tokens.find(
            {},
            {"_id": 0, "token": 1}
        )
    )
    return [d.get("token", "").strip() for d in docs if d.get("token")]


def _remove_mobile_push_token(token):
    if not token:
        return
    collection_mobile_push_tokens.delete_one({"token": token})


def send_mobile_push_alert(title, body, data_payload=None):
    if not FCM_SERVER_KEY:
        print("[PUSH] Missing FCM_SERVER_KEY, skip push")
        return
    if requests is None:
        print("[PUSH] Missing requests package, skip push")
        return

    tokens = _get_mobile_push_tokens()
    if not tokens:
        print("[PUSH] No mobile tokens registered")
        return

    headers = {
        "Authorization": f"key={FCM_SERVER_KEY}",
        "Content-Type": "application/json"
    }

    for token in tokens:
        payload = {
            "to": token,
            "priority": "high",
            "notification": {
                "title": title,
                "body": body,
                "android_channel_id": "smarthome_alerts",
                "sound": "default"
            },
            "data": {
                "title": title,
                "body": body,
                **(data_payload or {})
            }
        }

        try:
            resp = requests.post(FCM_SEND_URL, headers=headers, json=payload, timeout=8)
            if resp.status_code != 200:
                print(f"[PUSH] Send failed ({resp.status_code}) for token: {token[:16]}...")
                continue

            result = resp.json() if resp.text else {}
            if result.get("failure"):
                results = result.get("results") or []
                first_error = (results[0] or {}).get("error") if results else None
                if first_error in {"InvalidRegistration", "NotRegistered"}:
                    _remove_mobile_push_token(token)
                    print(f"[PUSH] Removed invalid token: {token[:16]}...")
                else:
                    print(f"[PUSH] Failed for token {token[:16]}... error={first_error}")
        except Exception as e:
            print(f"[PUSH] Exception while sending push: {e}")

def check_and_save_changes(data):
    """Kiểm tra thay đổi và lưu sự kiện nếu có"""
    global previous_state
    has_important_change = False
    
    # Kiểm tra thay đổi trạng thái thiết bị
    if data.get("door") != previous_state["door"]:
        event_type = "DOOR_OPENED" if data.get("door") else "DOOR_CLOSED"
        save_event(event_type, f"Cửa {'mở' if data.get('door') else 'đóng'}", {"door": data.get("door")})
        has_important_change = True
    
    if data.get("light1") != previous_state["light1"]:
        event_type = "LIGHT1_ON" if data.get("light1") else "LIGHT1_OFF"
        save_event(event_type, f"Đèn 1 {'bật' if data.get('light1') else 'tắt'}", {"light1": data.get("light1")})
        has_important_change = True
    
    if data.get("light2") != previous_state["light2"]:
        event_type = "LIGHT2_ON" if data.get("light2") else "LIGHT2_OFF"
        save_event(event_type, f"Đèn 2 {'bật' if data.get('light2') else 'tắt'}", {"light2": data.get("light2")})
        has_important_change = True
    
    if data.get("light3") != previous_state["light3"]:
        event_type = "LIGHT3_ON" if data.get("light3") else "LIGHT3_OFF"
        save_event(event_type, f"Đèn 3 {'bật' if data.get('light3') else 'tắt'}", {"light3": data.get("light3")})
        has_important_change = True
    
    if data.get("fan") != previous_state["fan"]:
        event_type = "FAN_ON" if data.get("fan") else "FAN_OFF"
        save_event(event_type, f"Quạt {'bật' if data.get('fan') else 'tắt'}", {"fan": data.get("fan")})
        has_important_change = True
    
    # Kiểm tra cảnh báo
    if data.get("flame") and not previous_state["flame"]:
        save_event("FIRE_ALERT", "CẢNH BÁO: Phát hiện lửa!", {"flame": True})
        send_mobile_push_alert(
            "🚨 CẢNH BÁO CHÁY",
            "Phát hiện lửa trong nhà. Hãy kiểm tra ngay!",
            {"event_type": "FIRE_ALERT"}
        )
        has_important_change = True
    
    if data.get("rain") != previous_state["rain"]:
        event_type = "RAIN_DETECTED" if data.get("rain") else "RAIN_STOPPED"
        save_event(event_type, f"{'Phát hiện mưa' if data.get('rain') else 'Hết mưa'}", {"rain": data.get("rain")})
        has_important_change = True
    
    if data.get("pir") != previous_state["pir"]:
        event_type = "MOTION_DETECTED" if data.get("pir") else "MOTION_STOPPED"
        save_event(event_type, f"{'Phát hiện chuyển động' if data.get('pir') else 'Không còn chuyển động'}", {"pir": data.get("pir")})

        # PIR automation: server quyết định và gửi lệnh ngược về ESP32 để ESP8266 bật/tắt đèn.
        if mqtt_client:
            auto_command = "LIGHT4_ON" if data.get("pir") else "LIGHT4_OFF"
            mqtt_client.publish(MQTT_TOPIC_CONTROL, auto_command)
            save_event(
                "AUTO_LIGHT4_ON_BY_PIR" if data.get("pir") else "AUTO_LIGHT4_OFF_BY_PIR",
                "Server tự động bật đèn 4 khi phát hiện chuyển động PIR" if data.get("pir") else "Server tự động tắt đèn 4 khi không còn chuyển động PIR",
                {"command": auto_command, "source": "pir_automation"}
            )
        has_important_change = True
    
    # Kiểm tra gas vượt ngưỡng
    gas_value = data.get("gas", 0)
    if gas_value > GAS_ALERT_THRESHOLD and previous_state["gas"] <= GAS_ALERT_THRESHOLD:
        save_event("GAS_ALERT", f"CẢNH BÁO: Phát hiện gas! Giá trị: {gas_value}", {"gas": gas_value})
        send_mobile_push_alert(
            "⚠️ CẢNH BÁO GAS",
            f"Nồng độ gas nguy hiểm: {gas_value}. Hãy xử lý ngay!",
            {"event_type": "GAS_ALERT", "gas": str(gas_value)}
        )
        has_important_change = True
    elif gas_value <= GAS_ALERT_THRESHOLD and previous_state["gas"] > GAS_ALERT_THRESHOLD:
        save_event("GAS_NORMAL", f"Gas trở về bình thường. Giá trị: {gas_value}", {"gas": gas_value})
        has_important_change = True
    
    # Kiểm tra thay đổi nhiệt độ/độ ẩm đáng kể
    temp = data.get("temp", 0.0)
    hum = data.get("hum", 0.0)
    if abs(temp - previous_state["temp"]) >= TEMP_CHANGE_THRESHOLD:
        save_event("TEMP_CHANGE", f"Nhiệt độ thay đổi: {previous_state['temp']:.1f}°C → {temp:.1f}°C", 
                  {"temp": temp, "previous_temp": previous_state["temp"]})
        has_important_change = True
    
    if abs(hum - previous_state["hum"]) >= HUM_CHANGE_THRESHOLD:
        save_event("HUMIDITY_CHANGE", f"Độ ẩm thay đổi: {previous_state['hum']:.1f}% → {hum:.1f}%", 
                  {"hum": hum, "previous_hum": previous_state["hum"]})
        has_important_change = True
    
    # Cập nhật trạng thái trước đó
    previous_state = {
        "door": data.get("door", False),
        "light1": data.get("light1", False),
        "light2": data.get("light2", False),
        "light3": data.get("light3", False),
        "fan": data.get("fan", False),
        "rain": data.get("rain", False),
        "flame": data.get("flame", False),
        "pir": data.get("pir", False),
        "gas": data.get("gas", 0),
        "temp": data.get("temp", 0.0),
        "hum": data.get("hum", 0.0)
    }
    
    return has_important_change

def on_message(client, userdata, msg):
    global latest_data, last_periodic_save, last_esp32_seen
    topic = getattr(msg, "topic", "") or ""
    try:
        payload = msg.payload.decode()
        if topic in {MQTT_TOPIC_SENSOR, MQTT_TOPIC_EVENTS, MQTT_TOPIC_PASSWORD, MQTT_TOPIC_RFID}:
            last_esp32_seen = datetime.now()
        # ===== BẮT ĐẦU CHỨC NĂNG HASH MẬT KHẨU =====
        if topic == MQTT_TOPIC_PASSWORD:
            _handle_password_hash_check(payload)
            return
        if topic == MQTT_TOPIC_RFID:
            _handle_rfid_scan(payload)
            return
        # ===== KẾT THÚC CHỨC NĂNG HASH MẬT KHẨU =====

        # Xử lý topic esp32/events (RFID, KEYPAD, BUZZER, ROOF_AUTO_CLOSE_RAIN...)
        if topic == MQTT_TOPIC_EVENTS:
            try:
                ev = json.loads(payload) if payload.strip().startswith("{") else {"event": payload.strip()}
                event_type = ev.get("event", str(ev))
                desc_map = {
                    "RFID_SCAN": "Quét RFID",
                    "RFID_OPEN": "RFID mở cửa",
                    "RFID_CLOSE": "RFID đóng cửa",
                    "RFID_GRANTED": "RFID hợp lệ",
                    "RFID_DENIED": "RFID không hợp lệ",
                    "RFID_INIT": "Khởi tạo RFID lần đầu",
                    "KEYPAD_OPEN": "Keypad mở cửa (mật khẩu đúng)",
                    "KEYPAD_CLOSE": "Keypad đóng cửa",
                    "BUZZER_ALARM": "Buzzer báo động kích hoạt",
                    "MOTION_DETECTED": "Phát hiện chuyển động (PIR HC-SR501)",
                    "MOTION_STOPPED": "Không còn phát hiện chuyển động",
                    "ROOF_AUTO_CLOSE_RAIN": "Mái tự động đóng do mưa",
                    "ROOF_AUTO_OPEN": "Mái tự động mở khi hết mưa"
                }
                desc = desc_map.get(event_type, str(event_type))
                save_event(event_type, desc, ev)
            except Exception as e:
                print(f"[MQTT] Lỗi xử lý event: {e}")
            return
        # Xử lý topic esp32/sensor
        data = json.loads(payload)
        data["timestamp"] = datetime.now()
        
        # Cập nhật dữ liệu mới nhất
        latest_data = data
        
        # Kiểm tra và lưu sự kiện quan trọng
        has_change = check_and_save_changes(data)
        
        # Lưu sensor_data định kỳ mỗi 2 phút
        now = datetime.now()
        if (now - last_periodic_save).total_seconds() >= PERIODIC_SAVE_INTERVAL:
            collection_sensor.insert_one(data.copy())
            last_periodic_save = now
            print(f"[SENSOR] Lưu định kỳ lúc {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Lưu sensor_data + device_states khi có sự kiện
        if has_change:
            collection_sensor.insert_one(data.copy())
            # Lưu trạng thái thiết bị khi có thay đổi
            state_doc = {
                "timestamp": data["timestamp"],
                "door": data.get("door", False),
                "light1": data.get("light1", False),
                "light2": data.get("light2", False),
                "light3": data.get("light3", False),
                "fan": data.get("fan", False),
                "roof": data.get("roof", False)
            }
            collection_states.insert_one(state_doc)
        
        # Log khi có thay đổi
        if has_change:
            print(f"[SENSOR] Thay đổi: temp={data.get('temp')} hum={data.get('hum')} gas={data.get('gas')} "
                  f"rain={data.get('rain')} flame={data.get('flame')} pir={data.get('pir')} "
                  f"door={data.get('door')} light1={data.get('light1')} light2={data.get('light2')} "
                  f"light3={data.get('light3')} fan={data.get('fan')}")

    except Exception as e:
        print(f"Error processing MQTT message: {e}")
        import traceback
        traceback.print_exc()

def _get_env_value(name):
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip().strip('"').strip("'").strip()
    return value or None


def init_mqtt():
    global mqtt_client
    mqtt_username = _get_env_value("MQTT_USERNAME")
    mqtt_password = _get_env_value("MQTT_PASSWORD")
    if not mqtt_username or not mqtt_password:
        raise RuntimeError("Missing MQTT_USERNAME or MQTT_PASSWORD environment variable")
    mqtt_client_id = _get_env_value("MQTT_CLIENT_ID") or f"SERVER_{int(time.time())}"
    mqtt_client = mqtt.Client(client_id=mqtt_client_id)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.username_pw_set(mqtt_username, mqtt_password)
    mqtt_client.tls_set(tls_version=ssl.PROTOCOL_TLS)
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()

def log_user_action(command, source, raw_text=None):
    """Lưu lịch sử hành động của người dùng vào MongoDB"""
    esp32 = get_esp32_status()
    if not esp32.get("connected", False):
        print(f"[USER ACTION] Skip save (ESP32 offline): {command} (source={source})")
        return False

    doc = {
        "timestamp": datetime.now(),
        "command": command,
        "source": source
    }
    if raw_text:
        doc["text"] = raw_text
    collection_user_actions.insert_one(doc)
    print(f"[USER ACTION] {command} (source={source})")
    return True

def voice_listen_once():
    """Nghe một lần từ microphone và trả về text."""
    if sr is None:
        return None, "speech_recognition not available"
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.8)
            audio = recognizer.listen(source)
        text = recognizer.recognize_google(audio, language=VOICE_LANGUAGE)
        return text, None
    except sr.UnknownValueError:
        return None, "Không nghe rõ"
    except sr.RequestError:
        return None, "Lỗi kết nối Google Speech API"
    except Exception as e:
        return None, str(e)

def start_voice_listener():
    """Giữ hàm rỗng để tương thích (không chạy nền)."""
    return


# def describe_command(command):
#     cmd = (command or "").strip().upper()
#     if not cmd:
#         return "Tôi đã thực hiện lệnh"
#     if cmd == "DOOR_OPEN":
#         return "Tôi đã mở cửa"
#     if cmd == "DOOR_CLOSE":
#         return "Tôi đã đóng cửa"
#     if cmd == "FAN_ON":
#         return "Tôi đã bật quạt"
#     if cmd == "FAN_OFF":
#         return "Tôi đã tắt quạt"
#     if cmd == "ROOF_OPEN":
#         return "Tôi đã mở rèm"
#     if cmd == "ROOF_CLOSE":
#         return "Tôi đã đóng rèm"
#     if cmd.startswith("LIGHT") and cmd.endswith("_ON"):
#         light_num = cmd.replace("LIGHT", "").replace("_ON", "")
#         return f"Tôi đã bật đèn {light_num}"
#     if cmd.startswith("LIGHT") and cmd.endswith("_OFF"):
#         light_num = cmd.replace("LIGHT", "").replace("_OFF", "")
#         return f"Tôi đã tắt đèn {light_num}"
#     return f"Tôi đã thực hiện lệnh {cmd}"
def describe_command(command: str):
    def get_device_display_name(device_key: str, fallback_name: str):
        """Lấy tên thiết bị từ CSDL để AI phản hồi đúng theo tên người dùng đặt."""
        key = (device_key or "").strip().lower()
        if not key:
            return fallback_name

        # 1) Collection chuyên cho tên thiết bị (ưu tiên)
        doc = collection_device_names.find_one(
            {"device": key},
            sort=[("updated_at", -1)]
        )
        if not doc:
            doc = collection_device_names.find_one(
                {"device_key": key},
                sort=[("updated_at", -1)]
            )
        if doc:
            display_name = doc.get("display_name") or doc.get("name")
            if display_name:
                return str(display_name).strip()

        # 2) Fallback từ alias AI đã dạy (lấy alias mới nhất)
        alias_doc = collection_ai_alias.find_one(
            {"device": key, "alias": {"$exists": True, "$ne": ""}},
            sort=[("updated_at", -1)]
        )
        if alias_doc and alias_doc.get("alias"):
            return str(alias_doc.get("alias")).strip()

        return fallback_name

    if not command:
        return "Tôi không hiểu lệnh"

    command = command.upper()

    # ===== LIGHT =====
    match = re.match(r"LIGHT(\d+)_(ON|OFF)", command)
    if match:
        number = match.group(1)
        action = match.group(2)
        light_name = get_device_display_name(f"light{number}", f"đèn {number}")
        if action == "ON":
            return f"Đã bật {light_name}"
        else:
            return f"Đã tắt {light_name}"

    # ===== FAN =====
    if command == "FAN_ON":
        return f"Đã bật {get_device_display_name('fan', 'quạt')}"
    if command == "FAN_OFF":
        return f"Đã tắt {get_device_display_name('fan', 'quạt')}"

    # ===== DOOR =====
    if command == "DOOR_OPEN":
        return f"Đã mở {get_device_display_name('door', 'cửa')}"
    if command == "DOOR_CLOSE":
        return f"Đã đóng {get_device_display_name('door', 'cửa')}"

    # ===== ROOF =====
    if command == "ROOF_OPEN":
        return f"Đã mở {get_device_display_name('roof', 'mái')}"
    if command == "ROOF_CLOSE":
        return f"Đã đóng {get_device_display_name('roof', 'mái')}"

    return "Đã thực hiện lệnh"

# def speak(text):
#     if not VOICE_ENABLED:
#         return
#     if pyttsx3 is None:
#         return
#     global tts_engine
#     with tts_lock:
#         if tts_engine is None:
#             try:
#                 tts_engine = pyttsx3.init()
#             except Exception:
#                 tts_engine = None
#                 return
#         try:
#             tts_engine.say(text)
#             tts_engine.runAndWait()
#         except Exception:
#             return

def speak(text):
    if not VOICE_ENABLED or pyttsx3 is None:
        return

    def _speak():
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print("TTS error:", e)

    t = threading.Thread(target=_speak)
    t.start()


def listen_for_wake_word():
    global wake_word_detected, wake_word_text
    global wake_session_active, wake_response_ready, wake_response_text

    if not VOICE_ENABLED or sr is None:
        print("Voice disabled or speech_recognition not available")
        return

    recognizer = sr.Recognizer()
    print("Wake word listener started...")

    while True:
        if voice_priority_event.is_set():
            time.sleep(0.1)
            continue

        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.8)
                print("Listening for wake word...")
                audio = recognizer.listen(source)

            heard = recognizer.recognize_google(audio, language=VOICE_LANGUAGE)
            print("Heard wake:", heard)

        except Exception as e:
            print("Wake error:", e)
            continue

        if not heard:
            continue

        if WAKE_WORD not in heard.strip().lower():
            continue

        # ===== Wake word detected =====
        print("Wake word detected!")
        wake_word_detected = True
        wake_word_text = WAKE_WORD
        wake_session_active = True
        wake_response_ready = False
        wake_response_text = ""

        speak("Nhà đây bạn cần gì")

        # ===== Listen for command =====
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.6)
                print("Listening for command...")
                cmd_audio = recognizer.listen(source)

            cmd_text = recognizer.recognize_google(cmd_audio, language=VOICE_LANGUAGE)
            print("Command heard:", cmd_text)

        except Exception as e:
            print("Command error:", e)
            response = "Tôi không hiểu lệnh"
            speak(response)
            wake_response_text = response
            wake_response_ready = True
            wake_session_active = False
            continue

        if not cmd_text:
            response = "Tôi không hiểu lệnh"
            speak(response)
            wake_response_text = response
            wake_response_ready = True
            wake_session_active = False
            continue

        # ===== Process AI =====
        command = ai_engine.process_command(cmd_text)
        print("AI parsed command:", command)

        if not command:
            response = "Tôi không hiểu lệnh"
            speak(response)
            wake_response_text = response
            wake_response_ready = True
            wake_session_active = False
            continue

        # ===== Publish MQTT =====
        if mqtt_client:
            result = mqtt_client.publish(MQTT_TOPIC_CONTROL, command)
            log_user_action(command, "wake_word", raw_text=cmd_text)

            if getattr(result, "rc", None) == mqtt.MQTT_ERR_SUCCESS:
                response = describe_command(command)
                print("MQTT sent successfully")
            else:
                response = "Tôi chưa gửi được lệnh"
                print("MQTT send failed")

        else:
            response = "MQTT chưa kết nối"
            print("MQTT client is None")

        speak(response)
        wake_response_text = response
        wake_response_ready = True
        wake_session_active = False

        time.sleep(1)


def start_wake_word_listener():
    global wake_thread_started
    if not VOICE_ENABLED:
        return
    if wake_thread_started:
        return
    wake_thread_started = True
    thread = threading.Thread(target=listen_for_wake_word, daemon=True)
    thread.start()

def ai_periodic_learn():
    """Chạy nền: retrain + learn mỗi giờ"""
    while True:
        time.sleep(3600)  # 1 giờ
        try:
            ai_engine.retrain_model_if_needed()
            ai_engine.learn_from_sensor_behavior()
            ai_engine.learn_patterns()
        except Exception as e:
            print(f"[AI] Periodic learn error: {e}")

def start_ai_periodic_learn():
    t = threading.Thread(target=ai_periodic_learn, daemon=True)
    t.start()

# ================== API ROUTES ==================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/history")
def history_page():
    return render_template("history.html")


@app.route("/rfid")
def rfid_page():
    return render_template("rfid.html")


@app.route("/door-password/manage")
def door_password_page():
    return render_template("door_password.html")


def _get_device_name_map():
    """Lấy map tên thiết bị từ MongoDB: {device_key: display_name}."""
    docs = list(
        collection_device_names.find(
            {},
            {"_id": 0, "device": 1, "display_name": 1}
        )
    )
    result = {}
    for d in docs:
        key = _normalize_device_key(d.get("device"))
        name = (d.get("display_name") or "").strip()
        if key and name:
            result[key] = name
    return result

@app.route("/sensor/latest")
def get_latest():
    device_names = _get_device_name_map()
    esp32 = get_esp32_status()
    if latest_data:
        data = latest_data.copy()
        if "_id" in data:
            data["_id"] = str(data["_id"])
        if "timestamp" in data:
            data["timestamp"] = str(data["timestamp"])
        data["device_names"] = device_names
        data["esp32_connected"] = esp32["connected"]
        data["esp32_last_seen"] = esp32["last_seen"]
        data["esp32_age_seconds"] = esp32["age_seconds"]
        data["esp32_offline_timeout_seconds"] = esp32["offline_timeout_seconds"]
        data["esp32_status_message"] = esp32["message"]
        return jsonify(data)
    return jsonify({
        "message": "No data",
        "device_names": device_names,
        "esp32_connected": esp32["connected"],
        "esp32_last_seen": esp32["last_seen"],
        "esp32_age_seconds": esp32["age_seconds"],
        "esp32_offline_timeout_seconds": esp32["offline_timeout_seconds"],
        "esp32_status_message": esp32["message"]
    })


@app.route("/mobile/bootstrap")
def mobile_bootstrap():
    """Trả dữ liệu khởi tạo cho mobile: sensor mới nhất + tên thiết bị."""
    esp32 = get_esp32_status()
    payload = {
        "device_names": _get_device_name_map(),
        "esp32": esp32
    }
    if latest_data:
        sensor = latest_data.copy()
        if "_id" in sensor:
            sensor["_id"] = str(sensor["_id"])
        if "timestamp" in sensor:
            sensor["timestamp"] = str(sensor["timestamp"])
        payload["sensor"] = sensor
    else:
        payload["sensor"] = {}
        payload["message"] = "No data"
    return jsonify(payload)


@app.route("/mobile/register-token", methods=["POST"])
def register_mobile_token():
    data = request.json or {}
    token = (data.get("token") or "").strip()
    platform = (data.get("platform") or "android").strip().lower()
    username = _normalize_username(data.get("username"))

    if not token:
        return jsonify({"success": False, "error": "token là bắt buộc"}), 400

    collection_mobile_push_tokens.update_one(
        {"token": token},
        {
            "$set": {
                "platform": platform,
                "username": username,
                "updated_at": datetime.now()
            },
            "$setOnInsert": {
                "created_at": datetime.now()
            }
        },
        upsert=True
    )

    uname_log = username or "(none)"
    print(f"[PUSH] Registered token: {token[:16]}... platform={platform} username={uname_log}")

    return jsonify({"success": True})


# ================== RFID ROUTES ==================

@app.route("/rfid/card", methods=["GET"])
def get_rfid_card():
    card = _get_active_rfid_card() or {}
    uid = _normalize_rfid_uid(card.get("uid"))
    return jsonify({
        "success": True,
        "is_initialized": bool(uid),
        "uid": uid,
        "source": card.get("source"),
        "updated_at": str(card.get("updated_at")) if card.get("updated_at") else None
    })


@app.route("/rfid/card", methods=["POST"])
def upsert_rfid_card():
    offline_response = require_esp32_connection()
    if offline_response:
        return offline_response

    data = request.json or {}
    new_uid = _normalize_rfid_uid(data.get("new_uid"))
    old_uid = _normalize_rfid_uid(data.get("old_uid"))

    if not new_uid:
        return jsonify({"success": False, "error": "new_uid là bắt buộc"}), 400

    active = _get_active_rfid_card() or {}
    active_uid = _normalize_rfid_uid(active.get("uid"))

    if active_uid and old_uid != active_uid:
        return jsonify({"success": False, "error": "Mã thẻ cũ không đúng"}), 401

    mode = "initialize" if not active_uid else "change"
    _upsert_active_rfid_card(new_uid, source="manual")

    save_event(
        "RFID_CARD_INITIALIZED" if mode == "initialize" else "RFID_CARD_CHANGED",
        "Khởi tạo mã thẻ RFID từ giao diện" if mode == "initialize" else "Đổi mã thẻ RFID từ giao diện",
        {
            "mode": mode,
            "new_uid": new_uid
        }
    )

    return jsonify({
        "success": True,
        "mode": mode,
        "uid": new_uid
    })


@app.route("/rfid/scans", methods=["GET"])
def get_rfid_scans():
    limit = request.args.get("limit", 30, type=int)
    limit = max(1, min(limit, 200))

    docs = list(collection_rfid_scans.find({}).sort("timestamp", -1).limit(limit))
    items = []
    for d in docs:
        items.append({
            "timestamp": str(d.get("timestamp")) if d.get("timestamp") else None,
            "uid": d.get("uid", ""),
            "status": d.get("status", ""),
            "source": d.get("source", ""),
            "data": d.get("data", {})
        })

    return jsonify({
        "success": True,
        "count": len(items),
        "items": items
    })


@app.route("/door-password", methods=["GET"])
def get_door_password_info():
    hash_value = _get_door_password_hash()
    doc = collection_door_password.find_one({"slot": "main"}) or {}
    return jsonify({
        "success": True,
        "is_initialized": bool(hash_value),
        "source": doc.get("source"),
        "updated_at": str(doc.get("updated_at")) if doc.get("updated_at") else None
    })


@app.route("/door-password", methods=["POST"])
def update_door_password():
    offline_response = require_esp32_connection()
    if offline_response:
        return offline_response

    data = request.json or {}
    old_hash = _resolve_password_hash(data, "old_password", "old_password_hash")
    new_hash = _resolve_password_hash(data, "new_password", "new_password_hash")

    if not new_hash:
        return jsonify({"success": False, "error": "new_password/new_password_hash là bắt buộc"}), 400

    if not _is_valid_sha256_hex(new_hash):
        return jsonify({"success": False, "error": "Mật khẩu mới không hợp lệ"}), 400

    current_hash = _get_door_password_hash()
    if current_hash and old_hash != current_hash:
        return jsonify({"success": False, "error": "Mật khẩu cũ không đúng"}), 401

    mode = "initialize" if not current_hash else "change"
    _set_door_password_hash(new_hash, source="manual")

    save_event(
        "DOOR_PASSWORD_INITIALIZED" if mode == "initialize" else "DOOR_PASSWORD_CHANGED",
        "Khởi tạo mật khẩu cửa" if mode == "initialize" else "Đổi mật khẩu cửa",
        {"mode": mode}
    )

    return jsonify({"success": True, "mode": mode})


@app.route("/door/open-by-password", methods=["POST"])
def open_door_by_password():
    offline_response = require_esp32_connection()
    if offline_response:
        return offline_response

    data = request.json or {}
    incoming_hash = _resolve_password_hash(data, "password", "password_hash")
    if not incoming_hash:
        return jsonify({"success": False, "error": "password/password_hash là bắt buộc"}), 400

    if not _is_valid_sha256_hex(incoming_hash):
        return jsonify({"success": False, "error": "password_hash không hợp lệ"}), 400

    stored_hash = _find_stored_password_hash()
    if not stored_hash or incoming_hash != stored_hash:
        save_event("PASSWORD_FAIL", "Mở cửa bằng mật khẩu thất bại", {"source": "mobile/web"})
        return jsonify({"success": False, "error": "Mật khẩu không đúng"}), 401

    _open_door_with_auto_close("password_ui", {"source": "mobile/web"})
    save_event("PASSWORD_OK", "Mở cửa bằng mật khẩu thành công", {"source": "mobile/web"})
    return jsonify({
        "success": True,
        "message": f"Mở cửa thành công, sẽ tự đóng sau {RFID_AUTO_CLOSE_SECONDS} giây"
    })

@app.route("/sensor/history")
def get_history():
    """Lấy lịch sử dữ liệu cảm biến, có thể lọc theo giờ/ngày/tháng/năm."""
    period = (request.args.get("period") or "").strip().lower()
    value = (request.args.get("value") or "").strip()
    limit = request.args.get("limit", 200, type=int)
    limit = max(1, min(limit, 5000))

    def build_time_range(selected_period: str, selected_value: str):
        try:
            if selected_period == "hour":
                start_time = datetime.strptime(selected_value, "%Y-%m-%dT%H")
                end_time = start_time + timedelta(hours=1)
            elif selected_period == "day":
                start_time = datetime.strptime(selected_value, "%Y-%m-%d")
                end_time = start_time + timedelta(days=1)
            elif selected_period == "month":
                start_time = datetime.strptime(selected_value, "%Y-%m")
                if start_time.month == 12:
                    end_time = datetime(start_time.year + 1, 1, 1)
                else:
                    end_time = datetime(start_time.year, start_time.month + 1, 1)
            elif selected_period == "year":
                start_time = datetime.strptime(selected_value, "%Y")
                end_time = datetime(start_time.year + 1, 1, 1)
            else:
                return None, None
            return start_time, end_time
        except ValueError:
            return None, None

    query = {}
    if period or value:
        if not period or not value:
            return jsonify({
                "success": False,
                "error": "Cần truyền đủ period và value để lọc dữ liệu"
            }), 400

        if period not in {"hour", "day", "month", "year"}:
            return jsonify({
                "success": False,
                "error": "period chỉ nhận: hour, day, month, year"
            }), 400

        start_time, end_time = build_time_range(period, value)
        if not start_time or not end_time:
            return jsonify({
                "success": False,
                "error": "Giá trị value không đúng định dạng cho period đã chọn"
            }), 400

        query["timestamp"] = {
            "$gte": start_time,
            "$lt": end_time
        }

    data = list(
        collection_sensor.find(query).sort("timestamp", -1).limit(limit)
    )

    for d in data:
        d["_id"] = str(d["_id"])
        d["timestamp"] = str(d["timestamp"])

    return jsonify({
        "success": True,
        "period": period or None,
        "value": value or None,
        "count": len(data),
        "data": data
    })

@app.route("/events")
def get_events():
    """Lấy danh sách sự kiện quan trọng"""
    limit = request.args.get("limit", 50, type=int)
    event_type = request.args.get("type", None)
    
    query = {}
    if event_type:
        query["event_type"] = event_type
    
    data = list(collection_events.find(query).sort("timestamp", -1).limit(limit))
    for d in data:
        d["_id"] = str(d["_id"])
        d["timestamp"] = str(d["timestamp"])
    return jsonify(data)

@app.route("/events/stats")
def get_event_stats():
    """Thống kê sự kiện"""
    pipeline = [
        {
            "$group": {
                "_id": "$event_type",
                "count": {"$sum": 1},
                "last_occurrence": {"$max": "$timestamp"}
            }
        },
        {"$sort": {"count": -1}}
    ]
    stats = list(collection_events.aggregate(pipeline))
    for s in stats:
        s["last_occurrence"] = str(s["last_occurrence"])
    return jsonify(stats)

@app.route("/states/latest")
def get_latest_state():
    """Lấy trạng thái thiết bị mới nhất"""
    state = collection_states.find_one(sort=[("timestamp", -1)])
    if state:
        state["_id"] = str(state["_id"])
        state["timestamp"] = str(state["timestamp"])
    return jsonify(state or {})


def _normalize_device_key(device: str):
    return (device or "").strip().lower()


def get_esp32_status():
    if not last_esp32_seen:
        return {
            "connected": False,
            "last_seen": None,
            "offline_timeout_seconds": ESP32_OFFLINE_SECONDS,
            "age_seconds": None,
            "message": "Chưa nhận dữ liệu từ ESP32"
        }

    age_seconds = (datetime.now() - last_esp32_seen).total_seconds()
    connected = age_seconds <= ESP32_OFFLINE_SECONDS

    return {
        "connected": connected,
        "last_seen": str(last_esp32_seen),
        "offline_timeout_seconds": ESP32_OFFLINE_SECONDS,
        "age_seconds": round(age_seconds, 1),
        "message": "ESP32 đã kết nối" if connected else "ESP32 không phản hồi"
    }


def require_esp32_connection():
    status = get_esp32_status()
    if status["connected"]:
        return None
    return jsonify({
        "success": False,
        "error": "ESP32 không kết nối, không thể điều khiển",
        "esp32": status
    }), 503


def _normalize_username(username: str):
    return (username or "").strip().lower()


def _resolve_password_hash(payload: dict, password_field: str, hash_field: str):
    incoming_hash = (payload.get(hash_field) or "").strip().lower()
    if _is_valid_sha256_hex(incoming_hash):
        return incoming_hash

    raw_password = (payload.get(password_field) or "")
    if raw_password:
        return _sha256_hex(raw_password)

    return None


def _hash_reset_token(token: str):
    return _sha256_hex(token or "")


def _is_session_authenticated():
    return bool(session.get("auth_user"))


def _get_auth_user():
    return (session.get("auth_user") or "").strip().lower()


def _is_authorized_request():
    if _is_session_authenticated():
        return True

    auth_header = (request.headers.get("Authorization") or "").strip()
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = (request.headers.get("X-Auth-Token") or "").strip()
    if not token:
        return False

    token_hash = _hash_reset_token(token)
    now = datetime.now()
    user = collection_users.find_one({
        "api_token_hash": token_hash,
        "api_token_expires_at": {"$gt": now}
    })
    if not user:
        return False

    session["auth_user"] = user.get("username")
    session["auth_at"] = now.isoformat()
    return True


def _is_public_route(path: str):
    public_exact = {
        "/login",
        "/register",
        "/forgot-password",
        "/reset-password",
        "/logout",
        "/favicon.ico"
    }
    if path in public_exact:
        return True

    public_prefixes = (
        "/auth/",
        "/mobile/",
        "/static/"
    )
    return path.startswith(public_prefixes)


@app.before_request
def enforce_authentication():
    path = request.path or "/"
    if _is_public_route(path):
        return None

    if _is_authorized_request():
        return None

    if path.startswith("/api/") or request.method in {"POST", "PUT", "PATCH", "DELETE"} or request.is_json:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    return redirect(url_for("login_page", next=path))


def _issue_api_token_for_user(username: str):
    token = secrets.token_urlsafe(32)
    token_hash = _hash_reset_token(token)
    expire_at = datetime.now() + timedelta(days=7)
    collection_users.update_one(
        {"username": username},
        {"$set": {
            "api_token_hash": token_hash,
            "api_token_expires_at": expire_at,
            "updated_at": datetime.now()
        }}
    )
    return token, expire_at


# ================== AUTH ROUTES ==================

@app.route("/login")
def login_page():
    if _is_session_authenticated():
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/register")
def register_page():
    if _is_session_authenticated():
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/forgot-password")
def forgot_password_page():
    if _is_session_authenticated():
        return redirect(url_for("index"))
    return render_template("forgot_password.html")


@app.route("/reset-password")
def reset_password_page():
    if _is_session_authenticated():
        return redirect(url_for("index"))
    return render_template("reset_password.html")


@app.route("/logout", methods=["GET", "POST"])
def auth_logout_web():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/auth/register", methods=["POST"])
def auth_register():
    data = request.json or {}
    username = _normalize_username(data.get("username"))
    password_hash = _resolve_password_hash(data, "password", "password_hash")
    recovery_answer = (data.get("recovery_answer") or "").strip()
    recovery_hash = _sha256_hex(recovery_answer) if recovery_answer else None

    if not username:
        return jsonify({"success": False, "error": "username là bắt buộc"}), 400
    if not password_hash:
        return jsonify({"success": False, "error": "password hoặc password_hash là bắt buộc"}), 400

    if collection_users.find_one({"username": username}):
        return jsonify({"success": False, "error": "Tài khoản đã tồn tại"}), 409

    collection_users.insert_one({
        "username": username,
        "pwd_sha256": password_hash,
        "recovery_hash": recovery_hash,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    })

    return jsonify({"success": True, "username": username})


@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.json or {}
    username = _normalize_username(data.get("username"))
    password_hash = _resolve_password_hash(data, "password", "password_hash")

    if not username or not password_hash:
        return jsonify({"success": False, "error": "username và password/password_hash là bắt buộc"}), 400

    user = collection_users.find_one({"username": username})
    if not user or user.get("pwd_sha256") != password_hash:
        return jsonify({"success": False, "error": "Sai tài khoản hoặc mật khẩu"}), 401

    now = datetime.now()
    session["auth_user"] = username
    session["auth_at"] = now.isoformat()
    token, expire_at = _issue_api_token_for_user(username)

    return jsonify({
        "success": True,
        "username": username,
        "api_token": token,
        "api_token_expires_at": expire_at.isoformat()
    })


@app.route("/auth/me", methods=["GET"])
def auth_me():
    if not _is_authorized_request():
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    return jsonify({"success": True, "username": _get_auth_user()})


@app.route("/auth/change-password", methods=["POST"])
def auth_change_password():
    data = request.json or {}
    username = _normalize_username(data.get("username"))
    old_password_hash = _resolve_password_hash(data, "old_password", "old_password_hash")
    new_password_hash = _resolve_password_hash(data, "new_password", "new_password_hash")

    if not username or not old_password_hash or not new_password_hash:
        return jsonify({"success": False, "error": "Thiếu username hoặc mật khẩu cũ/mới"}), 400

    user = collection_users.find_one({"username": username})
    if not user or user.get("pwd_sha256") != old_password_hash:
        return jsonify({"success": False, "error": "Mật khẩu cũ không đúng"}), 401

    collection_users.update_one(
        {"username": username},
        {"$set": {"pwd_sha256": new_password_hash, "updated_at": datetime.now()}}
    )

    return jsonify({"success": True, "username": username})


@app.route("/auth/forgot-password", methods=["POST"])
def auth_forgot_password():
    data = request.json or {}
    username = _normalize_username(data.get("username"))
    recovery_answer = (data.get("recovery_answer") or "").strip()

    if not username or not recovery_answer:
        return jsonify({"success": False, "error": "Thiếu username hoặc recovery_answer"}), 400

    user = collection_users.find_one({"username": username})
    if not user:
        return jsonify({"success": False, "error": "Không tìm thấy tài khoản"}), 404

    stored_recovery_hash = (user.get("recovery_hash") or "").strip().lower()
    if not stored_recovery_hash:
        return jsonify({
            "success": False,
            "error": "Tài khoản chưa có recovery_answer, hãy đổi mật khẩu khi đang đăng nhập"
        }), 400

    if stored_recovery_hash != _sha256_hex(recovery_answer):
        return jsonify({"success": False, "error": "Recovery answer không đúng"}), 401

    reset_token = secrets.token_urlsafe(24)
    token_hash = _hash_reset_token(reset_token)
    expire_at = datetime.now() + timedelta(minutes=15)

    collection_password_resets.update_one(
        {"username": username},
        {
            "$set": {
                "token_hash": token_hash,
                "expires_at": expire_at,
                "used": False,
                "updated_at": datetime.now()
            },
            "$setOnInsert": {
                "created_at": datetime.now()
            }
        },
        upsert=True
    )

    return jsonify({
        "success": True,
        "username": username,
        "reset_token": reset_token,
        "expires_at": expire_at.isoformat()
    })


@app.route("/auth/reset-password", methods=["POST"])
def auth_reset_password():
    data = request.json or {}
    username = _normalize_username(data.get("username"))
    reset_token = (data.get("reset_token") or "").strip()
    new_password_hash = _resolve_password_hash(data, "new_password", "new_password_hash")

    if not username or not reset_token or not new_password_hash:
        return jsonify({"success": False, "error": "Thiếu username, reset_token hoặc mật khẩu mới"}), 400

    record = collection_password_resets.find_one({"username": username})
    if not record:
        return jsonify({"success": False, "error": "Không có yêu cầu reset hợp lệ"}), 404

    if record.get("used"):
        return jsonify({"success": False, "error": "Reset token đã được sử dụng"}), 400

    expires_at = record.get("expires_at")
    if not expires_at or expires_at <= datetime.now():
        return jsonify({"success": False, "error": "Reset token đã hết hạn"}), 400

    if record.get("token_hash") != _hash_reset_token(reset_token):
        return jsonify({"success": False, "error": "Reset token không đúng"}), 401

    collection_users.update_one(
        {"username": username},
        {"$set": {"pwd_sha256": new_password_hash, "updated_at": datetime.now()}}
    )

    collection_password_resets.update_one(
        {"username": username},
        {"$set": {"used": True, "used_at": datetime.now(), "updated_at": datetime.now()}}
    )

    return jsonify({"success": True, "username": username})


# ================== DEVICE NAME ROUTES ==================

@app.route("/devices/names", methods=["GET"])
def get_device_names():
    """Lấy danh sách tên thiết bị do người dùng đặt."""
    docs = list(collection_device_names.find({}, {"_id": 0, "device": 1, "display_name": 1, "updated_at": 1}))
    # Chuẩn hóa output cho client
    items = []
    for d in docs:
        items.append({
            "device": d.get("device"),
            "display_name": d.get("display_name"),
            "updated_at": str(d.get("updated_at")) if d.get("updated_at") else None
        })
    return jsonify({"success": True, "items": items, "map": _get_device_name_map()})


@app.route("/devices/names", methods=["POST"])
def upsert_device_name():
    """Lưu/cập nhật tên thiết bị để AI đọc theo tên người dùng đặt."""
    data = request.json or {}
    device = _normalize_device_key(data.get("device"))
    display_name = (data.get("display_name") or "").strip()

    if not device or not display_name:
        return jsonify({"error": "device và display_name là bắt buộc"}), 400

    collection_device_names.update_one(
        {"device": device},
        {
            "$set": {
                "display_name": display_name,
                "updated_at": datetime.now()
            },
            "$setOnInsert": {
                "created_at": datetime.now()
            }
        },
        upsert=True
    )

    return jsonify({
        "success": True,
        "item": {
            "device": device,
            "display_name": display_name
        }
    })

# ================== AI ROUTES ==================

@app.route("/ai/teach-intent", methods=["POST"])
def ai_teach_intent():
    """Dạy AI câu lệnh custom"""
    data = request.json or {}
    trigger = data.get("trigger", "").strip()
    action = data.get("action", "").strip()
    if not trigger or not action:
        return jsonify({"error": "trigger và action là bắt buộc"}), 400
    result = ai_engine.teach_intent(trigger, action)
    return jsonify({"success": True, "result": result})

@app.route("/ai/teach-alias", methods=["POST"])
def ai_teach_alias():
    """Dạy AI từ đồng nghĩa cho thiết bị"""
    data = request.json or {}
    alias = data.get("alias", "").strip()
    device = data.get("device", "").strip()
    if not alias or not device:
        return jsonify({"error": "alias và device là bắt buộc"}), 400
    result = ai_engine.teach_alias(alias, device)
    return jsonify({"success": True, "result": result})

@app.route("/ai/teach-rule", methods=["POST"])
def ai_teach_rule():
    """Dạy AI luật tự động"""
    data = request.json or {}
    condition = data.get("condition", "").strip()
    action = data.get("action", "").strip()
    if not condition or not action:
        return jsonify({"error": "condition và action là bắt buộc"}), 400
    result = ai_engine.teach_rule(condition, action)
    return jsonify({"success": True, "result": result})

@app.route("/ai/process", methods=["POST"])
def ai_process():
    """Xử lý text từ client, publish MQTT và trả câu phản hồi để client đọc."""
    offline_response = require_esp32_connection()
    if offline_response:
        return offline_response

    data = request.json or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text là bắt buộc"}), 400

    command = ai_engine.process_command(text)
    if not command:
        print(f"[AI] Text='{text}' => no command")
        return jsonify({
            "success": False,
            "message": "Không tìm thấy lệnh phù hợp",
            "response_text": "Tôi không hiểu lệnh"
        })

    if mqtt_client:
        mqtt_client.publish(MQTT_TOPIC_CONTROL, command)
        log_user_action(command, "ai/process", raw_text=text)
        response_text = describe_command(command)
        print(f"[AI] Text='{text}' => command={command}")
        return jsonify({
            "success": True,
            "text": text,
            "command": command,
            "response_text": response_text
        })

    return jsonify({"error": "MQTT not connected"}), 500


@app.route("/ai/wake", methods=["POST"])
def ai_wake():
    """Server xử lý wake-word và trả câu phản hồi để mobile đọc."""
    data = request.json or {}
    text = (data.get("text") or "nhà ơi").strip()

    sensor_snapshot = latest_data.copy() if latest_data else {}
    context = ai_engine.detect_context(sensor_snapshot)

    if context.get("fire"):
        response_text = "Nhà đây. Cảnh báo, đang phát hiện lửa. Bạn cần tôi làm gì?"
    elif context.get("gas_alert"):
        response_text = "Nhà đây. Cảnh báo khí gas đang cao, bạn cần tôi làm gì?"
    else:
        response_text = "Nhà đây bạn cần gì"

    return jsonify({
        "success": True,
        "text": text,
        "response_text": response_text,
        "context": context
    })

@app.route("/ai/learn", methods=["POST"])
def ai_learn():
    """Học từ user_actions + sensor_data và patterns giờ"""
    try:
        r1 = ai_engine.learn_from_sensor_behavior()
        r2 = ai_engine.learn_patterns()
        return jsonify({
            "success": True,
            "sensor_behavior": r1,
            "patterns": r2
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/ai/retrain", methods=["POST"])
def ai_retrain():
    """Retrain model nếu cần (new intents >= 5 hoặc > 24h)"""
    try:
        payload = request.get_json(silent=True) or {}
        force = bool(payload.get("force", False))
        ok = ai_engine.retrain_model_if_needed(force=force)
        return jsonify({"success": True, "retrained": ok, "force": force})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/ai/context")
def ai_context():
    """Lấy ngữ cảnh từ sensor_data mới nhất"""
    data = latest_data.copy() if latest_data else {}
    context = ai_engine.detect_context(data)
    return jsonify({"context": context, "sensor": data})

@app.route("/voice/once", methods=["POST"])
def voice_once():
    """Thu âm một lần trên server (cho web) và xử lý bằng AI."""
    offline_response = require_esp32_connection()
    if offline_response:
        return offline_response

    if not VOICE_ENABLED:
        return jsonify({"success": False, "message": "Voice đang tắt trên server"}), 503

    voice_priority_event.set()
    try:
        text, err = voice_listen_once()
        if err:
            return jsonify({"success": False, "message": err})
        if not text:
            return jsonify({"success": False, "message": "Không nghe rõ"})

        command = ai_engine.process_command(text)
        if not command:
            return jsonify({
                "success": False,
                "text": text,
                "message": "Không nhận diện được lệnh",
                "response_text": "Tôi không hiểu lệnh"
            })

        if not mqtt_client:
            return jsonify({
                "success": False,
                "text": text,
                "message": "MQTT chưa kết nối"
            }), 500

        result = mqtt_client.publish(MQTT_TOPIC_CONTROL, command)
        if getattr(result, "rc", None) != mqtt.MQTT_ERR_SUCCESS:
            return jsonify({
                "success": False,
                "text": text,
                "message": "Gửi lệnh MQTT thất bại"
            }), 500

        log_user_action(command, "voice_once", raw_text=text)
        response_text = describe_command(command)
        return jsonify({
            "success": True,
            "text": text,
            "command": command,
            "response_text": response_text
        })
    finally:
        voice_priority_event.clear()


@app.route("/voice/status")
def voice_status():
    global wake_word_detected, wake_word_text
    global wake_response_ready, wake_response_text
    global wake_session_active

    detected = bool(wake_word_detected)
    detected_text = wake_word_text if wake_word_detected else ""
    response_ready = bool(wake_response_ready)
    response_text = wake_response_text if wake_response_ready else ""

    # Trả event 1 lần cho UI web, tránh lặp hiển thị.
    if wake_word_detected:
        wake_word_detected = False
        wake_word_text = ""
    if wake_response_ready:
        wake_response_ready = False
        wake_response_text = ""

    return jsonify({
        "wake_word": detected,
        "text": detected_text,
        "active": bool(wake_session_active),
        "response_ready": response_ready,
        "response_text": response_text,
        "message": "Wake-word listener đang hoạt động" if VOICE_ENABLED else "Voice đang tắt trên server"
    })

# ================== CONTROL ROUTES ==================

@app.route("/control/door", methods=["POST"])
def control_door():
    try:
        offline_response = require_esp32_connection()
        if offline_response:
            return offline_response

        data = request.json
        action = data.get("action", "").upper()
        
        if action == "OPEN":
            command = "DOOR_OPEN"
        elif action == "CLOSE":
            command = "DOOR_CLOSE"
        else:
            return jsonify({"error": "Invalid action"}), 400
        
        if mqtt_client:
            mqtt_client.publish(MQTT_TOPIC_CONTROL, command)
            print(f"[MQTT] Gửi command: {command}")
            log_user_action(command, "control/door")
            return jsonify({"success": True, "command": command})
        else:
            return jsonify({"error": "MQTT not connected"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/control/light", methods=["POST"])
def control_light():
    try:
        offline_response = require_esp32_connection()
        if offline_response:
            return offline_response

        data = request.json
        light_num = data.get("light", 1)
        state = data.get("state", False)
        
        command = f"LIGHT{light_num}_{'ON' if state else 'OFF'}"
        
        if mqtt_client:
            mqtt_client.publish(MQTT_TOPIC_CONTROL, command)
            print(f"[MQTT] Gửi command: {command}")
            log_user_action(command, "control/light")
            return jsonify({"success": True, "command": command})
        else:
            return jsonify({"error": "MQTT not connected"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/control/fan", methods=["POST"])
def control_fan():
    try:
        offline_response = require_esp32_connection()
        if offline_response:
            return offline_response

        data = request.json
        state = data.get("state", False)
        
        command = "FAN_ON" if state else "FAN_OFF"
        
        if mqtt_client:
            mqtt_client.publish(MQTT_TOPIC_CONTROL, command)
            print(f"[MQTT] Gửi command: {command}")
            log_user_action(command, "control/fan")
            return jsonify({"success": True, "command": command})
        else:
            return jsonify({"error": "MQTT not connected"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/control/roof", methods=["POST"])
def control_roof():
    try:
        offline_response = require_esp32_connection()
        if offline_response:
            return offline_response

        data = request.json
        state = data.get("state", False)
        command = "ROOF_OPEN" if state else "ROOF_CLOSE"
        
        if mqtt_client:
            mqtt_client.publish(MQTT_TOPIC_CONTROL, command)
            print(f"[MQTT] Gửi command: {command}")
            log_user_action(command, "control/roof")
            return jsonify({"success": True, "command": command})
        else:
            return jsonify({"error": "MQTT not connected"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ================== RUN ==================
if __name__ == "__main__":
    print("Initializing MQTT...")
    init_mqtt()
    if VOICE_ENABLED:
        print("Voice capture mode: server-side + web wake-word")
        start_wake_word_listener()
    else:
        print("Voice capture disabled (VOICE_ENABLED=0)")
    start_ai_periodic_learn()
    print("Server started on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
    
