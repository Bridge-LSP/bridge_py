from engine_bridge.autocorrector.autocorrector_core import AutoCorrector
from typing import Dict, List, Optional
import time

class AutoCorrectorService:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}

    def create_session(self, session_id: str) -> Dict:

        try:
            if not session_id or not isinstance(session_id, str):
                raise ValueError("session_id must be a non-empty string")

            self.sessions[session_id] = {
                "autocorrector": AutoCorrector(),
                "sentence": "",
                "last_letter_time": 0,
                "word_finalized": False,
                "last_corrected_word": "",
                "PAUSE_THRESHOLD": 3.0,
                "session_start_time": time.time()
            }

            print(f"[Bridge] Session created successfully: {session_id}")
            return {"session_id": session_id, "status": "created"}

        except Exception as e:
            print(f"[Bridge] Error creating session {session_id}: {str(e)}")
            raise e

    def add_letter(self, session_id: str, letter: str) -> Dict:

        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        session["autocorrector"].add_letter(letter.lower())
        session["last_letter_time"] = time.time()
        session["word_finalized"] = False

        return {
            "letter_added": letter.upper(),
            "current_buffer": ''.join(session["autocorrector"].word_buffer),
            "predicted_word": session["autocorrector"].get_current_word_corrected()
        }

    def finish_word(self, session_id: str, force: bool = False) -> Dict:

        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        current_time = time.time()

        auto_finish = (session["autocorrector"].word_buffer and
                      current_time - session["last_letter_time"] > session["PAUSE_THRESHOLD"] and
                      not session["word_finalized"])

        if force or auto_finish:
            corrected_word = session["autocorrector"].finish_word()
            if corrected_word and corrected_word.strip():
                if session["sentence"]:
                    session["sentence"] += " " + corrected_word
                else:
                    session["sentence"] = corrected_word

                session["last_corrected_word"] = corrected_word
                session["word_finalized"] = True

                return {
                    "word_completed": corrected_word,
                    "sentence": session["sentence"],
                    "auto_finished": auto_finish
                }

        return {"message": "Word not ready to finish"}

    def get_session_status(self, session_id: str) -> Dict:

        if session_id not in self.sessions:
            print(f"[Bridge] Session not found: {session_id}")
            return {"error": "Session not found"}

        try:
            session = self.sessions[session_id]
            current_time = time.time()

            should_auto_finish = (session["autocorrector"].word_buffer and
                                 current_time - session["last_letter_time"] > session["PAUSE_THRESHOLD"] and
                                 not session["word_finalized"])

            try:
                sentence_string = session["autocorrector"].get_sentence_string()
            except AttributeError:
                sentence_string = " ".join(session["autocorrector"].sentence_words) if hasattr(session["autocorrector"], 'sentence_words') else ""

            try:
                sentence_words = session["autocorrector"].get_sentence_words()
            except AttributeError:
                sentence_words = [(i, word) for i, word in enumerate(session["autocorrector"].sentence_words)] if hasattr(session["autocorrector"], 'sentence_words') else []

            try:
                learning_stats = session["autocorrector"].get_learning_stats()
            except (AttributeError, Exception):
                learning_stats = {"total_corrections": 0, "accuracy": 0.0}

            return {
                "current_buffer": ''.join(session["autocorrector"].word_buffer),
                "predicted_word": session["autocorrector"].get_current_word_corrected(),
                "sentence": sentence_string,
                "sentence_words": sentence_words,
                "should_auto_finish": should_auto_finish,
                "last_corrected_word": session["last_corrected_word"],
                "learning_stats": learning_stats
            }

        except Exception as e:
            print(f"[Bridge] Error getting session status for {session_id}: {str(e)}")
            return {"error": f"Error getting session status: {str(e)}"}

    def provide_feedback(self, session_id: str, correct_word: str) -> Dict:

        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        success = session["autocorrector"].provide_feedback(correct_word)

        return {
            "feedback_applied": success,
            "learned_correction": f"{session['autocorrector'].last_raw_word} -> {correct_word}" if success else None
        }

    def provide_feedback_for_word(self, session_id: str, word_position: int, correct_word: str) -> Dict:

        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        success = session["autocorrector"].provide_feedback_for_word(word_position, correct_word)

        return {
            "feedback_applied": success,
            "word_position": word_position,
            "corrected_to": correct_word
        }

    def remove_word(self, session_id: str, word_position: int) -> Dict:

        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        success = session["autocorrector"].remove_word(word_position)

        return {
            "word_removed": success,
            "word_position": word_position
        }

    def end_sentence(self, session_id: str) -> Dict:

        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        final_sentence = session["autocorrector"].end_sentence()

        return {
            "final_sentence": final_sentence,
            "sentence_ended": True
        }

    def reset_session(self, session_id: str) -> Dict:

        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        session["autocorrector"].clear_buffer()
        session["sentence"] = ""
        session["word_finalized"] = False
        session["last_corrected_word"] = ""

        return {"message": "Session reset"}

    def delete_session(self, session_id: str) -> Dict:

        if session_id in self.sessions:
            del self.sessions[session_id]
            return {"message": "Session deleted"}
        return {"error": "Session not found"}

    def get_correction_health_report(self, session_id: str) -> Dict:

        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        health_report = session["autocorrector"].get_correction_health_report()

        return {
            "session_id": session_id,
            "health_report": health_report
        }

    def clean_ineffective_corrections(self, session_id: str) -> Dict:

        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        cleanup_result = session["autocorrector"].clean_ineffective_corrections()

        return {
            "session_id": session_id,
            "cleanup_result": cleanup_result
        }

    def get_bert_training_suggestions(self, session_id: str) -> Dict:

        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        suggestions = session["autocorrector"].get_bert_training_suggestions()

        return {
            "session_id": session_id,
            "bert_suggestions": suggestions
        }
    def get_word_building_status(self, session_id: str) -> Dict:

        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        autocorrector = session["autocorrector"]
        current_time = time.time()

        try:
            stats = autocorrector.get_learning_stats()
            sentence_stats = autocorrector.get_successful_sentences_stats()
        except:
            stats = {"total_corrections": 0}
            sentence_stats = {"total": 0}

        return {
            "session_id": session_id,
            "current_buffer": ''.join(autocorrector.word_buffer),
            "buffer_length": len(autocorrector.word_buffer),
            "predicted_word": autocorrector.get_current_word_corrected(),
            "sentence": autocorrector.get_sentence_string(),
            "sentence_words": [word for i, word in autocorrector.get_sentence_words()],
            "word_count": len(autocorrector.sentence_words) if hasattr(autocorrector, 'sentence_words') else 0,
            "should_auto_finish": len(autocorrector.word_buffer) >= 3,
            "last_corrected_word": session.get("last_corrected_word", ""),
            "learning_stats": stats,
            "sentence_stats": sentence_stats,
            "user_preferences": session.get("user_preferences", {}),
            "session_active": True,
            "last_activity": current_time - session["last_letter_time"] if session["last_letter_time"] > 0 else 0
        }

    def reset_session_completely(self, session_id: str) -> Dict:

        if session_id not in self.sessions:
            return {"error": "Session not found"}

        old_preferences = self.sessions[session_id].get("user_preferences", {})

        self.sessions[session_id] = {
            "autocorrector": AutoCorrector(),
            "sentence": "",
            "last_letter_time": 0,
            "word_finalized": False,
            "last_corrected_word": "",
            "PAUSE_THRESHOLD": 3.0,
            "user_preferences": old_preferences
        }

        return {
            "session_id": session_id,
            "status": "reset_complete",
            "message": "Session completely reset",
            "preferences_preserved": len(old_preferences) > 0
        }

    def update_user_preferences(self, session_id: str, preferences: Dict) -> Dict:

        if session_id not in self.sessions:
            self.create_session(session_id)

        session = self.sessions[session_id]
        session["user_preferences"] = {
            "text_language": preferences.get("text_language", "es"),
            "voice_language": preferences.get("voice_language", "es"),
            "auto_translate": preferences.get("auto_translate", False),
            "target_language": preferences.get("target_language"),
            "tts_enabled": preferences.get("tts_enabled", True),
            "voice_speed": preferences.get("voice_speed", 1.0),
            "voice_pitch": preferences.get("voice_pitch", 1.0)
        }

        return {
            "session_id": session_id,
            "preferences_updated": True,
            "preferences": session["user_preferences"]
        }

    def get_session_analytics(self, session_id: str) -> Dict:

        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        autocorrector = session["autocorrector"]

        try:
            learning_stats = autocorrector.get_learning_stats()
            sentence_stats = autocorrector.get_successful_sentences_stats()
            health_report = autocorrector.get_correction_health_report()

            return {
                "session_id": session_id,
                "session_duration": time.time() - session.get("session_start_time", time.time()),
                "learning_stats": learning_stats,
                "sentence_stats": sentence_stats,
                "health_report": health_report,
                "current_session_info": {
                    "words_in_current_sentence": len(autocorrector.sentence_words) if hasattr(autocorrector, 'sentence_words') else 0,
                    "letters_in_buffer": len(autocorrector.word_buffer),
                    "last_activity": time.time() - session["last_letter_time"] if session["last_letter_time"] > 0 else 0
                }
            }
        except Exception as e:
            return {"error": f"Analytics not available: {str(e)}"}

autocorrector_service = AutoCorrectorService()