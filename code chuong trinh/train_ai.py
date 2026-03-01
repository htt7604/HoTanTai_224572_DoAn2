import json
import os
from pymongo import MongoClient
from ai_engine import SmartHomeAI


def main():
    # Kết nối MongoDB
    mongo = MongoClient("mongodb://localhost:27017/")
    db = mongo["iot_db"]

    # Khởi tạo AI
    ai = SmartHomeAI(db)

    # Dạy alias
    ai.teach_alias("phòng khách", "light1")
    ai.teach_alias("phòng ngủ", "light2")
    ai.teach_alias("phòng bếp", "light3")
    ai.teach_alias("quạt", "fan")

    # Dạy intent cho đèn và quạt
    ai.teach_intent("bật đèn phòng khách", "LIGHT1_ON")
    ai.teach_intent("tắt đèn phòng khách", "LIGHT1_OFF")
    ai.teach_intent("bật đèn phòng ngủ", "LIGHT2_ON")
    ai.teach_intent("tắt đèn phòng ngủ", "LIGHT2_OFF")
    ai.teach_intent("bật đèn phòng bếp", "LIGHT3_ON")
    ai.teach_intent("tắt đèn phòng bếp", "LIGHT3_OFF")
    ai.teach_intent("bật quạt", "FAN_ON")
    ai.teach_intent("tắt quạt", "FAN_OFF")

    # Dạy rule
    ai.teach_rule("temp > 30", "FAN_ON")

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
                    ai.teach_alias(alias, device)
            for item in data.get("intents", []):
                trigger = item.get("trigger", "").strip()
                action = item.get("action", "").strip()
                if trigger and action:
                    ai.teach_intent(trigger, action)
            for item in data.get("rules", []):
                condition = item.get("condition", "").strip()
                action = item.get("action", "").strip()
                if condition and action:
                    ai.teach_rule(condition, action)
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
            ai.teach_intent(line, action)
        print("Đã nạp train tuỳ ý từ console.")

    print("Huấn luyện SmartHomeAI hoàn tất.")


if __name__ == "__main__":
    main()
