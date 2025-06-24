from fastapi import APIRouter
from api.services.text_to_speech_service import generate_speech_file

router = APIRouter()

@router.get(
    "/tts",
    summary="Text to Speech",
    description="Converts text to speech and returns an audio file.",
    response_description="An MP3 audio file."
)
def text_to_speech(texto: str, idioma: str = "es"):
    return generate_speech_file(texto, idioma)