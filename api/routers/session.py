from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import time
import uuid
import logging
from datetime import datetime
from api.services.bert_autocorrector_service import AutoCorrectorService
from api.routers.realtime_detection import SESSIONS, PREFS, SessionState, UserPreferences

router = APIRouter()
logger = logging.getLogger(__name__)

class SessionInitRequest(BaseModel):
    session_id: Optional[str] = None
    preferences: Optional[dict] = None

class SessionInitResponse(BaseModel):
    status: str = "success"
    session_id: str
    modules_initialized: list[str]
    created_at: str

autocorrector_service = AutoCorrectorService()

@router.post("/init", response_model=SessionInitResponse)
async def init_session(
    request: SessionInitRequest,
    x_client_token: Optional[str] = Header(None)
):

    try:
        session_id = request.session_id or str(uuid.uuid4())

        modules_initialized = []

        try:
            if session_id not in autocorrector_service.sessions:
                autocorrector_service.create_session(session_id)
            modules_initialized.append("autocorrector")
        except Exception as e:
            logger.error(f"[Session] Error creating autocorrector session {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize autocorrector: {str(e)}")

        try:
            if session_id not in SESSIONS:
                SESSIONS[session_id] = SessionState()
                PREFS[session_id] = UserPreferences(session_id)

                if request.preferences:
                    prefs = PREFS[session_id]
                    if "tts_enabled" in request.preferences:
                        prefs.tts_enabled = bool(request.preferences["tts_enabled"])
                    if "voice_language" in request.preferences:
                        prefs.voice_language = str(request.preferences["voice_language"])
                    if "auto_translate" in request.preferences:
                        prefs.auto_translate = bool(request.preferences["auto_translate"])

                if x_client_token:
                    PREFS[session_id].client_token = x_client_token

            modules_initialized.append("realtime")
        except Exception as e:
            logger.error(f"[Session] Error creating realtime session {session_id}: {e}")
            if session_id in autocorrector_service.sessions:
                del autocorrector_service.sessions[session_id]
            raise HTTPException(status_code=500, detail=f"Failed to initialize realtime: {str(e)}")

        created_at = datetime.now().isoformat() + "Z"

        logger.info(f"[Session] Unified session created: {session_id} | modules: {modules_initialized}")

        return SessionInitResponse(
            status="success",
            session_id=session_id,
            modules_initialized=modules_initialized,
            created_at=created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Session] Unexpected error initializing session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{session_id}")
async def get_session_status(session_id: str):

    try:
        autocorrector_exists = session_id in autocorrector_service.sessions
        autocorrector_status = None
        if autocorrector_exists:
            autocorrector_status = autocorrector_service.get_session_status(session_id)

        realtime_exists = session_id in SESSIONS
        realtime_status = None
        if realtime_exists:
            session = SESSIONS[session_id]
            realtime_status = {
                "letters_buffer": session.letters_buffer,
                "current_word": session.current_word,
                "sentence_words": session.sentence_words,
                "sentence_so_far": session.sentence_so_far,
                "last_activity": session.last_activity,
                "is_building_word": session.is_building_word
            }

        preferences = None
        if session_id in PREFS:
            prefs = PREFS[session_id]
            preferences = {
                "tts_enabled": prefs.tts_enabled,
                "voice_language": prefs.voice_language,
                "auto_translate": prefs.auto_translate,
                "client_token": getattr(prefs, 'client_token', None)
            }

        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "modules": {
                    "autocorrector": {
                        "exists": autocorrector_exists,
                        "status": autocorrector_status
                    },
                    "realtime": {
                        "exists": realtime_exists,
                        "status": realtime_status
                    }
                },
                "preferences": preferences,
                "session_exists": autocorrector_exists and realtime_exists
            }
        }

    except Exception as e:
        logger.error(f"[Session] Error getting status for {session_id}: {e}")
        return {
            "status": "error",
            "detail": str(e)
        }

@router.delete("/destroy/{session_id}")
async def destroy_session(session_id: str):

    try:
        modules_destroyed = []

        if session_id in autocorrector_service.sessions:
            del autocorrector_service.sessions[session_id]
            modules_destroyed.append("autocorrector")

        if session_id in SESSIONS:
            del SESSIONS[session_id]
            modules_destroyed.append("realtime")

        if session_id in PREFS:
            del PREFS[session_id]
            modules_destroyed.append("preferences")

        from api.routers.continuous_detection import session_cache, detection_state
        if session_id in session_cache.cache:
            del session_cache.cache[session_id]
            modules_destroyed.append("cache")

        if session_id in detection_state["last_predictions"]:
            del detection_state["last_predictions"][session_id]
        if session_id in detection_state["last_times"]:
            del detection_state["last_times"][session_id]

        logger.info(f"[Session] Session destroyed: {session_id} | modules: {modules_destroyed}")

        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "modules_destroyed": modules_destroyed,
                "destroyed_at": datetime.now().isoformat() + "Z"
            }
        }

    except Exception as e:
        logger.error(f"[Session] Error destroying session {session_id}: {e}")
        return {
            "status": "error",
            "detail": str(e)
        }

@router.post("/create", deprecated=True)
async def create_session_legacy(
    request: SessionInitRequest,
    x_client_token: Optional[str] = Header(None)
):

    logger.warning("[Session] Using deprecated /session/create endpoint. Use /session/init instead.")
    return await init_session(request, x_client_token)