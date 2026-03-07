from datetime import datetime, timedelta
import os
import re
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


class SmartHomeAI:
    """
    AI Smart Home: học intent, alias, luật tự động và học từ hành vi.
    An toàn: không dùng eval(), parse điều kiện theo mẫu đơn giản.
    """

    VALID_RULE_KEYS = frozenset({"hour", "temp", "hum", "gas", "rain", "pir", "flame", "door"})
    MIN_PATTERN_COUNT = 3

    def __init__(self, db):
        self.db = db
        self.col_intents = db["ai_intents"]
        self.col_alias = db["ai_alias"]
        self.col_rules = db["ai_rules"]
        self.col_actions = db["user_actions"]
        self.col_sensor = db["sensor_data"]
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
        print(f"[AI RULE CREATED] {condition} -> {action}")
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

        intent = self._match_intent(text_norm)
        if intent:
            return intent

        device = self._match_alias(text_norm)
        if device:
            action = self._detect_action(text_norm)
            if action:
                return self._build_command(device, action)

        ml_action = self._predict_intent(text_norm)
        if ml_action:
            return ml_action

        action = self._detect_action(text_norm)
        if action:
            device = self._detect_device(text_norm)
            if device:
                return self._build_command(device, action)

        return None

    def auto_decision(self, sensor_data: dict):
        """Áp dụng rule từ MongoDB với sensor_data. Trả về list MQTT commands."""
        commands = []
        data = self._enrich_sensor_with_context(sensor_data)

        rules = self.col_rules.find({"condition": {"$exists": True, "$ne": ""}})
        for rule in rules:
            condition = rule.get("condition", "")
            action = rule.get("action", "").upper()
            if condition and action and self._evaluate_condition(condition, data):
                commands.append(action)
        return commands

    # ================== LEARNING ==================
    def learn_from_sensor_behavior(self):
        """
        Học từ user_actions + sensor_data.
        Nếu cùng lệnh được thực thi >= 3 lần trong điều kiện cảm biến tương tự => tạo rule.
        """
        learned = 0
        cutoff = datetime.now() - timedelta(days=14)
        actions = list(self.col_actions.find(
            {"timestamp": {"$gte": cutoff}, "command": {"$exists": True, "$ne": ""}}
        ).sort("timestamp", -1).limit(500))

        if not actions:
            return {"learned_rules": 0}

        sensor_cursor = self.col_sensor.find(
            {"timestamp": {"$gte": cutoff}}
        ).sort("timestamp", 1)
        sensor_list = list(sensor_cursor)

        def find_sensor_at(t):
            if not sensor_list:
                return None
            best = None
            best_diff = float("inf")
            for s in sensor_list:
                ts = s.get("timestamp")
                if not ts:
                    continue
                diff = abs((ts - t).total_seconds())
                if diff <= 300 and diff < best_diff:
                    best_diff = diff
                    best = s
            return best

        by_command = {}
        for a in actions:
            ts = a.get("timestamp")
            cmd = a.get("command", "").strip().upper()
            if not ts or not cmd:
                continue
            s = find_sensor_at(ts)
            if s is None:
                continue
            if cmd not in by_command:
                by_command[cmd] = []
            by_command[cmd].append(s)

        for cmd, sensors in by_command.items():
            if len(sensors) < self.MIN_PATTERN_COUNT:
                continue

            temps = [s.get("temp") for s in sensors if s.get("temp") is not None and isinstance(s.get("temp"), (int, float))]
            hums = [s.get("hum") for s in sensors if s.get("hum") is not None and isinstance(s.get("hum"), (int, float))]
            rains = [s.get("rain") for s in sensors if s.get("rain") is not None]
            gas_vals = [s.get("gas") for s in sensors if s.get("gas") is not None]

            conditions = []

            if len(temps) >= self.MIN_PATTERN_COUNT:
                min_temp = min(temps)
                if min_temp >= 25:
                    thresh = int(min_temp) - 1
                    conditions.append(f"temp >= {thresh}")

            if len(rains) >= self.MIN_PATTERN_COUNT and sum(1 for r in rains if r) >= self.MIN_PATTERN_COUNT:
                conditions.append("rain == true")

            if len(gas_vals) >= self.MIN_PATTERN_COUNT:
                min_gas = min(gas_vals)
                if min_gas >= 300:
                    thresh = int(min_gas) - 50
                    conditions.append(f"gas >= {max(0, thresh)}")

            if not conditions:
                continue

            cond_str = " and ".join(conditions)
            exists = self.col_rules.find_one({"condition": cond_str, "action": cmd})
            if not exists:
                self.col_rules.insert_one({
                    "condition": cond_str,
                    "action": cmd,
                    "created_at": datetime.now(),
                    "source": "learn_from_sensor_behavior"
                })
                print(f"[AI LEARN] Tạo rule từ hành vi: {cond_str} -> {cmd}")
                learned += 1

        return {"learned_rules": learned}

    def learn_patterns(self):
        """
        Phát hiện pattern: cùng lệnh, cùng khoảng giờ, >= 3 lần.
        Tạo rule: hour >= X and hour <= Y -> ACTION
        """
        learned = 0
        cutoff = datetime.now() - timedelta(days=30)
        actions = list(self.col_actions.find(
            {"timestamp": {"$gte": cutoff}, "command": {"$exists": True, "$ne": ""}}
        ).sort("timestamp", -1).limit(500))

        by_cmd = {}
        for a in actions:
            ts = a.get("timestamp")
            cmd = a.get("command", "").strip().upper()
            if not ts or not cmd:
                continue
            hour = ts.hour
            key = cmd
            if key not in by_cmd:
                by_cmd[key] = []
            by_cmd[key].append(hour)

        for cmd, hours in by_cmd.items():
            if len(hours) < self.MIN_PATTERN_COUNT:
                continue
            min_h, max_h = min(hours), max(hours)
            if max_h - min_h > 6:
                continue
            cond = f"hour >= {min_h} and hour <= {max_h}"
            exists = self.col_rules.find_one({"condition": cond, "action": cmd})
            if not exists:
                self.col_rules.insert_one({
                    "condition": cond,
                    "action": cmd,
                    "created_at": datetime.now(),
                    "source": "learn_patterns"
                })
                print(f"[AI RULE CREATED] {cond} -> {cmd} (từ pattern giờ)")
                learned += 1

        return {"learned_rules": learned}

    # ================== CONTEXT ==================
    def detect_context(self, sensor_data: dict) -> dict:
        """
        Phát hiện ngữ cảnh từ sensor_data.
        Trả về: hot, cold, rain, night, day, humid, gas_alert, motion, fire
        """
        data = sensor_data or {}
        now = datetime.now()
        hour = now.hour
        temp = self._safe_float(data.get("temp"), 25.0)
        hum = self._safe_float(data.get("hum"), 60.0)
        gas = self._safe_int(data.get("gas"), 0)
        rain = bool(data.get("rain"))
        pir = bool(data.get("pir"))
        flame = bool(data.get("flame"))

        return {
            "hot": temp >= 30,
            "cold": temp < 20,
            "rain": rain,
            "night": hour >= 18 or hour < 6,
            "day": 6 <= hour < 18,
            "humid": hum >= 70,
            "gas_alert": gas > 400,
            "motion": pir,
            "fire": flame,
        }

    def _safe_float(self, v, default):
        if v is None:
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def _safe_int(self, v, default):
        if v is None:
            return default
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    # ================== RETRAIN ==================
    def retrain_model_if_needed(self) -> bool:
        """
        Retrain nếu:
        - new_intents >= 5 HOẶC
        - last_training > 24 giờ
        """
        meta = self.col_meta.find_one({"_id": "intent_model"}) or {}
        new_count = int(meta.get("new_intents_since_train", 0))
        last_trained = meta.get("last_trained_at")
        now = datetime.now()

        should_train = new_count >= 5
        if last_trained:
            if (now - last_trained).total_seconds() > 86400:
                should_train = True
        else:
            should_train = True

        if not should_train:
            return False

        trained = self._train_intent_model_if_possible()
        if trained:
            self.col_meta.update_one(
                {"_id": "intent_model"},
                {"$set": {
                    "new_intents_since_train": 0,
                    "last_trained_at": now,
                    "trained_count": trained,
                    "updated_at": now
                },
                 "$setOnInsert": {"created_at": now}},
                upsert=True
            )
            print(f"[AI TRAIN] Retrain hoàn tất, {trained} mẫu")
        return bool(trained)

    # ================== UTILITIES ==================
    def _normalize_text(self, text: str):
        text = re.sub(r"\s+", " ", str(text).strip().lower())
        text = re.sub(r"\b(số|so)\b", " ", text)
        text = re.sub(r"\bmột\b", "1", text)
        text = re.sub(r"\bmot\b", "1", text)
        text = re.sub(r"\bhai\b", "2", text)
        text = re.sub(r"\bba\b", "3", text)
        return text

    def _enrich_sensor_with_context(self, data: dict) -> dict:
        """Thêm hour vào sensor_data để rule có thể dùng"""
        d = dict(data) if data else {}
        ts = d.get("timestamp")
        if ts:
            d["hour"] = ts.hour if hasattr(ts, "hour") else datetime.now().hour
        else:
            d["hour"] = datetime.now().hour
        return d

    # ================== ML INTENT CLASSIFIER ==================
    def _load_model_on_startup(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                return
            except Exception:
                self.model = None
        self._train_intent_model_if_possible()

    def _increase_new_intents_and_retrain_if_needed(self):
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
                    {"$set": {
                        "new_intents_since_train": 0,
                        "last_trained_at": datetime.now(),
                        "trained_count": trained
                    }},
                    upsert=True
                )

    def _train_intent_model_if_possible(self):
        """Train model nếu đủ dữ liệu. Đảm bảo texts và labels luôn align."""
        intents = list(self.col_intents.find({"trigger": {"$exists": True, "$ne": ""}}))

        pairs = []
        for it in intents:
            trigger = it.get("trigger", "").strip()
            action = it.get("action", "").strip()
            if trigger and action:
                pairs.append((trigger, action))

        if len(pairs) < 2:
            return 0

        labels_unique = {p[1] for p in pairs}
        if len(labels_unique) < 2:
            return 0

        texts = [p[0] for p in pairs]
        labels = [p[1] for p in pairs]

        model = Pipeline([
            ("tfidf", TfidfVectorizer(
                ngram_range=(1, 3),
                min_df=1,
                max_df=0.9
            )),
            ("clf", LogisticRegression(
                max_iter=2000,
                class_weight="balanced"
            ))
        ])
        model.fit(texts, labels)
        joblib.dump(model, self.model_path)
        self.model = model
        print(f"[AI TRAIN] Đã train {len(texts)} mẫu, {len(labels_unique)} lớp")
        return len(texts)

    def _predict_intent(self, text_norm: str):
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
            short = (text_norm[:40] + "..") if len(text_norm) > 40 else text_norm
            print(f"[AI PREDICT] \"{short}\" -> {pred}")
            return pred
        except Exception:
            return None

    def _match_intent(self, text_norm: str):
        exact = self.col_intents.find_one({"trigger": text_norm}, projection={"action": 1})
        if exact:
            return exact.get("action")

        intents = list(self.col_intents.find({"trigger": {"$exists": True, "$ne": ""}}, projection={"trigger": 1, "action": 1}))
        intents.sort(key=lambda x: len(x.get("trigger", "")), reverse=True)
        for it in intents:
            trigger = it.get("trigger", "")
            if trigger and trigger in text_norm:
                return it.get("action")
        return None

    def _match_alias(self, text_norm: str):
        aliases = list(self.col_alias.find({"alias": {"$exists": True, "$ne": ""}}, projection={"alias": 1, "device": 1}))
        aliases.sort(key=lambda x: len(x.get("alias", "")), reverse=True)
        for al in aliases:
            alias = al.get("alias", "")
            if alias and alias in text_norm:
                return al.get("device")
        return None

    def _detect_action(self, text_norm: str):
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
        Đánh giá điều kiện an toàn (không dùng eval).
        Hỗ trợ: hour, temp, hum, gas, rain, pir, flame, door
        Ví dụ: hour >= 18 and rain == true -> ROOF_CLOSE
        """
        condition = condition.strip()
        if not condition:
            return False

        data = self._enrich_sensor_with_context(data or {})

        if " or " in condition or "||" in condition:
            parts = re.split(r"\s+or\s+|\s*\|\|\s*", condition)
            return any(self._evaluate_condition(p.strip(), data) for p in parts)

        if " and " in condition or "&&" in condition:
            parts = re.split(r"\s+and\s+|\s*&&\s*", condition)
            return all(self._evaluate_condition(p.strip(), data) for p in parts)

        match = re.match(
            r"^\s*([a-zA-Z_]\w*)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$",
            condition
        )
        if not match:
            return False

        key, op, raw_value = match.groups()
        key = key.lower()
        if key not in self.VALID_RULE_KEYS:
            return False

        left = data.get(key)
        if left is None and key == "hour":
            left = datetime.now().hour
        if left is None:
            return False

        right = self._parse_value(raw_value)
        if right is None:
            return False

        return self._compare(left, right, op)

    def _parse_value(self, raw_value: str):
        raw_value = str(raw_value).strip().lower()
        if raw_value in ["true", "false"]:
            return raw_value == "true"

        if (raw_value.startswith("'") and raw_value.endswith("'")) or \
           (raw_value.startswith('"') and raw_value.endswith('"')):
            return raw_value[1:-1]

        if re.match(r"^-?\d+(\.\d+)?$", raw_value):
            return float(raw_value) if "." in raw_value else int(float(raw_value))

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
