from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
from api.services.bert_autocorrector_service import AutoCorrectorService
from api.models.schemas import (
    AddLetterRequest, FinishWordRequest, SessionStatusRequest,
    WordBuilderResponse, LetterAddedResponse
)

router = APIRouter()
autocorrector_service = AutoCorrectorService()

@router.post(
    "/detect-sequence",
    summary="Process sequence of gestures for word building",
    description="Processes a sequence of detected letters to build words in real-time"
)
async def detect_sequence(payload: dict = Body(...)):
    """Procesa secuencia de gestos para construir palabras"""
    try:
        session_id = payload.get("session_id")
        letters_sequence = payload.get("letters", [])
        
        if not session_id or not letters_sequence:
            raise HTTPException(status_code=400, detail="session_id and letters required")
        
        # Crear sesión si no existe
        if session_id not in autocorrector_service.sessions:
            autocorrector_service.create_session(session_id)
        
        results = []
        for letter in letters_sequence:
            result = autocorrector_service.add_letter(session_id, letter)
            results.append(result)
        
        # Obtener estado actual
        status = autocorrector_service.get_session_status(session_id)
        
        return JSONResponse(content={
            "session_id": session_id,
            "letters_processed": len(letters_sequence),
            "current_word": status["current_buffer"],
            "predicted_word": status["predicted_word"],
            "sentence": status["sentence"],
            "should_auto_finish": status["should_auto_finish"],
            "results": results
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/build-word",
    response_model=WordBuilderResponse,
    summary="Build word from current buffer",
    description="Constructs word from current letter buffer with BERT correction"
)
async def build_word(request: FinishWordRequest):
    """Construye palabra desde buffer actual con corrección BERT"""
    try:
        result = autocorrector_service.finish_word(request.session_id, request.force)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return WordBuilderResponse(
            word_completed=result.get("word_completed"),
            corrected_word=result.get("corrected_word"),
            sentence=result.get("sentence", ""),
            confidence_score=result.get("confidence_score", 0.0),
            auto_finished=result.get("auto_finished", False)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))