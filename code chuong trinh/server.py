from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
import paho.mqtt.client as mqtt
import json
from datetime import datetime, timedelta
import os
import threading
import time

# ================== MONGODB ==================
mongo = MongoClient("mongodb://localhost:27017/")
db = mongo["iot_db"]
collection_sensor = db["sensor_data"]  # Dữ liệu cảm biến định kỳ
collection_events = db["events"]  # Sự kiện quan trọng
collection_states = db["device_states"]  # Trạng thái thiết bị

# Tạo index cho truy vấn nhanh hơn
collection_sensor.create_index("timestamp")
collection_events.create_index("timestamp")
collection_events.create_index("event_type")

print("MongoDB connected")

# ================== FLASK ==================
app = Flask(__name__, template_folder='templates')
CORS(app)  # Cho phép CORS để web app có thể gọi API

# ================== MQTT ==================
MQTT_BROKER = "localhost"
MQTT_TOPIC_SENSOR = "esp32/sensor"
MQTT_TOPIC_CONTROL = "esp32/control"

latest_data = {}
mqtt_client = None

# ================== THEO DÕI TRẠNG THÁI ==================
# Lưu trạng thái trước đó để phát hiện thay đổi
previous_state = {
    "door": False,
    "light1": False,
    "light2": False,
    "light3": False,
    "rain": False,
    "flame": False,
    "pir": False,
    "gas": 0,
    "temp": 0.0,
    "hum": 0.0
}

# Thời gian lưu định kỳ
PERIODIC_SAVE_INTERVAL = 300  # 5 phút (300 giây)
last_periodic_save = datetime.now()

# Ngưỡng thay đổi để coi là sự kiện quan trọng
TEMP_CHANGE_THRESHOLD = 2.0  # Nhiệt độ thay đổi > 2°C
HUM_CHANGE_THRESHOLD = 5.0   # Độ ẩm thay đổi > 5%
GAS_CHANGE_THRESHOLD = 50    # Gas thay đổi > 50

def on_connect(client, userdata, flags, rc):
    print("MQTT connected:", rc)
    client.subscribe(MQTT_TOPIC_SENSOR)

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
    
    # Kiểm tra cảnh báo
    if data.get("flame") and not previous_state["flame"]:
        save_event("FIRE_ALERT", "CẢNH BÁO: Phát hiện lửa!", {"flame": True})
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
    if gas_value > 400 and previous_state["gas"] <= 400:
        save_event("GAS_ALERT", f"CẢNH BÁO: Phát hiện gas! Giá trị: {gas_value}", {"gas": gas_value})
        has_important_change = True
    elif gas_value <= 400 and previous_state["gas"] > 400:
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
    try:
        data = json.loads(msg.payload.decode())
        data["timestamp"] = datetime.now()
        
        # Cập nhật dữ liệu mới nhất
        latest_data = data
        
        # Kiểm tra và lưu sự kiện quan trọng
        has_change = check_and_save_changes(data)
        
        # Lưu định kỳ (mỗi 5 phút) để có dữ liệu lịch sử
        now = datetime.now()
        if (now - last_periodic_save).total_seconds() >= PERIODIC_SAVE_INTERVAL:
            collection_sensor.insert_one(data.copy())
            last_periodic_save = now
            print(f"[PERIODIC SAVE] Đã lưu dữ liệu định kỳ lúc {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Lưu ngay nếu có sự kiện quan trọng
        if has_change:
            collection_sensor.insert_one(data.copy())
            # Lưu trạng thái thiết bị khi có thay đổi
            state_doc = {
                "timestamp": data["timestamp"],
                "door": data.get("door", False),
                "light1": data.get("light1", False),
                "light2": data.get("light2", False),
                "light3": data.get("light3", False),
                "fan": data.get("fan", False) if "fan" in data else None
            }
            collection_states.insert_one(state_doc)
        
        # In thông tin (chỉ khi có thay đổi hoặc debug)
        if has_change:
            print("\n===== SENSOR DATA (CHANGED) =====")
            print("Temperature:", data.get("temp"))
            print("Humidity:", data.get("hum"))
            print("Gas:", data.get("gas"))
            print("Rain:", data.get("rain"))
            print("Flame:", data.get("flame"))
            print("PIR:", data.get("pir"))
            print("Door:", data.get("door"))
            print("Light1:", data.get("light1"))
            print("Light2:", data.get("light2"))
            print("Light3:", data.get("light3"))
            print("================================")

    except Exception as e:
        print(f"Error processing MQTT message: {e}")
        import traceback
        traceback.print_exc()

def init_mqtt():
    global mqtt_client
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER, 1883, 60)
    mqtt_client.loop_start()

# ================== API ROUTES ==================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/sensor/latest")
def get_latest():
    if latest_data:
        data = latest_data.copy()
        if "_id" in data:
            data["_id"] = str(data["_id"])
        if "timestamp" in data:
            data["timestamp"] = str(data["timestamp"])
        return jsonify(data)
    return jsonify({"message": "No data"})

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
            print(f"Sent command: {command}")
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
            print(f"Sent command: {command}")
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
            print(f"Sent command: {command}")
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
            print(f"Sent command: {command}")
            return jsonify({"success": True, "command": command})
        else:
            return jsonify({"error": "MQTT not connected"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ================== RUN ==================
if __name__ == "__main__":
    print("Initializing MQTT...")
    init_mqtt()
    print("Server started on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
