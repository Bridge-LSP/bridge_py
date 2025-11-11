from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional
from api.services.timer_manager_service import timer_manager_service

router = APIRouter()

class TimerControlRequest(BaseModel):
    session_id: str
    action: str  # "start_word", "start_phrase", "reset", "status"

class WordFinishRequest(BaseModel):
    session_id: str
    force: Optional[bool] = False

class PhraseFinishRequest(BaseModel):
    session_id: str
    force: Optional[bool] = False
    enable_translation: Optional[bool] = True
    enable_tts: Optional[bool] = True

@router.post(
    "/word/auto-finish",
    summary="Auto-finish word after timeout",
    description="Automatically finishes current word after 2s timeout (replicates main.py behavior)"
)
async def auto_finish_word(request: WordFinishRequest):
    """Auto-finaliza palabra después de timeout (idéntico a main.py)"""
    try:
        if request.force:
            # Finalizar inmediatamente
            result = timer_manager_service.autocorrector_service.finish_word(request.session_id, True)
            if "error" in result:
                raise HTTPException(status_code=404, detail=result["error"])
            return {
                "word_completed": result.get("word_completed"),
                "sentence": result.get("sentence", ""),
                "auto_finished": False,
                "forced": True
            }
        else:
            # Iniciar timer de auto-finalización
            timer_manager_service.start_word_timer(request.session_id)
            return {
                "timer_started": True,
                "timeout_seconds": timer_manager_service.PAUSE_THRESHOLD,
                "message": f"Word will auto-finish in {timer_manager_service.PAUSE_THRESHOLD}s"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/phrase/auto-finish",
    summary="Auto-finish phrase after timeout",
    description="Automatically finishes current phrase after 5s timeout (replicates main.py behavior)"
)
async def auto_finish_phrase(request: PhraseFinishRequest):
    """Auto-finaliza frase después de timeout (idéntico a main.py)"""
    try:
        if request.force:
            # Finalizar inmediatamente con TTS y traducción
            if request.session_id not in timer_manager_service.autocorrector_service.sessions:
                raise HTTPException(status_code=404, detail="Session not found")
                
            session = timer_manager_service.autocorrector_service.sessions[request.session_id]
            autocorrector = session["autocorrector"]
            
            if not autocorrector.sentence_words:
                raise HTTPException(status_code=400, detail="No words to complete phrase")
            
            final_sentence = autocorrector.end_sentence()
            
            # Obtener preferencias
            user_prefs = session.get("user_preferences", {})
            translated_sentence = None
            
            # Auto-traducción si está habilitada
            if request.enable_translation and user_prefs.get("auto_translate", False):
                target_lang = user_prefs.get("target_language")
                if target_lang:
                    from api.services.translation_service import translate_text
                    translated_sentence = translate_text(final_sentence, target_lang)
            
            # Auto-TTS si está habilitado
            tts_started = False
            if request.enable_tts and user_prefs.get("tts_enabled", True):
                from engine_bridge.text_to_speech import bridge_tts
                text_for_tts = translated_sentence if translated_sentence else final_sentence
                lang_for_tts = user_prefs.get("target_language", "es") if translated_sentence else "es"
                tts_started = bridge_tts.speak_text_async(text_for_tts, lang_for_tts)
            
            return {
                "phrase_completed": final_sentence,
                "translated_phrase": translated_sentence,
                "tts_started": tts_started,
                "auto_finished": False,
                "forced": True
            }
        else:
            # Iniciar timer de auto-finalización
            timer_manager_service.start_phrase_timer(request.session_id)
            return {
                "timer_started": True,
                "timeout_seconds": timer_manager_service.PHRASE_TIMEOUT,
                "message": f"Phrase will auto-finish in {timer_manager_service.PHRASE_TIMEOUT}s"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/timers/control",
    summary="Control word and phrase timers",
    description="Start, reset, or check status of automatic timers"
)
async def control_timers(request: TimerControlRequest):
    """Controla los timers automáticos"""
    try:
        if request.action == "start_word":
            timer_manager_service.start_word_timer(request.session_id)
            return {
                "action": "start_word",
                "timer_started": True,
                "timeout_seconds": timer_manager_service.PAUSE_THRESHOLD
            }
        
        elif request.action == "start_phrase":
            timer_manager_service.start_phrase_timer(request.session_id)
            return {
                "action": "start_phrase", 
                "timer_started": True,
                "timeout_seconds": timer_manager_service.PHRASE_TIMEOUT
            }
            
        elif request.action == "reset":
            timer_manager_service.reset_timers(request.session_id)
            return {
                "action": "reset",
                "timers_reset": True,
                "message": "All timers reset"
            }
            
        elif request.action == "status":
            status = timer_manager_service.get_timer_status(request.session_id)
            return {
                "action": "status",
                "timer_status": status
            }
            
        else:
            raise HTTPException(status_code=400, detail="Invalid action. Use: start_word, start_phrase, reset, status")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/timers/status/{session_id}",
    summary="Get timer status for session", 
    description="Returns current status of word and phrase timers"
)
async def get_timer_status(session_id: str):
    """Obtiene el estado de los timers"""
    try:
        status = timer_manager_service.get_timer_status(session_id)
        return {
            "session_id": session_id,
            "timer_status": status,
            "pause_threshold": timer_manager_service.PAUSE_THRESHOLD,
            "phrase_timeout": timer_manager_service.PHRASE_TIMEOUT
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/detection/add-letter-with-timer",
    summary="Add letter and manage timers automatically",
    description="Adds letter and automatically manages word/phrase timers (main.py behavior)"
)
async def add_letter_with_timer(payload: dict = Body(...)):
    """Agrega letra y maneja timers automáticamente (comportamiento de main.py)"""
    try:
        session_id = payload.get("session_id")
        letter = payload.get("letter")
        
        if not session_id or not letter:
            raise HTTPException(status_code=400, detail="session_id and letter required")
        
        # Agregar letra al autocorrector
        result = timer_manager_service.autocorrector_service.add_letter(session_id, letter)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        # Resetear timers existentes
        timer_manager_service.reset_timers(session_id)
        
        # Iniciar timer de palabra
        timer_manager_service.start_word_timer(session_id)
        
        return {
            "letter_added": result["letter_added"],
            "current_buffer": result["current_buffer"],
            "predicted_word": result["predicted_word"],
            "word_timer_started": True,
            "timer_timeout": timer_manager_service.PAUSE_THRESHOLD
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))