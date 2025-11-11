from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import time
import uuid
import logging
from datetime import datetime
from api.services.bert_autocorrector_service import BertAutocorrectorService
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

# Global instances
autocorrector_service = BertAutocorrectorService()

@router.post("/init", response_model=SessionInitResponse)
async def init_session(
    request: SessionInitRequest,
    x_client_token: Optional[str] = Header(None)
):
    """
    Unified session initialization combining autocorrector and realtime sessions.
    Replaces separate /autocorrector/session/create and /realtime/session/create calls.
    """
    try:
        # Generate or use provided session ID
        session_id = request.session_id or str(uuid.uuid4())
        
        # Initialize modules
        modules_initialized = []
        
        # 1. Create autocorrector session
        try:
            if session_id not in autocorrector_service.sessions:
                autocorrector_service.create_session(session_id)
            modules_initialized.append("autocorrector")
        except Exception as e:
            logger.error(f"[Session] Error creating autocorrector session {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize autocorrector: {str(e)}")
        
        # 2. Create realtime session
        try:
            if session_id not in SESSIONS:
                SESSIONS[session_id] = SessionState()
                PREFS[session_id] = UserPreferences(session_id)
                
                # Apply preferences if provided
                if request.preferences:
                    prefs = PREFS[session_id]
                    if "tts_enabled" in request.preferences:
                        prefs.tts_enabled = bool(request.preferences["tts_enabled"])
                    if "voice_language" in request.preferences:
                        prefs.voice_language = str(request.preferences["voice_language"])
                    if "auto_translate" in request.preferences:
                        prefs.auto_translate = bool(request.preferences["auto_translate"])
                
                # Store client token if provided
                if x_client_token:
                    PREFS[session_id].client_token = x_client_token
                
            modules_initialized.append("realtime")
        except Exception as e:
            logger.error(f"[Session] Error creating realtime session {session_id}: {e}")
            # Clean up autocorrector session if realtime fails
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
    """Get comprehensive session status across all modules"""
    try:
        # Check autocorrector session
        autocorrector_exists = session_id in autocorrector_service.sessions
        autocorrector_status = None
        if autocorrector_exists:
            autocorrector_status = autocorrector_service.get_session_status(session_id)
        
        # Check realtime session
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
        
        # Check preferences
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
    """Destroy session across all modules"""
    try:
        modules_destroyed = []
        
        # Clean up autocorrector session
        if session_id in autocorrector_service.sessions:
            del autocorrector_service.sessions[session_id]
            modules_destroyed.append("autocorrector")
        
        # Clean up realtime session
        if session_id in SESSIONS:
            del SESSIONS[session_id]
            modules_destroyed.append("realtime")
        
        # Clean up preferences
        if session_id in PREFS:
            del PREFS[session_id]
            modules_destroyed.append("preferences")
        
        # Clean up any cached state in continuous detection
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

# Backward compatibility endpoints (marked as deprecated)
@router.post("/create", deprecated=True)
async def create_session_legacy(
    request: SessionInitRequest,
    x_client_token: Optional[str] = Header(None)
):
    """
    Legacy session creation endpoint.
    DEPRECATED: Use /session/init instead.
    """
    logger.warning("[Session] Using deprecated /session/create endpoint. Use /session/init instead.")
    return await init_session(request, x_client_token)
