import json
import os
import random
import ssl
import threading
import time
import paho.mqtt.client as mqtt

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

# ================== CONFIG ==================
MQTT_BROKER = os.getenv(
    "MQTT_BROKER",
    "3c5308fe02794486932d547731382984.s1.eu.hivemq.cloud"
)
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
MQTT_TOPIC_SENSOR = os.getenv("MQTT_TOPIC_SENSOR", "esp32/sensor")
MQTT_TOPIC_CONTROL = os.getenv("MQTT_TOPIC_CONTROL", "esp32/control")
MQTT_CLIENT_ID = os.getenv(
    "MQTT_CLIENT_ID",
    f"ESP32_SIM_{random.randint(1000, 9999)}"
)
PUBLISH_INTERVAL = float(os.getenv("PUBLISH_INTERVAL", "3"))

# ================== STATE ==================
state_lock = threading.Lock()
stop_event = threading.Event()

device_state = {
    "door": "CLOSED",
    "light1": False,
    "light2": False,
    "light3": False,
    "fan": False,
    "roof": False
}

sensor_state = {
    "temp": 28.0,
    "hum": 70.0,
    "gas": 280,
    "rain": False,
    "flame": False,
    "pir": False
}


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def jitter_sensor_values():
    with state_lock:
        sensor_state["temp"] = round(
            clamp(sensor_state["temp"] + random.uniform(-0.3, 0.3), 18.0, 36.0), 1
        )
        sensor_state["hum"] = round(
            clamp(sensor_state["hum"] + random.uniform(-1.2, 1.2), 30.0, 90.0), 1
        )
        sensor_state["gas"] = int(
            clamp(sensor_state["gas"] + random.randint(-12, 12), 150, 600)
        )

        # Thỉnh thoảng có sự kiện
        if random.random() < 0.03:
            sensor_state["rain"] = True
        elif random.random() < 0.08:
            sensor_state["rain"] = False

        if random.random() < 0.02:
            sensor_state["flame"] = True
        elif random.random() < 0.06:
            sensor_state["flame"] = False

        sensor_state["pir"] = random.random() < 0.15

        # Gas spike hiếm
        if random.random() < 0.02:
            sensor_state["gas"] = clamp(sensor_state["gas"] + random.randint(80, 150), 150, 600)


def build_payload():
    with state_lock:
        payload = {
            "temp": sensor_state["temp"],
            "hum": sensor_state["hum"],
            "gas": sensor_state["gas"],
            "rain": sensor_state["rain"],
            "flame": sensor_state["flame"],
            "pir": sensor_state["pir"],
            "door": device_state["door"],
            "light1": device_state["light1"],
            "light2": device_state["light2"],
            "light3": device_state["light3"],
            "fan": device_state["fan"]
        }
    return payload


def apply_command(command):
    command = (command or "").strip().upper()
    if not command:
        return False

    changed = False
    with state_lock:
        if command == "DOOR_OPEN":
            device_state["door"] = "OPEN"
            changed = True
        elif command == "DOOR_CLOSE":
            device_state["door"] = "CLOSED"
            changed = True
        elif command == "LIGHT1_ON":
            device_state["light1"] = True
            changed = True
        elif command == "LIGHT1_OFF":
            device_state["light1"] = False
            changed = True
        elif command == "LIGHT2_ON":
            device_state["light2"] = True
            changed = True
        elif command == "LIGHT2_OFF":
            device_state["light2"] = False
            changed = True
        elif command == "LIGHT3_ON":
            device_state["light3"] = True
            changed = True
        elif command == "LIGHT3_OFF":
            device_state["light3"] = False
            changed = True
        elif command == "FAN_ON":
            device_state["fan"] = True
            changed = True
        elif command == "FAN_OFF":
            device_state["fan"] = False
            changed = True
        elif command == "ROOF_OPEN":
            device_state["roof"] = True
            changed = True
        elif command == "ROOF_CLOSE":
            device_state["roof"] = False
            changed = True

    return changed


def parse_command(payload):
    raw = payload.decode(errors="ignore")
    raw = raw.strip()
    if not raw:
        return None

    # Plain command string
    if raw[0] != "{":
        return raw

    # JSON payload (tương thích mở rộng)
    try:
        data = json.loads(raw)
    except Exception:
        return raw

    if isinstance(data, dict):
        if "command" in data:
            return str(data.get("command"))
        device = str(data.get("device", "")).strip().lower()
        action = str(data.get("action", "")).strip().lower()
        if device and action:
            if device.startswith("light"):
                light_num = device.replace("light", "")
                if action == "on":
                    return f"LIGHT{light_num}_ON"
                if action == "off":
                    return f"LIGHT{light_num}_OFF"
            if device == "fan":
                return "FAN_ON" if action == "on" else "FAN_OFF"
            if device == "door":
                return "DOOR_OPEN" if action == "open" else "DOOR_CLOSE"
            if device == "roof":
                return "ROOF_OPEN" if action == "open" else "ROOF_CLOSE"
    return None


def publish_sensor(client, reason=None):
    payload = build_payload()
    client.publish(MQTT_TOPIC_SENSOR, json.dumps(payload))
    if reason:
        print(f"Published sensor data ({reason}): {payload}")
    else:
        print(f"Published sensor data: {payload}")


def on_connect(client, userdata, flags, reason_code, properties=None):
    rc = int(reason_code) if hasattr(reason_code, "__int__") else reason_code
    if rc == 0:
        print(f"Connected to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC_CONTROL)
    else:
        print(f"MQTT connect failed: {rc} (not authorized?)")


def on_disconnect(client, userdata, reason_code=None, properties=None, *args, **kwargs):
    rc = int(reason_code) if hasattr(reason_code, "__int__") else reason_code
    if rc not in (0, None):
        print(f"Unexpected MQTT disconnect (rc={rc})")


def on_message(client, userdata, msg):
    command = parse_command(msg.payload)
    if not command:
        return
    print(f"Received command: {command}")
    if apply_command(command):
        publish_sensor(client, reason="command")


def publish_loop(client):
    while not stop_event.is_set():
        jitter_sensor_values()
        publish_sensor(client)
        stop_event.wait(PUBLISH_INTERVAL)


def main():
    mqtt_username = os.getenv("MQTT_USERNAME")
    mqtt_password = os.getenv("MQTT_PASSWORD")
    if mqtt_username:
        mqtt_username = mqtt_username.strip().strip('"').strip("'").strip()
    if mqtt_password:
        mqtt_password = mqtt_password.strip().strip('"').strip("'").strip()
    if not mqtt_username or not mqtt_password:
        raise RuntimeError(
            "Missing MQTT_USERNAME or MQTT_PASSWORD environment variable "
            f"(check {ENV_FILE})"
        )

    client = mqtt.Client(
        client_id=MQTT_CLIENT_ID,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.enable_logger()

    client.username_pw_set(mqtt_username, mqtt_password)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS)
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        raise RuntimeError(f"MQTT connect error: {e}") from e
    client.loop_start()

    print("ESP32 simulator started")
    try:
        publish_thread = threading.Thread(target=publish_loop, args=(client,), daemon=True)
        publish_thread.start()
        while not stop_event.is_set():
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Stopping ESP32 simulator...")
    finally:
        stop_event.set()
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()