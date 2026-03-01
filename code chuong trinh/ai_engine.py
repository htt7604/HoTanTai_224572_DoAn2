from datetime import datetime
import os
import re
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


class SmartHomeAI:
    """
    AI Smart Home: học intent, alias và luật tự động.
    An toàn: không dùng eval, parse điều kiện theo mẫu đơn giản.
    """

    def __init__(self, db):
        self.db = db
        self.col_intents = db["ai_intents"]
        self.col_alias = db["ai_alias"]
        self.col_rules = db["ai_rules"]
        self.col_actions = db["user_actions"]
        self.col_meta = db["ai_meta"]

        self.model = None
        self.model_path = os.path.join(os.path.dirname(__file__), "intent_model.joblib")
        self._load_model_on_startup()

    # ================== TEACH ==================
    def teach_intent(self, trigger: str, action: str):
        """Lưu lệnh custom (trigger -> action)"""
        trigger_norm = self._normalize_text(trigger)
        action_norm = action.strip().upper()
        result = self.col_intents.update_one(
            {"trigger": trigger_norm},
            {"$set": {"action": action_norm, "updated_at": datetime.now()},
             "$setOnInsert": {"created_at": datetime.now()}},
            upsert=True
        )
        if result.upserted_id:
            self._increase_new_intents_and_retrain_if_needed()
        return {"matched": result.matched_count, "upserted": bool(result.upserted_id)}

    def teach_alias(self, alias: str, device: str):
        """Lưu từ đồng nghĩa (alias -> device)"""
        alias_norm = self._normalize_text(alias)
        device_norm = device.strip().lower()
        result = self.col_alias.update_one(
            {"alias": alias_norm},
            {"$set": {"device": device_norm, "updated_at": datetime.now()},
             "$setOnInsert": {"created_at": datetime.now()}},
            upsert=True
        )
        return {"matched": result.matched_count, "upserted": bool(result.upserted_id)}

    def teach_rule(self, condition: str, action: str):
        """Lưu luật tự động (condition -> action)"""
        doc = {
            "condition": condition.strip(),
            "action": action.strip().upper(),
            "created_at": datetime.now()
        }
        self.col_rules.insert_one(doc)
        return {"inserted": True}

    # ================== CORE ==================
    def process_command(self, text: str):
        """
        Xử lý câu lệnh:
        1) kiểm tra custom intents
        2) kiểm tra alias
        3) fallback rule-based intent detection
        Trả về MQTT command hoặc None
        """
        text_norm = self._normalize_text(text)
        if not text_norm:
            return None

        # 1) Custom intents (ưu tiên cao nhất)
        intent = self._match_intent(text_norm)
        if intent:
            return intent

        # 2) Alias -> device
        device = self._match_alias(text_norm)
        if device:
            action = self._detect_action(text_norm)
            if action:
                return self._build_command(device, action)

        # 3) ML classifier (nếu đã train)
        ml_action = self._predict_intent(text_norm)
        if ml_action:
            return ml_action

        # 4) Rule-based (dựa trên từ khóa thiết bị)
        action = self._detect_action(text_norm)
        if action:
            device = self._detect_device(text_norm)
            if device:
                return self._build_command(device, action)

        return None

    def auto_decision(self, sensor_data: dict):
        """
        Áp dụng rule từ MongoDB với sensor_data.
        Trả về list MQTT commands cần publish.
        """
        commands = []
        rules = list(self.col_rules.find())
        for rule in rules:
            condition = rule.get("condition", "")
            action = rule.get("action", "").upper()
            if self._evaluate_condition(condition, sensor_data):
                commands.append(action)
        return commands

    def learn_patterns(self):
        """
        Phân tích thói quen người dùng dựa trên user_actions.
        Ví dụ: nếu một lệnh lặp lại nhiều lần ở cùng giờ => tạo rule.
        """
        actions = list(self.col_actions.find().sort("timestamp", -1).limit(500))
        counter = {}
        for a in actions:
            ts = a.get("timestamp")
            cmd = a.get("command")
            if not ts or not cmd:
                continue
            hour = ts.hour
            key = (hour, cmd)
            counter[key] = counter.get(key, 0) + 1

        for (hour, cmd), count in counter.items():
            if count >= 3:
                condition = f"hour == {hour}"
                exists = self.col_rules.find_one({"condition": condition, "action": cmd})
                if not exists:
                    self.col_rules.insert_one({
                        "condition": condition,
                        "action": cmd,
                        "created_at": datetime.now(),
                        "source": "learn_patterns"
                    })

        return {"learned_rules": len(counter)}

    # ================== UTILITIES ==================
    def _normalize_text(self, text: str):
        text = re.sub(r"\s+", " ", text.strip().lower())
        # Chuẩn hóa cụm "số/so" và số tiếng Việt cơ bản
        text = re.sub(r"\b(số|so)\b", " ", text)
        text = re.sub(r"\bmột\b", "1", text)
        text = re.sub(r"\bmot\b", "1", text)
        text = re.sub(r"\bhai\b", "2", text)
        text = re.sub(r"\bba\b", "3", text)
        return text

    # ================== ML INTENT CLASSIFIER ==================
    def _load_model_on_startup(self):
        """Load model nếu có sẵn, nếu chưa có thì train nếu đủ dữ liệu"""
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                return
            except Exception:
                self.model = None
        # Nếu chưa có model, thử train khi đủ dữ liệu
        self._train_intent_model_if_possible()

    def _increase_new_intents_and_retrain_if_needed(self):
        """Tăng bộ đếm lệnh mới, đủ 5 thì retrain"""
        meta = self.col_meta.find_one({"_id": "intent_model"}) or {}
        new_count = int(meta.get("new_intents_since_train", 0)) + 1
        self.col_meta.update_one(
            {"_id": "intent_model"},
            {"$set": {"new_intents_since_train": new_count, "updated_at": datetime.now()},
             "$setOnInsert": {"created_at": datetime.now()}},
            upsert=True
        )
        if new_count >= 5:
            trained = self._train_intent_model_if_possible()
            if trained:
                self.col_meta.update_one(
                    {"_id": "intent_model"},
                    {"$set": {"new_intents_since_train": 0,
                              "last_trained_at": datetime.now(),
                              "trained_count": trained}},
                    upsert=True
                )

    def _train_intent_model_if_possible(self):
        """Train model nếu có đủ dữ liệu, trả về số mẫu train"""
        intents = list(self.col_intents.find())
        if len(intents) < 2:
            return 0

        texts = [it.get("trigger", "") for it in intents if it.get("trigger")]
        labels = [it.get("action", "") for it in intents if it.get("trigger")]
        if len(set(labels)) < 2:
            return 0

        model = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2))),
            ("clf", LogisticRegression(max_iter=1000))
        ])
        model.fit(texts, labels)
        joblib.dump(model, self.model_path)
        self.model = model
        return len(texts)

    def _predict_intent(self, text_norm: str):
        """Dự đoán action bằng ML, có ngưỡng tin cậy"""
        if not self.model:
            return None
        try:
            proba = None
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba([text_norm])[0]
            pred = self.model.predict([text_norm])[0]
            if proba is not None:
                best = float(max(proba))
                if best < 0.55:
                    return None
            return pred
        except Exception:
            return None

    def _match_intent(self, text_norm: str):
        # Ưu tiên khớp đúng
        exact = self.col_intents.find_one({"trigger": text_norm})
        if exact:
            return exact.get("action")

        # Khớp theo substring (trigger là một phần của câu lệnh)
        intents = list(self.col_intents.find())
        intents.sort(key=lambda x: len(x.get("trigger", "")), reverse=True)
        for it in intents:
            trigger = it.get("trigger", "")
            if trigger and trigger in text_norm:
                return it.get("action")
        return None

    def _match_alias(self, text_norm: str):
        aliases = list(self.col_alias.find())
        aliases.sort(key=lambda x: len(x.get("alias", "")), reverse=True)
        for al in aliases:
            alias = al.get("alias", "")
            if alias and alias in text_norm:
                return al.get("device")
        return None

    def _detect_action(self, text_norm: str):
        # Ưu tiên tiếng Việt
        if "bật" in text_norm or re.search(r"\bturn on\b", text_norm) or re.search(r"\bon\b", text_norm):
            return "on"
        if "tắt" in text_norm or re.search(r"\bturn off\b", text_norm) or re.search(r"\boff\b", text_norm):
            return "off"
        if "mở" in text_norm or re.search(r"\bopen\b", text_norm):
            return "open"
        if "đóng" in text_norm or re.search(r"\bclose\b", text_norm):
            return "close"
        return None

    def _detect_device(self, text_norm: str): 
        # Thiết bị hỗ trợ mặc định
        device_keywords = {
            "light1": ["đèn 1", "đèn1", "den 1", "den1", "light 1", "light1", "đèn một", "den mot"],
            "light2": ["đèn 2", "đèn2", "den 2", "den2", "light 2", "light2", "đèn hai", "den hai"],
            "light3": ["đèn 3", "đèn3", "den 3", "den3", "light 3", "light3", "đèn ba", "den ba"],
            "fan": ["quạt", "fan"],
            "door": ["cửa", "door"],
            "roof": ["mái", "roof"]
        }
        for device, keywords in device_keywords.items():
            for kw in keywords:
                if kw in text_norm:
                    return device
        # Fallback: nếu chỉ nói "đèn" không kèm số, mặc định đèn 1
        if "đèn" in text_norm or "den" in text_norm or "light" in text_norm:
            return "light1"
        return None

    def _build_command(self, device: str, action: str):
        device = (device or "").lower()
        action = (action or "").lower()
        if device.startswith("light"):
            light_num = device.replace("light", "")
            if action == "on":
                return f"LIGHT{light_num}_ON"
            if action == "off":
                return f"LIGHT{light_num}_OFF"
        if device == "fan":
            return "FAN_ON" if action == "on" else "FAN_OFF"
        if device == "door":
            if action == "open":
                return "DOOR_OPEN"
            if action == "close":
                return "DOOR_CLOSE"
            return None
        if device == "roof":
            if action == "open":
                return "ROOF_OPEN"
            if action == "close":
                return "ROOF_CLOSE"
            return None
        return None

    def _evaluate_condition(self, condition: str, data: dict):
        """
        Parse và đánh giá điều kiện an toàn.
        Hỗ trợ: temp > 30, gas <= 400, rain == true, hour == 18
        Hỗ trợ AND/OR đơn giản: "temp > 30 and hum < 70"
        """
        condition = condition.strip()
        if not condition:
            return False

        # Ưu tiên tách OR trước
        if " or " in condition or "||" in condition:
            parts = re.split(r"\s+or\s+|\s*\|\|\s*", condition)
            return any(self._evaluate_condition(p, data) for p in parts)

        # Tách AND
        if " and " in condition or "&&" in condition:
            parts = re.split(r"\s+and\s+|\s*&&\s*", condition)
            return all(self._evaluate_condition(p, data) for p in parts)

        # Parse điều kiện đơn
        match = re.match(
            r"^\s*([a-zA-Z_]\w*)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$",
            condition
        )
        if not match:
            return False

        key, op, raw_value = match.groups()
        left = data.get(key)
        if left is None:
            return False

        right = self._parse_value(raw_value)
        if right is None:
            return False

        return self._compare(left, right, op)

    def _parse_value(self, raw_value: str):
        raw_value = raw_value.strip().lower()
        if raw_value in ["true", "false"]:
            return raw_value == "true"

        # Chuỗi có dấu nháy
        if (raw_value.startswith("'") and raw_value.endswith("'")) or \
           (raw_value.startswith('"') and raw_value.endswith('"')):
            return raw_value[1:-1]

        # Số nguyên hoặc float
        if re.match(r"^-?\d+(\.\d+)?$", raw_value):
            return float(raw_value) if "." in raw_value else int(raw_value)

        return None

    def _compare(self, left, right, op: str):
        try:
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            if op == ">":
                return left > right
            if op == "<":
                return left < right
            if op == ">=":
                return left >= right
            if op == "<=":
                return left <= right
        except Exception:
            return False
        return False
