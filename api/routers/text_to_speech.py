from fastapi import APIRouter
from pydantic import BaseModel
from api.services.text_to_speech_service import generate_speech_file

class TextToSpeechRequest(BaseModel):
    language: str
    text: str

router = APIRouter()

@router.post(
    "/text_to_speech",
    summary="Text to Speech",
    description="Converts text to speech and returns an audio file.",
    response_description="An MP3 audio file."
)
def text_to_speech(request: TextToSpeechRequest):
    return generate_speech_file(request.text, request.language)