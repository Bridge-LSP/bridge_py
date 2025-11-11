import json
import os
import time
from collections import defaultdict

class AutoCorrectorStorage:
    def __init__(self, learning_file):
        self.learning_file = learning_file

        self.successful_sentences_file = "dataset_bridge/successful_sentences.json"
        self.weighted_corrections_file = "dataset_bridge/weighted_corrections.json"
        self.correction_feedback_file = "dataset_bridge/correction_feedback.json"

        self.learned_corrections = defaultdict(lambda: {"corrections": [], "count": 0})
        self.sequence_patterns = defaultdict(int)
        self.successful_sentences = []
        self.weighted_corrections = defaultdict(float)
        self.correction_feedback = defaultdict(lambda: {"positive": 0, "negative": 0, "error_count": 0})
        self.correction_blacklist = set()
        self.pending_sentence_confirmation = None

        self._load_all()

    def _load_all(self):
        self._load_json_file(self.learning_file, self._parse_learned_corrections)
        self._load_json_file(self.successful_sentences_file, self._parse_successful_sentences)
        self._load_json_file(self.weighted_corrections_file, self._parse_weighted_corrections)
        self._load_json_file(self.correction_feedback_file, self._parse_feedback)

    def _load_json_file(self, path, parser):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    parser(data)
        except Exception as e:
            print(f"⚠️ Error al cargar {path}: {e}")

    def _parse_learned_corrections(self, data):
        for word, info in data.get('corrections', {}).items():
            if isinstance(info, dict) and "corrections" in info:
                self.learned_corrections[word] = info
            else:
                self.learned_corrections[word] = {
                    "corrections": [{
                        "correct_word": info.get("word", ""),
                        "context": "",
                        "count": info.get("count", 1)
                    }],
                    "count": info.get("count", 1)
                }
        self.sequence_patterns.update(data.get('patterns', {}))
        print(f"📚 Cargadas {len(self.learned_corrections)} correcciones")

    def _parse_successful_sentences(self, data):
        self.successful_sentences = data.get('sentences', [])
        print(f"📚 Cargadas {len(self.successful_sentences)} frases exitosas")

    def _parse_weighted_corrections(self, data):
        self.weighted_corrections.update(data.get('weights', {}))

    def _parse_feedback(self, data):
        self.correction_feedback.update(data.get('feedback', {}))
        self.correction_blacklist = set(data.get('blacklist', []))

    def _save_json(self, path, data):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Error al guardar {path}: {e}")

    def save_learned_corrections(self):
        self._save_json(self.learning_file, {
            'corrections': dict(self.learned_corrections),
            'patterns': dict(self.sequence_patterns),
            'last_updated': time.time()
        })

    def save_successful_sentences(self):
        self._save_json(self.successful_sentences_file, {
            'sentences': self.successful_sentences,
            'total_sentences': len(self.successful_sentences),
            'last_updated': time.time()
        })

    def save_weighted_corrections(self):
        self._save_json(self.weighted_corrections_file, {
            'weights': dict(self.weighted_corrections),
            'last_updated': time.time()
        })

    def save_correction_feedback(self):
        self._save_json(self.correction_feedback_file, {
            'feedback': dict(self.correction_feedback),
            'blacklist': list(self.correction_blacklist),
            'last_updated': time.time()
        })

    def learn_correction(self, wrong_word, correct_word, context=None, word_position=-1):
        if not wrong_word or not correct_word or wrong_word == correct_word:
            return

        wrong_key = wrong_word.lower()
        correct_lower = correct_word.lower()
        context_key = self._build_context_key(context)

        existing = next((c for c in self.learned_corrections[wrong_key]["corrections"]
                         if c.get("context", "") == context_key), None)

        if existing:
            existing["correct_word"] = correct_lower
            existing["count"] += 1
        else:
            self.learned_corrections[wrong_key]["corrections"].append({
                "correct_word": correct_lower,
                "count": 1,
                "context": context_key,
                "position_in_sentence": word_position
            })

        self.learned_corrections[wrong_key]["count"] += 1

        pattern = f"{wrong_key}->{correct_lower}"
        if context_key:
            pattern += f"[ctx:{context_key}]"
        self.sequence_patterns[pattern] += 1

        self.save_learned_corrections()
        print(f"🧠 Aprendido: '{wrong_word}' → '{correct_word}'")

    def _build_context_key(self, context):
        if not context:
            return ""
        return " ".join(context[-3:] if len(context) >= 3 else context).lower()

    def get_learned_suggestion_weighted(self, word, context=None):
        word_key = word.lower()
        corrections = self.learned_corrections.get(word_key, {}).get("corrections", [])

        if not corrections:
            return None

        context_key = self._build_context_key(context)
        valid = []

        for c in corrections:
            key = f"{word_key}->{c['correct_word']}"
            if key in self.correction_blacklist:
                continue

            base = c["count"]
            bonus = self.weighted_corrections.get(key, 0.0)
            feedback = self.correction_feedback.get(key, {})
            penalty = feedback.get("negative", 0)

            score = base + (bonus * 2) - (penalty * 0.3)
            if score > 0:
                c["weighted_score"] = score
                valid.append(c)

        if not valid:
            return None

        for c in valid:
            if c["context"] == context_key:
                return c["correct_word"]

        return max(valid, key=lambda x: x["weighted_score"])["correct_word"]

    def set_pending_confirmation(self, sentence_record):
        self.pending_sentence_confirmation = sentence_record

    def confirm_sentence_quality(self, is_correct=True, user_satisfaction=3):
        record = self.pending_sentence_confirmation
        if not record:
            print("❌ No hay frase pendiente de confirmación")
            return False

        record["user_confirmed"] = is_correct
        record["user_satisfaction"] = user_satisfaction
        record["confirmation_timestamp"] = time.time()

        for detail in record["words_details"]:
            if not detail["was_corrected"]:
                continue

            key = f"{detail['original'].lower()}->{detail['corrected'].lower()}"
            feedback = self.correction_feedback[key]

            if is_correct and user_satisfaction >= 3:
                feedback["positive"] += 1
                self.weighted_corrections[key] += user_satisfaction * 0.2
            else:
                feedback["negative"] += 1

        if is_correct and user_satisfaction >= 3:
            self.successful_sentences.append(record)
            self.save_successful_sentences()
            self.save_weighted_corrections()
            print("✅ Frase confirmada y guardada")
        else:
            print("❌ Frase no guardada - feedback negativo registrado")

        self.save_correction_feedback()
        self.pending_sentence_confirmation = None
        return True

    def clean_ineffective_corrections(self):
        cleaned = 0
        initial_count = len(self.learned_corrections)
        keys_to_delete = []

        for word_key, data in self.learned_corrections.items():
            keep = []
            for c in data["corrections"]:
                key = f"{word_key}->{c['correct_word']}"
                if key in self.correction_blacklist:
                    cleaned += 1
                    continue

                feedback = self.correction_feedback.get(key, {})
                total = feedback.get("positive", 0) + feedback.get("negative", 0)

                if total >= 5 and feedback.get("positive", 0) / total < 0.3:
                    self.correction_blacklist.add(key)
                    cleaned += 1
                    continue

                keep.append(c)

            if keep:
                data["corrections"] = keep
                data["count"] = sum(c["count"] for c in keep)
            else:
                keys_to_delete.append(word_key)

        for k in keys_to_delete:
            del self.learned_corrections[k]
            cleaned += 1

        if cleaned:
            self.save_learned_corrections()
            self.save_correction_feedback()
            print(f"🧹 Limpieza: {cleaned} correcciones eliminadas")

        return {
            "cleaned_corrections": cleaned,
            "total_before": initial_count,
            "total_after": len(self.learned_corrections)
        }