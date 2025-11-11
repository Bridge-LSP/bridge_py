from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
from api.models.schemas import PhraseCompletionRequest, PhraseCompletionResponse
from api.services.phrase_completion_service import phrase_completion_service

router = APIRouter()

@router.post(
    "/complete-phrase",
    response_model=PhraseCompletionResponse,
    summary="Complete current phrase",
    description="Completes the current phrase and optionally translates it based on user preferences"
)
async def complete_phrase(request: PhraseCompletionRequest):
    """Completa la frase actual con traducción opcional"""
    try:
        result = phrase_completion_service.complete_phrase(
            request.session_id, 
            request.force_completion
        )
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return PhraseCompletionResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/user-preferences",
    summary="Set user preferences for session",
    description="Configures user preferences for language, translation, and TTS"
)
async def set_user_preferences(payload: dict = Body(...)):
    """Configura preferencias del usuario para la sesión"""
    try:
        session_id = payload.get("session_id")
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id required")
        
        # Importar aquí para evitar dependencias circulares
        from api.services.bert_autocorrector_service import AutoCorrectorService
        autocorrector_service = AutoCorrectorService()
        
        if session_id not in autocorrector_service.sessions:
            autocorrector_service.create_session(session_id)
        
        # Actualizar preferencias
        session = autocorrector_service.sessions[session_id]
        session["user_preferences"] = {
            "text_language": payload.get("text_language", "es"),
            "voice_language": payload.get("voice_language", "es"),
            "auto_translate": payload.get("auto_translate", False),
            "target_language": payload.get("target_language"),
            "tts_enabled": payload.get("tts_enabled", True),
            "voice_speed": payload.get("voice_speed", 1.0),
            "voice_pitch": payload.get("voice_pitch", 1.0)
        }
        
        return JSONResponse(content={
            "session_id": session_id,
            "preferences_updated": True,
            "preferences": session["user_preferences"]
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))