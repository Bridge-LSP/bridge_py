from typing import Dict, List
from api.services.bert_autocorrector_service import AutoCorrectorService

class BERTCorrectionService:
    def __init__(self):
        self.autocorrector_service = AutoCorrectorService()

    def correct_word(self, session_id: str, word: str, context: str = None) -> Dict:

        try:
            if session_id not in self.autocorrector_service.sessions:
                self.autocorrector_service.create_session(session_id)

            session = self.autocorrector_service.sessions[session_id]
            autocorrector = session["autocorrector"]

            if not context and autocorrector.sentence_words:
                context = " ".join(autocorrector.sentence_words)

            corrected_word = autocorrector._correct_word(word, context or "")

            suggestions = []
            confidence_score = 0.8

            if autocorrector.model_loaded and context:
                try:
                    masked_context = context.replace(word, "[MASK]")
                    predictions = autocorrector.nlp(masked_context, top_k=5)

                    suggestions = [pred["token_str"] for pred in predictions]

                    if corrected_word in suggestions:
                        confidence_score = 0.9
                    elif any(corrected_word.lower() in sugg.lower() for sugg in suggestions):
                        confidence_score = 0.7
                    else:
                        confidence_score = 0.6

                except Exception as e:
                    print(f"Error en sugerencias BERT: {e}")

            return {
                "original_word": word,
                "corrected_word": corrected_word,
                "confidence_score": confidence_score,
                "suggestions": suggestions[:3],
                "context_used": context or "",
                "session_id": session_id
            }

        except Exception as e:
            return {"error": str(e)}

bert_correction_service = BERTCorrectionService()