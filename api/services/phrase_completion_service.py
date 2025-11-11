from typing import Dict, Optional
from api.services.bert_autocorrector_service import AutoCorrectorService
from api.services.translation_service import translate_text

class PhraseCompletionService:
    def __init__(self):
        self.autocorrector_service = AutoCorrectorService()
    
    def complete_phrase(self, session_id: str, force_completion: bool = False) -> Dict:
        """Completa la frase actual y opcionalmente la traduce"""
        try:
            if session_id not in self.autocorrector_service.sessions:
                return {"error": "Session not found"}
            
            session = self.autocorrector_service.sessions[session_id]
            autocorrector = session["autocorrector"]
            
            # Finalizar palabra actual si existe
            if autocorrector.word_buffer and not force_completion:
                autocorrector.finish_word()
            
            # Completar frase
            completed_phrase = autocorrector.end_sentence()
            
            if not completed_phrase.strip():
                return {"error": "No phrase to complete"}
            
            # Obtener estadísticas
            word_count = len(completed_phrase.split())
            stats = autocorrector.get_learning_stats()
            
            # Obtener preferencias del usuario
            user_prefs = session.get("user_preferences", {})
            translated_phrase = None
            target_language = None
            
            # Traducir si está configurado
            if user_prefs.get("auto_translate", False) and user_prefs.get("target_language"):
                target_language = user_prefs["target_language"]
                translated_phrase = translate_text(completed_phrase, target_language)
            
            return {
                "completed_phrase": completed_phrase,
                "translated_phrase": translated_phrase,
                "target_language": target_language,
                "word_count": word_count,
                "corrections_made": stats.get("total_corrections", 0),
                "confidence_score": self._calculate_phrase_confidence(autocorrector),
                "session_id": session_id
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _calculate_phrase_confidence(self, autocorrector) -> float:
        """Calcula la confianza de la frase basada en correcciones"""
        try:
            if hasattr(autocorrector, 'analytics'):
                last_record = autocorrector.storage.successful_sentences
                if last_record:
                    return last_record[-1].get("semantic_coherence", 0.5)
            return 0.7  # Confianza por defecto
        except:
            return 0.7

# Instancia global del servicio
phrase_completion_service = PhraseCompletionService()