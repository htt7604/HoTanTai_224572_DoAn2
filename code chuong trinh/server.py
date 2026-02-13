from flask import Flask, jsonify
from pymongo import MongoClient
import paho.mqtt.client as mqtt
import json
from datetime import datetime

# ================== MONGODB ==================
mongo = MongoClient("mongodb://localhost:27017/")
db = mongo["iot_db"]
collection = db["sensor_data"]

print("MongoDB connected")

# ================== FLASK ==================
app = Flask(__name__)

# ================== MQTT ==================
MQTT_BROKER = "localhost"
MQTT_TOPIC = "esp32/sensor"

latest_data = {}

def on_connect(client, userdata, flags, rc):
    print("MQTT connected:", rc)
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    global latest_data
    try:
        data = json.loads(msg.payload.decode())
        
        data["timestamp"] = datetime.now()

        # Lưu MongoDB
        collection.insert_one(data)

        latest_data = data

        print("\n===== SENSOR DATA =====")
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
        print("========================")

    except Exception as e:
        print("Error:", e)

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, 1883, 60)
mqtt_client.loop_start()

# ================== API ==================

@app.route("/sensor/latest")
def get_latest():
    if latest_data:
        latest_data["_id"] = str(latest_data["_id"])
        latest_data["timestamp"] = str(latest_data["timestamp"])
        return jsonify(latest_data)
    return jsonify({"message": "No data"})


@app.route("/sensor/history")
def get_history():
    data = list(collection.find().sort("timestamp", -1).limit(20))
    for d in data:
        d["_id"] = str(d["_id"])
        d["timestamp"] = str(d["timestamp"])
    return jsonify(data)

# ================== RUN ==================
if __name__ == "__main__":
    print("Server started")
    app.run(host="0.0.0.0", port=5000)
