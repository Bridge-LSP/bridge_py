from transformers import pipeline, AutoTokenizer, AutoModelForMaskedLM
from spellchecker import SpellChecker
import Levenshtein
import time
from .autocorrector_storage import AutoCorrectorStorage
from .autocorrector_analytics import AutoCorrectorAnalytics

class AutoCorrector:
    def __init__(self, learning_file="dataset_bridge/dataset_bert.json"):
        self.spell = SpellChecker(language='es')
        self.storage = AutoCorrectorStorage(learning_file)
        self.analytics = AutoCorrectorAnalytics(self)
        self._load_bert_model()
        self._reset_session()

    def _load_bert_model(self):
        try:
            model_name = "dccuchile/bert-base-spanish-wwm-uncased"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForMaskedLM.from_pretrained(model_name)
            self.nlp = pipeline('fill-mask', model=self.model, tokenizer=self.tokenizer)
            self.model_loaded = True
        except Exception:
            self.model_loaded = False

    def add_letter(self, letter):
        self.word_buffer.append(letter)

    def get_current_word_corrected(self):
        return self._correct_word(''.join(self.word_buffer), self.current_context)

    def finish_word(self):
        if not self.word_buffer:
            return ""
        if not self.session_start_time:
            self._start_session()

        raw_word = ''.join(self.word_buffer)
        corrected = self._correct_word(raw_word, self.current_context)
        self._update_context(corrected)
        self._store_feedback(raw_word, corrected)
        self.word_buffer.clear()
        return corrected

    def end_sentence(self):
        if not self.sentence_words:
            return ""

        sentence = " ".join(self.sentence_words)
        if self.words_feedback:
            record = self.analytics.create_sentence_record(
                self.words_feedback, self.sentence_words,
                self.session_start_time, self.corrections_made_in_session
            )
            self.storage.set_pending_confirmation(record)

        self._reset_session()
        return sentence

    def provide_feedback_for_word(self, index, correct_word):
        if 0 <= index < len(self.words_feedback):
            word_info = self.words_feedback[index]
            self.storage.learn_correction(
                word_info["raw_word"], correct_word, word_info["context"], index
            )
            self.sentence_words[index] = correct_word
            return True
        return False

    def confirm_sentence(self, is_correct=True, satisfaction=4):
        return self.storage.confirm_sentence_quality(is_correct, satisfaction)

    def confirm_sentence_quality(self, is_correct, satisfaction=4):
        return self.confirm_sentence(is_correct, satisfaction)

    def remove_word(self, index):
        if 0 <= index < len(self.sentence_words):
            removed = self.sentence_words.pop(index)
            if index < len(self.words_feedback):
                self.words_feedback.pop(index)
            return True
        return False

    def clear_buffer(self):
        self.word_buffer.clear()

    def _correct_word(self, word, context):
        if not word or len(word) < 2:
            return word

        learned = self.storage.get_learned_suggestion_weighted(word, context)
        if learned:
            return learned.capitalize() if word[0].isupper() else learned

        if word.lower() in self.spell:
            return word

        candidates = self.spell.candidates(word.lower())
        if candidates:
            best = min(candidates, key=lambda x: Levenshtein.distance(word.lower(), x))
            return best.capitalize() if word[0].isupper() else best

        return word

    def _start_session(self):
        self.session_start_time = time.time()
        self.corrections_made_in_session = 0

    def _update_context(self, word):
        self.current_context.append(word.lower())
        if len(self.current_context) > 10:
            self.current_context.pop(0)

    def _store_feedback(self, raw_word, corrected):
        self.sentence_words.append(corrected)
        self.words_feedback.append({
            "raw_word": raw_word,
            "corrected_word": corrected,
            "context": self.current_context.copy()
        })

    def _reset_session(self):
        self.word_buffer = []
        self.current_context = []
        self.sentence_words = []
        self.words_feedback = []
        self.session_start_time = None
        self.corrections_made_in_session = 0

    @property
    def sentence_feedback_requested(self):
        return self.storage.pending_sentence_confirmation is not None

    @property
    def pending_sentence_confirmation(self):
        return self.storage.pending_sentence_confirmation

    @property
    def pos_analysis_enabled(self):
        return False

    def get_sentence_string(self):
        return " ".join(self.sentence_words)

    def get_sentence_words(self):
        return list(enumerate(self.sentence_words))

    def get_stats(self):
        return self.analytics.get_learning_stats()

    def get_learning_stats(self):
        return self.get_stats()

    def get_successful_sentences_stats(self):
        total = len(self.storage.successful_sentences)
        return {
            "total": total,
            "avg_words_per_sentence": self._avg("word_count"),
            "avg_corrections_per_sentence": self._avg("corrections_made"),
            "quality_distribution": self._distribution("context_quality")
        }

    def get_correction_health_report(self):
        return self.analytics.get_correction_health_report()

    def clean_bad_corrections(self):
        return self.storage.clean_ineffective_corrections()

    def clean_ineffective_corrections(self):
        return self.clean_bad_corrections()

    def get_bert_training_suggestions(self):
        return self.analytics.get_bert_training_suggestions()

    def _avg(self, key):
        records = self.storage.successful_sentences
        return round(sum(s.get(key, 0) for s in records) / len(records), 1) if records else 0

    def _distribution(self, key):
        distribution = {}
        for s in self.storage.successful_sentences:
            val = s.get(key, "unknown")
            distribution[val] = distribution.get(val, 0) + 1
        return distribution