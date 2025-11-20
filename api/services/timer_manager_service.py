from typing import Dict, Optional
import time
import asyncio
from threading import Timer
from api.services.bert_autocorrector_service import AutoCorrectorService
from api.services.translation_service import translate_text
from engine_bridge.text_to_speech import bridge_tts

class TimerManagerService:

    def __init__(self):
        self.autocorrector_service = AutoCorrectorService()
        self.active_timers: Dict[str, Dict] = {}

        self.PAUSE_THRESHOLD = 2.0
        self.PHRASE_TIMEOUT = 5.0

    def start_word_timer(self, session_id: str):

        self._cancel_timer(session_id, 'word')

        timer = Timer(self.PAUSE_THRESHOLD, self._auto_finish_word, [session_id])
        timer.start()

        if session_id not in self.active_timers:
            self.active_timers[session_id] = {}
        self.active_timers[session_id]['word'] = timer

    def start_phrase_timer(self, session_id: str):

        self._cancel_timer(session_id, 'phrase')

        timer = Timer(self.PHRASE_TIMEOUT, self._auto_finish_phrase, [session_id])
        timer.start()

        if session_id not in self.active_timers:
            self.active_timers[session_id] = {}
        self.active_timers[session_id]['phrase'] = timer

    def reset_timers(self, session_id: str):
        self._cancel_timer(session_id, 'word')
        self._cancel_timer(session_id, 'phrase')

    def _cancel_timer(self, session_id: str, timer_type: str):

        if session_id in self.active_timers and timer_type in self.active_timers[session_id]:
            timer = self.active_timers[session_id][timer_type]
            timer.cancel()
            del self.active_timers[session_id][timer_type]

    def _auto_finish_word(self, session_id: str):

        try:
            if session_id not in self.autocorrector_service.sessions:
                return

            session = self.autocorrector_service.sessions[session_id]
            autocorrector = session["autocorrector"]

            if autocorrector.word_buffer and not session.get("word_finalized", False):
                word = autocorrector.finish_word()
                session["word_finalized"] = True

                if autocorrector.sentence_words:
                    self.start_phrase_timer(session_id)

        except Exception:
            pass

    def _auto_finish_phrase(self, session_id: str):

        try:
            if session_id not in self.autocorrector_service.sessions:
                return

            session = self.autocorrector_service.sessions[session_id]
            autocorrector = session["autocorrector"]

            if autocorrector.sentence_words:
                final_sentence = autocorrector.end_sentence()
                if final_sentence.strip():
                    user_prefs = session.get("user_preferences", {})

                    translated_sentence = None
                    if user_prefs.get("auto_translate", False) and user_prefs.get("target_language"):
                        translated_sentence = translate_text(final_sentence, user_prefs["target_language"])

                    if user_prefs.get("tts_enabled", True):
                        text_for_tts = translated_sentence if translated_sentence else final_sentence
                        lang_for_tts = user_prefs.get("target_language", "es") if translated_sentence else "es"
                        bridge_tts.speak_text_async(text_for_tts, lang_for_tts)

                    session["sentence_completed"] = True
                    session["completed_sentence"] = final_sentence
                    if translated_sentence:
                        session["translated_sentence"] = translated_sentence

        except Exception:
            pass

    def get_timer_status(self, session_id: str) -> Dict:

        if session_id not in self.active_timers:
            return {"word_timer": False, "phrase_timer": False}

        return {
            "word_timer": "word" in self.active_timers[session_id],
            "phrase_timer": "phrase" in self.active_timers[session_id],
            "timers_active": len(self.active_timers[session_id]) > 0
        }

timer_manager_service = TimerManagerService()