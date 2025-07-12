from engine_bridge.autocorrector.autocorrector_core import AutoCorrector
from typing import Dict, List, Optional
import time

class AutoCorrectorService:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
    
    def create_session(self, session_id: str) -> Dict:
        """Crea una nueva sesión de autocorrección."""
        self.sessions[session_id] = {
            "autocorrector": AutoCorrector(),
            "sentence": "",
            "last_letter_time": 0,
            "word_finalized": False,
            "last_corrected_word": "",
            "PAUSE_THRESHOLD": 3.0
        }
        return {"session_id": session_id, "status": "created"}
    
    def add_letter(self, session_id: str, letter: str) -> Dict:
        """Añade una letra al buffer de la sesión."""
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
        """Finaliza la palabra actual y la añade a la frase."""
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        session = self.sessions[session_id]
        current_time = time.time()
        
        # Verificar si debe finalizar automáticamente
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
        """Obtiene el estado actual de la sesión."""
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        session = self.sessions[session_id]
        current_time = time.time()
        
        # Verificar si la palabra debe finalizarse automáticamente
        should_auto_finish = (session["autocorrector"].word_buffer and 
                             current_time - session["last_letter_time"] > session["PAUSE_THRESHOLD"] and 
                             not session["word_finalized"])
        
        # ✅ ARREGLO: Usar el método correcto para obtener la frase
        try:
            sentence_string = session["autocorrector"].get_sentence_string()
        except AttributeError:
            # Fallback si el método no existe
            sentence_string = " ".join(session["autocorrector"].sentence_words) if hasattr(session["autocorrector"], 'sentence_words') else ""
        
        try:
            sentence_words = session["autocorrector"].get_sentence_words()
        except AttributeError:
            # Fallback si el método no existe
            sentence_words = [(i, word) for i, word in enumerate(session["autocorrector"].sentence_words)] if hasattr(session["autocorrector"], 'sentence_words') else []
        
        return {
            "current_buffer": ''.join(session["autocorrector"].word_buffer),
            "predicted_word": session["autocorrector"].get_current_word_corrected(),
            "sentence": sentence_string,
            "sentence_words": sentence_words,
            "should_auto_finish": should_auto_finish,
            "last_corrected_word": session["last_corrected_word"],
            "learning_stats": session["autocorrector"].get_learning_stats()
        }
    
    def provide_feedback(self, session_id: str, correct_word: str) -> Dict:
        """Proporciona retroalimentación para mejorar el autocorrector."""
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        session = self.sessions[session_id]
        success = session["autocorrector"].provide_feedback(correct_word)
        
        return {
            "feedback_applied": success,
            "learned_correction": f"{session['autocorrector'].last_raw_word} -> {correct_word}" if success else None
        }
    
    def provide_feedback_for_word(self, session_id: str, word_position: int, correct_word: str) -> Dict:
        """✅ NUEVO: Proporciona feedback para una palabra específica de la frase."""
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
        """✅ NUEVO: Elimina una palabra de la frase."""
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        session = self.sessions[session_id]
        success = session["autocorrector"].remove_word(word_position)
        
        return {
            "word_removed": success,
            "word_position": word_position
        }
    
    def end_sentence(self, session_id: str) -> Dict:
        """✅ NUEVO: Finaliza la frase actual."""
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        session = self.sessions[session_id]
        final_sentence = session["autocorrector"].end_sentence()
        
        return {
            "final_sentence": final_sentence,
            "sentence_ended": True
        }
    
    def reset_session(self, session_id: str) -> Dict:
        """Reinicia la sesión."""
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        session = self.sessions[session_id]
        session["autocorrector"].clear_buffer()
        session["sentence"] = ""
        session["word_finalized"] = False
        session["last_corrected_word"] = ""
        
        return {"message": "Session reset"}
    
    def delete_session(self, session_id: str) -> Dict:
        """Elimina la sesión."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return {"message": "Session deleted"}
        return {"error": "Session not found"}
    
    def get_correction_health_report(self, session_id: str) -> Dict:
        """✅ NUEVO: Obtener reporte de salud del autocorrector."""
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        session = self.sessions[session_id]
        health_report = session["autocorrector"].get_correction_health_report()
        
        return {
            "session_id": session_id,
            "health_report": health_report
        }
    
    def clean_ineffective_corrections(self, session_id: str) -> Dict:
        """✅ NUEVO: Limpiar correcciones ineficaces."""
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        session = self.sessions[session_id]
        cleanup_result = session["autocorrector"].clean_ineffective_corrections()
        
        return {
            "session_id": session_id,
            "cleanup_result": cleanup_result
        }
    
    def get_bert_training_suggestions(self, session_id: str) -> Dict:
        """✅ NUEVO: Obtener sugerencias de entrenamiento con análisis gramatical."""
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        session = self.sessions[session_id]
        suggestions = session["autocorrector"].get_bert_training_suggestions()
        
        return {
            "session_id": session_id,
            "bert_suggestions": suggestions
        }