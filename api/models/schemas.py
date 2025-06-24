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