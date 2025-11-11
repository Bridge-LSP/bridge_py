from fastapi import APIRouter, HTTPException
from api.models.schemas import TTSEnhancedRequest
from api.services.enhanced_tts_service import enhanced_tts_service

router = APIRouter()

@router.post(
    "/generate-audio",
    summary="Generate audio for complete phrases",
    description="Generates TTS audio for complete phrases with user preferences"
)
async def generate_audio(request: TTSEnhancedRequest):

    try:
        result = enhanced_tts_service.generate_audio_for_phrase(
            text=request.text,
            language=request.language,
            session_id=request.session_id,
            voice_speed=request.voice_speed or 1.0,
            voice_pitch=request.voice_pitch or 1.0
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/stop-audio",
    summary="Stop current audio playback",
    description="Stops the currently playing TTS audio"
)
async def stop_audio(payload: dict):

    try:
        session_id = payload.get("session_id")
        result = enhanced_tts_service.stop_audio(session_id)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/tts-status",
    summary="Get TTS status",
    description="Gets the current status of TTS engine and session"
)
async def get_tts_status(session_id: str = None):

    try:
        result = enhanced_tts_service.get_tts_status(session_id)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))