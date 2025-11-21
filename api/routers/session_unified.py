"""
Unified session management endpoints using SessionEngine.

This module provides REST endpoints for session initialization, preferences,
and manual phrase management, all delegating to SessionEngine instances.
"""

import time
import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from engine_bridge.session_manager import get_session_manager
from api.config import WS_BASE_URL

router = APIRouter()
logger = logging.getLogger(__name__)


class SessionInitRequest(BaseModel):
    session_id: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


class SessionInitResponse(BaseModel):
    status: str = "success"
    session_id: str
    preferences: Dict[str, Any]
    created_at: str
    websocket_url: str


class PreferencesUpdateRequest(BaseModel):
    session_id: str
    preferences: Dict[str, Any]


class PhraseRequest(BaseModel):
    session_id: str


@router.post("/init", response_model=SessionInitResponse)
async def init_session(
    request: SessionInitRequest,
    x_client_token: Optional[str] = Header(None)
):
    """
    Initialize a new session or get existing one with SessionEngine.
    
    Creates a SessionEngine instance with specified preferences and returns
    the session configuration.
    """
    try:
        # Check if BERT models are still loading
        from engine_bridge.bert_model_loader import is_loading
        if is_loading():
            raise HTTPException(
                status_code=503,
                detail="BERT model is still loading. Please retry in a few seconds or check /bert/status"
            )
        
        session_manager = get_session_manager()
        
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Default preferences
        default_preferences = {
            "tts_enabled": True,
            "tts_muted": False,
            "text_language": "es",
            "target_language": "en",
            "auto_translate": False,
            "word_pause_ms": 4000,
            "phrase_pause_ms": 8000
        }
        
        # Merge with provided preferences
        if request.preferences:
            default_preferences.update(request.preferences)
        
        # Add client token if provided
        if x_client_token:
            default_preferences["client_token"] = x_client_token
        
        # Get or create session engine
        session_engine = session_manager.get_or_create_session(
            session_id=session_id,
            preferences=default_preferences
        )
        
        created_at = datetime.now().isoformat() + "Z"
        
        logger.info(f"Session initialized: {session_id}")
        
        # Return current preferences from the engine
        current_preferences = {
            "tts_enabled": session_engine.tts_enabled,
            "tts_muted": session_engine.tts_muted,
            "text_language": session_engine.text_language,
            "target_language": session_engine.target_language,
            "auto_translate": session_engine.auto_translate,
            "word_pause_ms": session_engine.word_pause_ms,
            "phrase_pause_ms": session_engine.phrase_pause_ms
        }
        
        # Build WebSocket URL
        websocket_url = f"{WS_BASE_URL}/realtime/ws/detection/{session_id}"
        
        return SessionInitResponse(
            status="success",
            session_id=session_id,
            preferences=current_preferences,
            created_at=created_at,
            websocket_url=websocket_url
        )
        
    except Exception as e:
        logger.error(f"Error initializing session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/preferences")
async def update_session_preferences(
    request: PreferencesUpdateRequest,
    x_client_token: Optional[str] = Header(None)
):
    """
    Update preferences for an existing session.
    
    Merges new preferences with existing ones in the SessionEngine.
    """
    try:
        session_manager = get_session_manager()
        session_engine = session_manager.get_session(request.session_id)
        
        if not session_engine:
            raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found")
        
        # Update preferences
        session_engine.update_preferences(request.preferences)
        
        logger.info(f"Preferences updated for session {request.session_id}")
        
        # Return updated preferences
        current_preferences = {
            "tts_enabled": session_engine.tts_enabled,
            "tts_muted": session_engine.tts_muted,
            "text_language": session_engine.text_language,
            "target_language": session_engine.target_language,
            "auto_translate": session_engine.auto_translate,
            "word_pause_ms": session_engine.word_pause_ms,
            "phrase_pause_ms": session_engine.phrase_pause_ms
        }
        
        return {
            "status": "success",
            "session_id": request.session_id,
            "preferences": current_preferences,
            "updated_at": datetime.now().isoformat() + "Z"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{session_id}")
async def get_session_status(session_id: str):
    """
    Get current status and state of a session.
    
    Returns the current state payload from SessionEngine without processing frames.
    """
    try:
        session_manager = get_session_manager()
        session_engine = session_manager.get_session(session_id)
        
        if not session_engine:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # Get current state from engine
        state_data = session_engine._build_state_payload()
        
        # Add session metadata
        state_data["session_exists"] = True
        state_data["is_running"] = session_engine.is_running
        
        return {
            "status": "success",
            "data": state_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        return {
            "status": "error",
            "detail": str(e)
        }


@router.delete("/destroy/{session_id}")
async def destroy_session(session_id: str):
    """
    Destroy a session and clean up resources.
    
    Removes the SessionEngine instance and cleans up any associated state.
    """
    try:
        session_manager = get_session_manager()
        removed = session_manager.remove_session(session_id)
        
        if not removed:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        logger.info(f"Session destroyed: {session_id}")
        
        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "destroyed_at": datetime.now().isoformat() + "Z"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error destroying session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/finalize")
async def finalize_phrase(
    request: PhraseRequest,
    x_client_token: Optional[str] = Header(None)
):
    """
    Manually finalize the current phrase in a session.
    
    Triggers sentence completion, translation, and TTS through SessionEngine.
    """
    try:
        session_manager = get_session_manager()
        session_engine = session_manager.get_session(request.session_id)
        
        if not session_engine:
            raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found")
        
        start_time = time.time()
        
        # Manually finalize phrase
        state_data = session_engine.manual_finalize_phrase()
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        state_data["processing_time_ms"] = processing_time_ms
        
        logger.info(f"Phrase finalized manually for session {request.session_id}")
        
        return {
            "status": "success",
            "data": state_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finalizing phrase: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_session(
    request: PhraseRequest,
    x_client_token: Optional[str] = Header(None)
):
    """
    Reset/clear all state in a session.
    
    Clears word buffer, sentence, translation, and TTS state through SessionEngine.
    """
    try:
        session_manager = get_session_manager()
        session_engine = session_manager.get_session(request.session_id)
        
        if not session_engine:
            raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found")
        
        # Clear all state
        session_engine.clear_all()
        
        # Get clean state
        state_data = session_engine._build_state_payload()
        
        logger.info(f"Session reset: {request.session_id}")
        
        return {
            "status": "success",
            "data": state_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_sessions():
    """
    List all active sessions with their status.
    
    Returns information about all SessionEngine instances.
    """
    try:
        session_manager = get_session_manager()
        session_info = session_manager.get_session_info()
        
        return {
            "status": "success",
            "data": {
                "session_count": len(session_info),
                "sessions": session_info
            }
        }
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return {
            "status": "error",
            "detail": str(e)
        }


@router.post("/cleanup")
async def cleanup_inactive_sessions():
    """
    Manually trigger cleanup of inactive sessions.
    
    Removes sessions that have exceeded their TTL.
    """
    try:
        session_manager = get_session_manager()
        cleaned_count = session_manager.cleanup_inactive_sessions()
        
        return {
            "status": "success",
            "data": {
                "cleaned_sessions": cleaned_count,
                "remaining_sessions": session_manager.get_session_count(),
                "cleaned_at": datetime.now().isoformat() + "Z"
            }
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return {
            "status": "error",
            "detail": str(e)
        }