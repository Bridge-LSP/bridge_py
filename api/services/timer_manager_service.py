from typing import Dict, Optional
import time
import asyncio
from threading import Timer
from api.services.bert_autocorrector_service import AutoCorrectorService
from api.services.translation_service import translate_text
from engine_bridge.text_to_speech import bridge_tts

class TimerManagerService:
    """
    Servicio que gestiona los timers automáticos para palabras y frases
    Replica la funcionalidad exacta de main.py
    """
    
    def __init__(self):
        self.autocorrector_service = AutoCorrectorService()
        self.active_timers: Dict[str, Dict] = {}
        
        # Configuraciones de timers (idéntico a main.py)
        self.PAUSE_THRESHOLD = 2.0  # 2s para finalizar palabra
        self.PHRASE_TIMEOUT = 5.0   # 5s para finalizar frase
        
    def start_word_timer(self, session_id: str):
        """Inicia timer para auto-finalizar palabra después de 2s"""
        self._cancel_timer(session_id, 'word')
        
        timer = Timer(self.PAUSE_THRESHOLD, self._auto_finish_word, [session_id])
        timer.start()
        
        if session_id not in self.active_timers:
            self.active_timers[session_id] = {}
        self.active_timers[session_id]['word'] = timer
        
        print(f"[Timer] Word timer started for session {session_id} ({self.PAUSE_THRESHOLD}s)")
    
    def start_phrase_timer(self, session_id: str):
        """Inicia timer para auto-finalizar frase después de 5s"""
        self._cancel_timer(session_id, 'phrase')
        
        timer = Timer(self.PHRASE_TIMEOUT, self._auto_finish_phrase, [session_id])
        timer.start()
        
        if session_id not in self.active_timers:
            self.active_timers[session_id] = {}
        self.active_timers[session_id]['phrase'] = timer
        
        print(f"[Timer] Phrase timer started for session {session_id} ({self.PHRASE_TIMEOUT}s)")
    
    def reset_timers(self, session_id: str):
        """Resetea todos los timers para una sesión"""
        self._cancel_timer(session_id, 'word')
        self._cancel_timer(session_id, 'phrase')
        print(f"[Timer] All timers reset for session {session_id}")
    
    def _cancel_timer(self, session_id: str, timer_type: str):
        """Cancela un timer específico"""
        if session_id in self.active_timers and timer_type in self.active_timers[session_id]:
            timer = self.active_timers[session_id][timer_type]
            timer.cancel()
            del self.active_timers[session_id][timer_type]
    
    def _auto_finish_word(self, session_id: str):
        """Auto-finaliza palabra (llamado por timer)"""
        try:
            if session_id not in self.autocorrector_service.sessions:
                return
                
            session = self.autocorrector_service.sessions[session_id]
            autocorrector = session["autocorrector"]
            
            if autocorrector.word_buffer and not session.get("word_finalized", False):
                word = autocorrector.finish_word()
                session["word_finalized"] = True
                print(f"[Timer] Auto-finished word: '{word}' for session {session_id}")
                
                # Iniciar timer de frase si hay palabras en la oración
                if autocorrector.sentence_words:
                    self.start_phrase_timer(session_id)
                    
        except Exception as e:
            print(f"[Timer] Error auto-finishing word for {session_id}: {e}")
    
    def _auto_finish_phrase(self, session_id: str):
        """Auto-finaliza frase (llamado por timer)"""
        try:
            if session_id not in self.autocorrector_service.sessions:
                return
                
            session = self.autocorrector_service.sessions[session_id]
            autocorrector = session["autocorrector"]
            
            if autocorrector.sentence_words:
                final_sentence = autocorrector.end_sentence()
                if final_sentence.strip():
                    print(f"[Timer] Auto-finished phrase: '{final_sentence}' for session {session_id}")
                    
                    # Obtener preferencias del usuario
                    user_prefs = session.get("user_preferences", {})
                    
                    # Auto-traducción si está configurada
                    translated_sentence = None
                    if user_prefs.get("auto_translate", False) and user_prefs.get("target_language"):
                        translated_sentence = translate_text(final_sentence, user_prefs["target_language"])
                        if translated_sentence:
                            print(f"[Timer] Auto-translated to {user_prefs['target_language']}: '{translated_sentence}'")
                    
                    # Auto-TTS si está configurado
                    if user_prefs.get("tts_enabled", True):
                        text_for_tts = translated_sentence if translated_sentence else final_sentence
                        lang_for_tts = user_prefs.get("target_language", "es") if translated_sentence else "es"
                        
                        # Usar TTS de manera asíncrona
                        success = bridge_tts.speak_text_async(text_for_tts, lang_for_tts)
                        if success:
                            print(f"[Timer] Auto-TTS started in {lang_for_tts}")
                    
                    # Marcar como completada
                    session["sentence_completed"] = True
                    session["completed_sentence"] = final_sentence
                    if translated_sentence:
                        session["translated_sentence"] = translated_sentence
                        
        except Exception as e:
            print(f"[Timer] Error auto-finishing phrase for {session_id}: {e}")
    
    def get_timer_status(self, session_id: str) -> Dict:
        """Obtiene el estado de los timers para una sesión"""
        if session_id not in self.active_timers:
            return {"word_timer": False, "phrase_timer": False}
            
        return {
            "word_timer": "word" in self.active_timers[session_id],
            "phrase_timer": "phrase" in self.active_timers[session_id],
            "timers_active": len(self.active_timers[session_id]) > 0
        }

# Instancia global del servicio
timer_manager_service = TimerManagerService()