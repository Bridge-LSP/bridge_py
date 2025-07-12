import time
from collections import defaultdict, Counter
import Levenshtein

# === CLASE ANALÍTICA DEL AUTOCORRECTOR ===
class AutoCorrectorAnalytics:
    def __init__(self, autocorrector):
        self.autocorrector = autocorrector
        self.storage = autocorrector.storage

    # === CREACIÓN DE REGISTROS DE FRASES ===
    def create_sentence_record(self, words_feedback, sentence_words, session_start_time, corrections_made):
        if not words_feedback:
            return None

        original = " ".join(info["raw_word"] for info in words_feedback)
        corrected = " ".join(sentence_words)
        duration = time.time() - (session_start_time or time.time())
        ratio = self.calculate_levenshtein_ratio(original, corrected)
        coherence = self.evaluate_semantic_coherence(corrected)

        return {
            "id": f"sentence_{int(time.time())}_{len(self.storage.successful_sentences)}",
            "timestamp": time.time(),
            "original_sentence": original,
            "corrected_sentence": corrected,
            "word_count": len(sentence_words),
            "corrections_made": corrections_made,
            "correction_ratio_advanced": ratio,
            "semantic_coherence": coherence,
            "session_duration_seconds": round(duration, 2),
            "words_details": self._build_words_details(words_feedback, sentence_words),
            "difficulty_score": self._calculate_difficulty_score(original, corrected, coherence),
            "context_quality": self._assess_context_quality(coherence, ratio),
            "requires_confirmation": True,
            "user_confirmed": False
        }

    def _build_words_details(self, feedback, corrected_words):
        return [
            {
                "position": i,
                "original": info["raw_word"],
                "corrected": corrected_words[i],
                "was_corrected": info["raw_word"].lower() != corrected_words[i].lower(),
                "levenshtein_distance": Levenshtein.distance(info["raw_word"].lower(), corrected_words[i].lower())
            }
            for i, info in enumerate(feedback)
        ]

    # === MÉTRICAS DE EVALUACIÓN DE CALIDAD ===
    def calculate_levenshtein_ratio(self, original: str, corrected: str) -> float:
        orig_words = original.lower().split()
        corr_words = corrected.lower().split()
        total = max(len(orig_words), len(corr_words))
        if total == 0: return 0.0

        score = sum(
            (Levenshtein.distance(orig_words[i], corr_words[i]) / max(len(orig_words[i]), len(corr_words[i]))
             if i < len(orig_words) and i < len(corr_words) and max(len(orig_words[i]), len(corr_words[i])) > 0
             else 1.0)
            for i in range(total)
        )
        return round(score / total, 3)

    def evaluate_semantic_coherence(self, sentence: str) -> float:
        if not self.autocorrector.model_loaded or not sentence:
            return 0.5

        words = sentence.split()
        if len(words) < 2:
            return 0.8

        total_score, evaluations = 0.0, 0

        for i, word in enumerate(words):
            context = words.copy()
            context[i] = "[MASK]"
            try:
                predictions = self.autocorrector.nlp(" ".join(context), top_k=10)
                found = next((j for j, p in enumerate(predictions) if p["token_str"].lower() == word.lower()), None)
                total_score += max(0.1, 1.0 - (found / 10)) if found is not None else 0.1
                evaluations += 1
            except Exception:
                evaluations += 1

        return round(min(1.0, total_score / evaluations), 3) if evaluations else 0.5

    # === ESTADÍSTICAS DE APRENDIZAJE Y SALUD ===
    def get_learning_stats(self) -> dict:
        learned = self.storage.learned_corrections
        return {
            "total_corrections": len(learned),
            "corrections_per_word": {w: len(d["corrections"]) for w, d in learned.items()},
            "most_corrected_words": sorted(((w, len(d["corrections"])) for w, d in learned.items()), key=lambda x: x[1], reverse=True)[:5],
            "successful_sentences": len(self.storage.successful_sentences),
            "pending_confirmation": self.storage.pending_sentence_confirmation is not None,
            "blacklisted_corrections": len(self.storage.correction_blacklist)
        }

    def get_correction_health_report(self) -> dict:
        feedback = self.storage.correction_feedback
        positives = sum(f["positive"] for f in feedback.values())
        negatives = sum(f["negative"] for f in feedback.values())
        total = positives + negatives
        rate = positives / total if total else 0

        return {
            "total_corrections": len(self.storage.learned_corrections),
            "blacklisted_corrections": len(self.storage.correction_blacklist),
            "feedback_stats": {
                "total_feedback_events": total,
                "positive_feedback": positives,
                "negative_feedback": negatives,
                "success_rate": round(rate * 100, 2)
            },
            "recommendations": self._get_health_recommendations(rate, len(self.storage.correction_blacklist), len(self.storage.learned_corrections))
        }

    # === SUGERENCIAS PARA ENTRENAMIENTO CON BERT ===
    def get_bert_training_suggestions(self) -> dict:
        sentences = [
            s for s in self.storage.successful_sentences
            if s.get("context_quality") in ["excellent", "good"] and s.get("user_confirmed")
        ]
        if len(sentences) < 5:
            return {"message": "Necesitas al menos 5 frases de alta calidad"}

        training_data, mistakes = [], defaultdict(int)

        for s in sentences:
            orig_words = s["original_sentence"].split()
            for d in s["words_details"]:
                if d["was_corrected"]:
                    masked = orig_words.copy()
                    masked[d["position"]] = "[MASK]"
                    key = f"{d['original']}->{d['corrected']}"
                    training_data.append({
                        "input": " ".join(masked),
                        "target": d["corrected"],
                        "original_word": d["original"],
                        "correction_type": self._classify_correction_type(d["original"], d["corrected"])
                    })
                    mistakes[key] += 1

        return {
            "training_examples": len(training_data),
            "high_quality_sentences": len(sentences),
            "training_data": training_data[:50],
            "most_common_mistakes": dict(Counter(mistakes).most_common(10))
        }

    # === CLASIFICADORES INTERNOS Y RECOMENDACIONES ===
    def _calculate_difficulty_score(self, original, corrected, coherence):
        wc = len(original.split())
        ratio = self.calculate_levenshtein_ratio(original, corrected)
        score = (0.1 if wc <= 3 else 0.3 if wc <= 6 else 0.5) + (ratio * 0.4) + ((1 - coherence) * 0.5)
        return "easy" if score <= 0.3 else "medium" if score <= 0.6 else "hard" if score <= 0.8 else "very_hard"

    def _assess_context_quality(self, coherence, correction_ratio):
        q = coherence * 0.7 + (1.0 - correction_ratio) * 0.3
        return "excellent" if q >= 0.8 else "good" if q >= 0.6 else "fair" if q >= 0.4 else "poor"

    def _classify_correction_type(self, original, corrected):
        d = Levenshtein.distance(original.lower(), corrected.lower())
        len_diff = abs(len(original) - len(corrected))
        if d == 0: return "no_change"
        if d == 1 and len_diff == 0: return "substitution"
        if d == 1 and len_diff == 1: return "insertion" if len(corrected) > len(original) else "deletion"
        if len_diff > 2: return "major_rewrite"
        return "minor_edit"

    def _get_health_recommendations(self, success_rate, blacklisted, total):
        recs = []
        if success_rate < 0.7:
            recs.append("⚠️ Tasa de éxito baja - Revisar calidad de correcciones")
        if total > 0 and blacklisted / total > 0.1:
            recs.append("🧹 Alto número de correcciones blacklisted")
        if total < 10:
            recs.append("📚 Pocas correcciones aprendidas")
        return recs or ["✅ Sistema funcionando correctamente"]