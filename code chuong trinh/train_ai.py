import json
import os
from pymongo import MongoClient
from ai_engine import SmartHomeAI
try:
    import certifi
except Exception:
    certifi = None


ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")


def load_env_file(path):
    if not os.path.exists(path):
        return
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


def main():
    load_env_file(ENV_FILE)

    # Kết nối MongoDB
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

    # Khởi tạo AI
    ai = SmartHomeAI(db)

    seeded = {
        "aliases": 0,
        "intents": 0,
        "rules": 0
    }

    def seed_alias(alias: str, device: str):
        result = ai.teach_alias(alias, device)
        if result.get("upserted"):
            seeded["aliases"] += 1

    def seed_intent(trigger: str, action: str):
        result = ai.teach_intent(trigger, action)
        if result.get("upserted"):
            seeded["intents"] += 1

    def seed_rule(condition: str, action: str):
        result = ai.teach_rule(condition, action)
        if result.get("upserted"):
            seeded["rules"] += 1

    # Dạy alias
    seed_alias("phòng khách", "light1")
    seed_alias("phòng ngủ", "light2")
    seed_alias("phòng bếp", "light3")
    seed_alias("quạt", "fan")
    seed_alias("cửa", "door")
    seed_alias("rèm", "roof")
    seed_alias("mái", "roof")

    # Dạy intent cho đèn và quạt
    seed_intent("bật đèn phòng khách", "LIGHT1_ON")
    seed_intent("tắt đèn phòng khách", "LIGHT1_OFF")
    seed_intent("bật đèn phòng ngủ", "LIGHT2_ON")
    seed_intent("tắt đèn phòng ngủ", "LIGHT2_OFF")
    seed_intent("bật đèn phòng bếp", "LIGHT3_ON")
    seed_intent("tắt đèn phòng bếp", "LIGHT3_OFF")
    seed_intent("bật quạt", "FAN_ON")
    seed_intent("tắt quạt", "FAN_OFF")
    seed_intent("mở cửa", "DOOR_OPEN")
    seed_intent("đóng cửa", "DOOR_CLOSE")
    seed_intent("mở mái", "ROOF_OPEN")
    seed_intent("đóng mái", "ROOF_CLOSE")

    # Dạy rule
    seed_rule("temp > 30", "FAN_ON")

    # ===== TRAIN TÙY Ý (từ file JSON hoặc nhập tay) =====
    custom_file = os.getenv("TRAIN_CUSTOM_FILE")
    if custom_file and os.path.exists(custom_file):
        try:
            with open(custom_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("aliases", []):
                alias = item.get("alias", "").strip()
                device = item.get("device", "").strip()
                if alias and device:
                    seed_alias(alias, device)
            for item in data.get("intents", []):
                trigger = item.get("trigger", "").strip()
                action = item.get("action", "").strip()
                if trigger and action:
                    seed_intent(trigger, action)
            for item in data.get("rules", []):
                condition = item.get("condition", "").strip()
                action = item.get("action", "").strip()
                if condition and action:
                    seed_rule(condition, action)
            print(f"Đã nạp train tùy ý từ file: {custom_file}")
        except Exception as e:
            print(f"Lỗi đọc TRAIN_CUSTOM_FILE: {e}")

    if os.getenv("TRAIN_CUSTOM_PROMPT", "0") == "1":
        print("Nhập lệnh tuỳ ý (bỏ trống để dừng). Ví dụ: bật đèn 1 -> LIGHT1_ON")
        while True:
            line = input("Câu lệnh: ").strip()
            if not line:
                break
            action = input("Action (MQTT command): ").strip()
            if not action:
                continue
            seed_intent(line, action)
        print("Đã nạp train tuỳ ý từ console.")

    retrained = ai.retrain_model_if_needed(force=True)

    print("Huấn luyện SmartHomeAI hoàn tất.")
    print(
        f"Seed mới: intents={seeded['intents']}, aliases={seeded['aliases']}, rules={seeded['rules']}; "
        f"retrained={'yes' if retrained else 'no'}"
    )


if __name__ == "__main__":
    main()
