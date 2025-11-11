from pydantic import BaseModel
from typing import List, Optional

class HandDetectionResponse(BaseModel):
    prediction: str
    handedness: str
    confidence: float

class TTSRequest(BaseModel):
    texto: str
    idioma: str = "es"

class HealthResponse(BaseModel):
    status: str
    version: str

class SessionCreateRequest(BaseModel):
    session_id: str

class AddLetterRequest(BaseModel):
    session_id: str
    letter: str

class FinishWordRequest(BaseModel):
    session_id: str
    force: Optional[bool] = False

class FeedbackRequest(BaseModel):
    session_id: str
    correct_word: str

class SessionStatusRequest(BaseModel):
    session_id: str

class SessionResponse(BaseModel):
    session_id: str
    status: str

class LetterAddedResponse(BaseModel):
    letter_added: str
    current_buffer: str
    predicted_word: str

class WordCompletedResponse(BaseModel):
    word_completed: Optional[str] = None
    sentence: str
    auto_finished: bool
    message: Optional[str] = None

class SessionStatusResponse(BaseModel):
    current_buffer: str
    predicted_word: str
    sentence: str
    should_auto_finish: bool
    last_corrected_word: str
    learning_stats: dict

class FeedbackResponse(BaseModel):
    feedback_applied: bool
    learned_correction: Optional[str] = None

class TranslationRequest(BaseModel):
    language: str
    text: str

class TranslationResponse(BaseModel):
    translation: str

class WordBuilderResponse(BaseModel):
    word_completed: Optional[str] = None
    corrected_word: Optional[str] = None
    sentence: str
    confidence_score: float
    auto_finished: bool

class PhraseCompletionRequest(BaseModel):
    session_id: str
    force_completion: Optional[bool] = False

class PhraseCompletionResponse(BaseModel):
    completed_phrase: str
    translated_phrase: Optional[str] = None
    target_language: Optional[str] = None
    word_count: int
    corrections_made: int
    confidence_score: float

class BERTCorrectionRequest(BaseModel):
    session_id: str
    word: str
    context: Optional[str] = None

class BERTCorrectionResponse(BaseModel):
    original_word: str
    corrected_word: str
    confidence_score: float
    suggestions: List[str]

class UserPreferencesRequest(BaseModel):
    session_id: str
    text_language: str = "es"
    voice_language: str = "es"
    auto_translate: bool = False
    target_language: Optional[str] = None
    tts_enabled: bool = True

class TTSEnhancedRequest(BaseModel):
    text: str
    language: str = "es"
    voice_speed: Optional[float] = 1.0
    voice_pitch: Optional[float] = 1.0
    session_id: Optional[str] = None