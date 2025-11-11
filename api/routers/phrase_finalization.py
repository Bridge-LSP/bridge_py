from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import time
import logging
import base64
from api.services.timer_manager_service import timer_manager_service
from api.services.translation_service import translation_service
from api.services.enhanced_tts_service import enhanced_tts_service

router = APIRouter()
logger = logging.getLogger(__name__)

class PhraseRequest(BaseModel):
    session_id: str
    auto_translate: Optional[bool] = False
    target_language: Optional[str] = "en"
    tts_enabled: Optional[bool] = True
    voice_language: Optional[str] = "es"

class PhraseResponse(BaseModel):
    status: str = "success"
    phrase_finalized: str
    translated: Optional[str] = None
    tts_audio: Optional[str] = None
    processing_time_ms: int

@router.post("/finalize", response_model=PhraseResponse)
async def finalize_phrase(
    request: PhraseRequest,
    x_client_token: Optional[str] = Header(None)
):
    """
    Unified phrase finalization endpoint.
    Performs phrase completion, optional translation, and optional TTS generation in a single call.
    Reduces latency and complexity compared to multiple sequential calls.
    """
    start_time = time.time()
    phrase_start_time = start_time
    
    try:
        session_id = request.session_id
        
        # Verify session exists
        if session_id not in timer_manager_service.autocorrector_service.sessions:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # Step 1: Complete phrase
        try:
            # Force complete current word if building
            session = timer_manager_service.autocorrector_service.sessions[session_id]
            autocorrector = session["autocorrector"]
            
            # Finalize current word buffer if not empty
            if autocorrector.word_buffer.strip():
                timer_manager_service.autocorrector_service.finish_word(session_id)
            
            # Get completed phrase
            phrase_finalized = " ".join(autocorrector.sentence_words).strip()
            
            if not phrase_finalized:
                phrase_finalized = autocorrector.word_buffer.strip()
            
            if not phrase_finalized:
                raise HTTPException(status_code=400, detail="No content to finalize")
            
            phrase_time_ms = int((time.time() - phrase_start_time) * 1000)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'[Phrase] Finalized in {phrase_time_ms}ms | phrase="{phrase_finalized}"')
                
        except Exception as e:
            logger.error(f"[Phrase] Error finalizing phrase for {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to finalize phrase: {str(e)}")
        
        # Step 2: Optional translation
        translated = None
        if request.auto_translate and phrase_finalized:
            try:
                translation_start = time.time()
                translation_result = await translation_service.translate_text(
                    phrase_finalized,
                    target_language=request.target_language,
                    source_language="es"
                )
                
                if translation_result.get("status") == "success":
                    translated = translation_result["data"]["translated_text"]
                    
                    translation_time_ms = int((time.time() - translation_start) * 1000)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f'[Phrase] Translated in {translation_time_ms}ms | "{phrase_finalized}" -> "{translated}"')
                else:
                    logger.warning(f"[Phrase] Translation failed: {translation_result.get('detail', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"[Phrase] Translation error for {session_id}: {e}")
                # Continue without translation rather than failing the whole request
                translated = None
        
        # Step 3: Optional TTS generation
        tts_audio = None
        if request.tts_enabled:
            try:
                tts_start = time.time()
                
                # Use translated text if available, otherwise original phrase
                tts_text = translated if translated else phrase_finalized
                
                tts_result = await enhanced_tts_service.generate_speech(
                    text=tts_text,
                    language=request.voice_language,
                    session_id=session_id
                )
                
                if tts_result.get("status") == "success":
                    tts_audio = tts_result["data"].get("audio_base64")
                    
                    tts_time_ms = int((time.time() - tts_start) * 1000)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f'[Phrase] TTS generated in {tts_time_ms}ms | text="{tts_text}" | lang={request.voice_language}')
                else:
                    logger.warning(f"[Phrase] TTS failed: {tts_result.get('detail', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"[Phrase] TTS error for {session_id}: {e}")
                # Continue without TTS rather than failing the whole request
                tts_audio = None
        
        # Calculate total processing time
        total_time_ms = int((time.time() - start_time) * 1000)
        
        # Log completion
        if logger.isEnabledFor(logging.DEBUG):
            components = []
            if translated:
                components.append("translation")
            if tts_audio:
                components.append("tts")
            
            logger.debug(f'[Phrase] Complete finalization in {total_time_ms}ms | components: {components or ["phrase-only"]} | session: {session_id}')
        
        return PhraseResponse(
            status="success",
            phrase_finalized=phrase_finalized,
            translated=translated,
            tts_audio=tts_audio,
            processing_time_ms=total_time_ms
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Phrase] Unexpected error finalizing phrase for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/quick-complete")
async def quick_complete_phrase(
    request: PhraseRequest,
    x_client_token: Optional[str] = Header(None)
):
    """
    Quick phrase completion without translation or TTS.
    For faster UI updates when only text completion is needed.
    """
    try:
        session_id = request.session_id
        
        # Verify session exists
        if session_id not in timer_manager_service.autocorrector_service.sessions:
            return {
                "status": "error",
                "detail": f"Session {session_id} not found"
            }
        
        # Force complete current word if building
        session = timer_manager_service.autocorrector_service.sessions[session_id]
        autocorrector = session["autocorrector"]
        
        # Finalize current word buffer if not empty
        if autocorrector.word_buffer.strip():
            timer_manager_service.autocorrector_service.finish_word(session_id)
        
        # Get completed phrase
        phrase_finalized = " ".join(autocorrector.sentence_words).strip()
        
        if not phrase_finalized:
            phrase_finalized = autocorrector.word_buffer.strip()
        
        if not phrase_finalized:
            return {
                "status": "error",
                "detail": "No content to complete"
            }
        
        return {
            "status": "success",
            "data": {
                "phrase_finalized": phrase_finalized,
                "session_id": session_id
            }
        }
        
    except Exception as e:
        logger.error(f"[Phrase] Quick complete error for {session_id}: {e}")
        return {
            "status": "error",
            "detail": str(e)
        }