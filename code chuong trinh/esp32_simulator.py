import hashlib
import json
import os
import random
import ssl
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")


def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as file:
        for raw in file:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_env_file(ENV_FILE)


def env_value(name, default=None):
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip().strip('"').strip("'").strip()
    return value if value else default


MQTT_BROKER = env_value("MQTT_BROKER", "3c5308fe02794486932d547731382984.s1.eu.hivemq.cloud")
MQTT_PORT = int(env_value("MQTT_PORT", "8883"))

MQTT_TOPIC_SENSOR = env_value("MQTT_TOPIC_SENSOR", "esp32/sensor")
MQTT_TOPIC_EVENTS = env_value("MQTT_TOPIC_EVENTS", "esp32/events")
MQTT_TOPIC_CONTROL = env_value("MQTT_TOPIC_CONTROL", "esp32/control")
MQTT_TOPIC_PASSWORD = env_value("MQTT_TOPIC_PASSWORD", "esp32/password")
MQTT_TOPIC_PASSWORD_RESULT = env_value("MQTT_TOPIC_PASSWORD_RESULT", "esp32/password/result")
MQTT_TOPIC_RFID = env_value("MQTT_TOPIC_RFID", "esp32/rfid")
MQTT_TOPIC_RFID_RESULT = env_value("MQTT_TOPIC_RFID_RESULT", "esp32/rfid/result")

MQTT_USERNAME = (
    env_value("ESP32_SIM_MQTT_USERNAME")
    or env_value("MQTT_USERNAME")
    or "esp32"
)
MQTT_PASSWORD = (
    env_value("ESP32_SIM_MQTT_PASSWORD")
    or env_value("MQTT_PASSWORD")
    or "Esp32123"
)

MQTT_CLIENT_ID = env_value("ESP32_SIM_CLIENT_ID", f"ESP32_SmartHome_SIM_{random.randint(1000, 9999)}")
PUBLISH_INTERVAL = float(env_value("ESP32_SIM_PUBLISH_INTERVAL", "2.0"))
TICK_INTERVAL = float(env_value("ESP32_SIM_TICK_INTERVAL", "0.2"))

GAS_ALERT_THRESHOLD = int(env_value("ESP32_SIM_GAS_ALERT_THRESHOLD", "1200"))
GAS_ALERT_DELTA = int(env_value("ESP32_SIM_GAS_ALERT_DELTA", "250"))
GAS_HYSTERESIS = int(env_value("ESP32_SIM_GAS_HYSTERESIS", "150"))
FIRE_EVENT_INTERVAL = float(env_value("ESP32_SIM_FIRE_EVENT_INTERVAL", "3.0"))

state_lock = threading.Lock()
stop_event = threading.Event()

device_state = {
    "door": False,
    "light1": False,
    "light2": False,
    "light3": False,
    "light4": False,
    "fan": False,
    "roof": False,
}

sensor_state = {
    "temp": 28.0,
    "hum": 70.0,
    "gas": 280,
    "rain": False,
    "flame": False,
    "pir": False,
}

runtime = {
    "last_rain": False,
    "last_pir": False,
    "last_gas_detected": False,
    "gas_baseline": 280,
    "last_sensor_publish": 0.0,
    "last_fire_event": 0.0,
}

manual_flags = {
    "rain": False,
    "pir": False,
    "flame": False,
    "gas": False,
}


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def sha256_hex(raw_text):
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def publish_json(client, topic, payload):
    body = json.dumps(payload, ensure_ascii=False)
    client.publish(topic, body)


def publish_event(client, event_name, data=None):
    payload = {"event": event_name}
    if data:
        payload.update(data)
    publish_json(client, MQTT_TOPIC_EVENTS, payload)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] EVENT -> {payload}")


def build_sensor_payload():
    with state_lock:
        return {
            "temp": round(float(sensor_state["temp"]), 1),
            "hum": round(float(sensor_state["hum"]), 1),
            "gas": int(sensor_state["gas"]),
            "rain": bool(sensor_state["rain"]),
            "flame": bool(sensor_state["flame"]),
            "pir": bool(sensor_state["pir"]),
            "door": bool(device_state["door"]),
            "light1": bool(device_state["light1"]),
            "light2": bool(device_state["light2"]),
            "light3": bool(device_state["light3"]),
            "light4": bool(device_state["light4"]),
            "fan": bool(device_state["fan"]),
            "roof": bool(device_state["roof"]),
        }


def publish_sensor(client, reason="periodic"):
    payload = build_sensor_payload()
    publish_json(client, MQTT_TOPIC_SENSOR, payload)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] SENSOR ({reason}) -> {payload}")


def parse_control_command(raw_payload):
    text = raw_payload.decode(errors="ignore").strip()
    if not text:
        return None

    if not text.startswith("{"):
        return text.upper()

    try:
        data = json.loads(text)
    except Exception:
        return text.upper()

    if not isinstance(data, dict):
        return None

    command = str(data.get("command", "")).strip().upper()
    if command:
        return command

    device = str(data.get("device", "")).strip().lower()
    action = str(data.get("action", "")).strip().lower()
    if not device or not action:
        return None

    if device.startswith("light"):
        number = device.replace("light", "")
        if action == "on":
            return f"LIGHT{number}_ON"
        if action == "off":
            return f"LIGHT{number}_OFF"
    if device == "fan":
        return "FAN_ON" if action == "on" else "FAN_OFF"
    if device == "door":
        return "DOOR_OPEN" if action == "open" else "DOOR_CLOSE"
    if device == "roof":
        return "ROOF_OPEN" if action == "open" else "ROOF_CLOSE"
    return None


def apply_control_command(command):
    cmd = (command or "").strip().upper()
    if not cmd:
        return False

    changed = False
    with state_lock:
        if cmd == "DOOR_OPEN":
            changed = device_state["door"] is False
            device_state["door"] = True
        elif cmd == "DOOR_CLOSE":
            changed = device_state["door"] is True
            device_state["door"] = False
        elif cmd == "LIGHT1_ON":
            changed = device_state["light1"] is False
            device_state["light1"] = True
        elif cmd == "LIGHT1_OFF":
            changed = device_state["light1"] is True
            device_state["light1"] = False
        elif cmd == "LIGHT2_ON":
            changed = device_state["light2"] is False
            device_state["light2"] = True
        elif cmd == "LIGHT2_OFF":
            changed = device_state["light2"] is True
            device_state["light2"] = False
        elif cmd == "LIGHT3_ON":
            changed = device_state["light3"] is False
            device_state["light3"] = True
        elif cmd == "LIGHT3_OFF":
            changed = device_state["light3"] is True
            device_state["light3"] = False
        elif cmd == "LIGHT4_ON":
            changed = device_state["light4"] is False
            device_state["light4"] = True
        elif cmd == "LIGHT4_OFF":
            changed = device_state["light4"] is True
            device_state["light4"] = False
        elif cmd == "FAN_ON":
            changed = device_state["fan"] is False
            device_state["fan"] = True
        elif cmd == "FAN_OFF":
            changed = device_state["fan"] is True
            device_state["fan"] = False
        elif cmd == "ROOF_OPEN":
            changed = device_state["roof"] is False
            device_state["roof"] = True
        elif cmd == "ROOF_CLOSE":
            changed = device_state["roof"] is True
            device_state["roof"] = False

    if changed:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CONTROL applied: {cmd}")
    return changed


def update_sensor_randomly():
    with state_lock:
        sensor_state["temp"] = round(clamp(sensor_state["temp"] + random.uniform(-0.25, 0.25), 18.0, 40.0), 1)
        sensor_state["hum"] = round(clamp(sensor_state["hum"] + random.uniform(-0.9, 0.9), 35.0, 95.0), 1)

        if not manual_flags["gas"]:
            drift = random.randint(-15, 15)
            sensor_state["gas"] = int(clamp(sensor_state["gas"] + drift, 150, 2200))
            if random.random() < 0.015:
                sensor_state["gas"] = int(clamp(sensor_state["gas"] + random.randint(180, 420), 150, 3000))

        if not manual_flags["rain"]:
            if random.random() < 0.01:
                sensor_state["rain"] = not sensor_state["rain"]

        if not manual_flags["pir"]:
            if random.random() < 0.08:
                sensor_state["pir"] = not sensor_state["pir"]

        if not manual_flags["flame"]:
            if random.random() < 0.005:
                sensor_state["flame"] = True
            elif random.random() < 0.08:
                sensor_state["flame"] = False


def process_firmware_like_logic(client):
    now = time.time()
    with state_lock:
        is_raining = bool(sensor_state["rain"])
        pir_detected = bool(sensor_state["pir"])
        flame_detected = bool(sensor_state["flame"])
        gas_value = int(sensor_state["gas"])
        gas_baseline = int(runtime["gas_baseline"])

    gas_baseline = int(round(gas_baseline * 0.995 + gas_value * 0.005))
    runtime["gas_baseline"] = gas_baseline
    gas_dynamic_threshold = max(GAS_ALERT_THRESHOLD, gas_baseline + GAS_ALERT_DELTA)

    gas_detected_prev = bool(runtime["last_gas_detected"])
    gas_detected = gas_detected_prev
    if not gas_detected_prev and gas_value > gas_dynamic_threshold:
        gas_detected = True
    elif gas_detected_prev and gas_value < (gas_dynamic_threshold - GAS_HYSTERESIS):
        gas_detected = False

    if is_raining != runtime["last_rain"]:
        if is_raining:
            apply_control_command("ROOF_CLOSE")
            publish_event(client, "ROOF_AUTO_CLOSE_RAIN")
        else:
            apply_control_command("ROOF_OPEN")
            publish_event(client, "ROOF_AUTO_OPEN")
        runtime["last_rain"] = is_raining

    if gas_detected != runtime["last_gas_detected"]:
        if gas_detected:
            apply_control_command("FAN_ON")
            publish_event(client, "GAS_DETECTED", {"gas": gas_value})
        else:
            apply_control_command("FAN_OFF")
            publish_event(client, "GAS_NORMAL", {"gas": gas_value})
        runtime["last_gas_detected"] = gas_detected

    if pir_detected != runtime["last_pir"]:
        publish_event(client, "MOTION_DETECTED" if pir_detected else "MOTION_STOPPED")
        runtime["last_pir"] = pir_detected

    if flame_detected and (now - runtime["last_fire_event"] >= FIRE_EVENT_INTERVAL):
        publish_event(client, "BUZZER_ALARM")
        runtime["last_fire_event"] = now


def on_connect(client, userdata, flags, reason_code, properties=None):
    rc = int(reason_code) if hasattr(reason_code, "__int__") else reason_code
    if rc != 0:
        print(f"MQTT connect failed: rc={rc}")
        return

    print(f"Connected MQTT: {MQTT_BROKER}:{MQTT_PORT} as {MQTT_USERNAME} / client_id={MQTT_CLIENT_ID}")
    client.subscribe(MQTT_TOPIC_CONTROL)
    client.subscribe(MQTT_TOPIC_PASSWORD_RESULT)
    client.subscribe(MQTT_TOPIC_RFID_RESULT)
    print(f"Subscribed: {MQTT_TOPIC_CONTROL}, {MQTT_TOPIC_PASSWORD_RESULT}, {MQTT_TOPIC_RFID_RESULT}")


def on_disconnect(client, userdata, reason_code=None, properties=None, *args, **kwargs):
    rc = int(reason_code) if hasattr(reason_code, "__int__") else reason_code
    if rc not in (0, None):
        print(f"Unexpected disconnect, rc={rc}")


def on_message(client, userdata, msg):
    topic = (msg.topic or "").strip()
    if topic == MQTT_TOPIC_CONTROL:
        cmd = parse_control_command(msg.payload)
        if not cmd:
            return
        changed = apply_control_command(cmd)
        if changed:
            publish_sensor(client, reason=f"control:{cmd}")
        return

    text = msg.payload.decode(errors="ignore").strip()
    if topic == MQTT_TOPIC_PASSWORD_RESULT:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] PASSWORD_RESULT <- {text}")
        return

    if topic == MQTT_TOPIC_RFID_RESULT:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] RFID_RESULT <- {text}")
        return


def publish_password_check(client, password_text):
    payload = {
        "type": "password_check",
        "hash": sha256_hex(password_text),
    }
    publish_json(client, MQTT_TOPIC_PASSWORD, payload)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] PASSWORD_CHECK -> hash({len(password_text)} chars)")


def publish_rfid_scan(client, uid):
    uid_text = "".join(ch for ch in uid.upper() if ch in "0123456789ABCDEF")
    if not uid_text:
        print("UID không hợp lệ. Ví dụ: A1B2C3D4")
        return
    publish_json(client, MQTT_TOPIC_RFID, {"uid": uid_text, "source": "esp32"})
    publish_event(client, "RFID_SCAN", {"uid": uid_text})
    print(f"[{datetime.now().strftime('%H:%M:%S')}] RFID_SCAN -> {uid_text}")


def print_state():
    with state_lock:
        merged = {
            "device": dict(device_state),
            "sensor": dict(sensor_state),
            "runtime": {
                "last_rain": runtime["last_rain"],
                "last_pir": runtime["last_pir"],
                "last_gas_detected": runtime["last_gas_detected"],
                "gas_baseline": runtime["gas_baseline"],
            },
        }
    print(json.dumps(merged, ensure_ascii=False, indent=2))


def set_bool_sensor(name, value):
    if name not in {"rain", "pir", "flame"}:
        print("Chỉ hỗ trợ: rain | pir | flame")
        return
    with state_lock:
        sensor_state[name] = bool(value)
        manual_flags[name] = True


def set_gas_value(value):
    with state_lock:
        sensor_state["gas"] = int(clamp(value, 100, 3500))
        manual_flags["gas"] = True


def console_loop(client):
    print("\nESP32 simulator commands:")
    print("  help")
    print("  state")
    print("  keypad <mat_khau_tho>")
    print("  rfid <UID_HEX>")
    print("  cmd <MQTT_COMMAND>")
    print("  rain on|off|auto")
    print("  pir on|off|auto")
    print("  flame on|off|auto")
    print("  gas <value>|auto")
    print("  quit\n")

    while not stop_event.is_set():
        try:
            line = input("sim> ").strip()
        except (EOFError, KeyboardInterrupt):
            stop_event.set()
            break

        if not line:
            continue

        lower = line.lower()
        if lower in {"quit", "exit", "q"}:
            stop_event.set()
            break
        if lower == "help":
            print("help | state | keypad <pwd> | rfid <uid> | cmd <command> | rain/pir/flame on|off|auto | gas <num>|auto | quit")
            continue
        if lower == "state":
            print_state()
            continue

        if lower.startswith("keypad "):
            password_text = line[7:].strip()
            if not password_text:
                print("Thiếu mật khẩu")
                continue
            publish_password_check(client, password_text)
            continue

        if lower.startswith("rfid "):
            uid = line[5:].strip()
            publish_rfid_scan(client, uid)
            continue

        if lower.startswith("cmd "):
            cmd = line[4:].strip().upper()
            if not cmd:
                print("Thiếu command")
                continue
            client.publish(MQTT_TOPIC_CONTROL, cmd)
            print(f"Injected control command: {cmd}")
            continue

        if lower.startswith("rain "):
            option = lower.split(" ", 1)[1].strip()
            if option == "auto":
                manual_flags["rain"] = False
            else:
                set_bool_sensor("rain", option in {"on", "1", "true"})
            continue

        if lower.startswith("pir "):
            option = lower.split(" ", 1)[1].strip()
            if option == "auto":
                manual_flags["pir"] = False
            else:
                set_bool_sensor("pir", option in {"on", "1", "true"})
            continue

        if lower.startswith("flame "):
            option = lower.split(" ", 1)[1].strip()
            if option == "auto":
                manual_flags["flame"] = False
            else:
                set_bool_sensor("flame", option in {"on", "1", "true"})
            continue

        if lower.startswith("gas "):
            option = lower.split(" ", 1)[1].strip()
            if option == "auto":
                manual_flags["gas"] = False
            else:
                try:
                    set_gas_value(int(option))
                except ValueError:
                    print("gas phải là số nguyên hoặc 'auto'")
            continue

        print("Lệnh không hợp lệ. Gõ 'help'.")


def simulation_loop(client):
    runtime["last_sensor_publish"] = 0.0
    while not stop_event.is_set():
        update_sensor_randomly()
        process_firmware_like_logic(client)

        now = time.time()
        if now - runtime["last_sensor_publish"] >= PUBLISH_INTERVAL:
            publish_sensor(client, reason="periodic")
            runtime["last_sensor_publish"] = now

        stop_event.wait(TICK_INTERVAL)


def build_mqtt_client():
    try:
        client = mqtt.Client(
            client_id=MQTT_CLIENT_ID,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
    except Exception:
        client = mqtt.Client(client_id=MQTT_CLIENT_ID)

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS)
    client.enable_logger()
    return client


def main():
    client = build_mqtt_client()
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    print("ESP32 simulator đang chạy.")
    print(f"Broker={MQTT_BROKER}:{MQTT_PORT}, user={MQTT_USERNAME}, topic_sensor={MQTT_TOPIC_SENSOR}")

    simulation_thread = threading.Thread(target=simulation_loop, args=(client,), daemon=True)
    simulation_thread.start()

    try:
        console_loop(client)
    finally:
        stop_event.set()
        simulation_thread.join(timeout=2)
        client.loop_stop()
        client.disconnect()
        print("ESP32 simulator đã dừng.")


if __name__ == "__main__":
    main()