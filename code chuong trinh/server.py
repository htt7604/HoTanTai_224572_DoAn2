from flask import Flask, jsonify, request, render_template, send_from_directory
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

# ================== MONGODB ==================
mongo = MongoClient("mongodb://localhost:27017/")
db = mongo["iot_db"]
collection_sensor = db["sensor_data"]  # Dữ liệu cảm biến định kỳ
collection_events = db["events"]  # Sự kiện quan trọng
collection_states = db["device_states"]  # Trạng thái thiết bị
collection_user_actions = db["user_actions"]  # Lịch sử điều khiển thiết bị
collection_ai_alias = db["ai_alias"]  # Alias người dùng đặt cho thiết bị
collection_device_names = db["device_names"]  # Tên hiển thị thiết bị do người dùng đặt
collection_mobile_push_tokens = db["mobile_push_tokens"]  # Token FCM từ mobile

# Tạo index cho truy vấn nhanh hơn
collection_sensor.create_index("timestamp")
collection_events.create_index("timestamp")
collection_events.create_index("event_type")
collection_user_actions.create_index("timestamp")
collection_mobile_push_tokens.create_index("token", unique=True)

print("MongoDB connected")

# ================== AI ENGINE ==================
ai_engine = SmartHomeAI(db)

# ================== FLASK ==================
app = Flask(__name__, template_folder='templates')
CORS(app)  # Cho phép CORS để web app có thể gọi API

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

# ================== MQTT ==================
MQTT_BROKER = "3c5308fe02794486932d547731382984.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_TOPIC_SENSOR = "esp32/sensor"
MQTT_TOPIC_CONTROL = "esp32/control"
MQTT_TOPIC_EVENTS = "esp32/events"
MQTT_TOPIC_PASSWORD = "esp32/password"
MQTT_TOPIC_PASSWORD_RESULT = "esp32/password/result"

latest_data = {}
mqtt_client = None

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
    stored_hash = _find_stored_password_hash()
    is_valid = bool(incoming_hash and stored_hash and incoming_hash == stored_hash)

    mqtt_client.publish(MQTT_TOPIC_PASSWORD_RESULT, "OK" if is_valid else "FAIL")
    if is_valid:
        mqtt_client.publish(MQTT_TOPIC_CONTROL, "DOOR_OPEN")
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

def save_event(event_type, description, data=None):
    """Lưu sự kiện quan trọng vào MongoDB"""
    event = {
        "timestamp": datetime.now(),
        "event_type": event_type,
        "description": description,
        "data": data or {}
    }
    collection_events.insert_one(event)
    print(f"[EVENT] {event_type}: {description}")


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
    global latest_data, last_periodic_save
    topic = getattr(msg, "topic", "") or ""
    try:
        payload = msg.payload.decode()
        # ===== BẮT ĐẦU CHỨC NĂNG HASH MẬT KHẨU =====
        if topic == MQTT_TOPIC_PASSWORD:
            _handle_password_hash_check(payload)
            return
        # ===== KẾT THÚC CHỨC NĂNG HASH MẬT KHẨU =====

        # Xử lý topic esp32/events (RFID, KEYPAD, BUZZER, ROOF_AUTO_CLOSE_RAIN...)
        if topic == MQTT_TOPIC_EVENTS:
            try:
                ev = json.loads(payload) if payload.strip().startswith("{") else {"event": payload.strip()}
                event_type = ev.get("event", str(ev))
                desc_map = {
                    "RFID_OPEN": "RFID mở cửa",
                    "RFID_CLOSE": "RFID đóng cửa",
                    "KEYPAD_OPEN": "Keypad mở cửa (mật khẩu đúng)",
                    "KEYPAD_CLOSE": "Keypad đóng cửa",
                    "BUZZER_ALARM": "Buzzer báo động kích hoạt",
                    "HUMAN_DETECTED": "Phát hiện người (PIR)",
                    "HUMAN_LEFT": "Không còn phát hiện người",
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
    doc = {
        "timestamp": datetime.now(),
        "command": command,
        "source": source
    }
    if raw_text:
        doc["text"] = raw_text
    collection_user_actions.insert_one(doc)
    print(f"[USER ACTION] {command} (source={source})")

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
    if latest_data:
        data = latest_data.copy()
        if "_id" in data:
            data["_id"] = str(data["_id"])
        if "timestamp" in data:
            data["timestamp"] = str(data["timestamp"])
        data["device_names"] = device_names
        return jsonify(data)
    return jsonify({"message": "No data", "device_names": device_names})


@app.route("/mobile/bootstrap")
def mobile_bootstrap():
    """Trả dữ liệu khởi tạo cho mobile: sensor mới nhất + tên thiết bị."""
    payload = {
        "device_names": _get_device_name_map()
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

    if not token:
        return jsonify({"success": False, "error": "token là bắt buộc"}), 400

    collection_mobile_push_tokens.update_one(
        {"token": token},
        {
            "$set": {
                "platform": platform,
                "updated_at": datetime.now()
            },
            "$setOnInsert": {
                "created_at": datetime.now()
            }
        },
        upsert=True
    )

    return jsonify({"success": True})

@app.route("/sensor/history")
def get_history():
    """Lấy lịch sử dữ liệu cảm biến"""
    data = list(collection_sensor.find().sort("timestamp", -1).limit(50))
    for d in data:
        d["_id"] = str(d["_id"])
        d["timestamp"] = str(d["timestamp"])
    return jsonify(data)

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
        ok = ai_engine.retrain_model_if_needed()
        return jsonify({"success": True, "retrained": ok})
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
    """Deprecated: voice capture moved to mobile client."""
    return jsonify({
        "success": False,
        "message": "Server không còn thu âm. Hãy gửi text lên /ai/process từ app mobile."
    }), 410


@app.route("/voice/status")
def voice_status():
    return jsonify({
        "wake_word": False,
        "text": "",
        "active": False,
        "response_ready": False,
        "response_text": "",
        "message": "Server wake-word listener đã tắt."
    })

# ================== CONTROL ROUTES ==================

@app.route("/control/door", methods=["POST"])
def control_door():
    try:
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
    print("Voice capture mode: client-side (mobile)")
    start_ai_periodic_learn()
    print("Server started on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
    
