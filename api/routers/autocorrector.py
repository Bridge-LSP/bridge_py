from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from api.models.schemas import (
    SessionCreateRequest, AddLetterRequest, FinishWordRequest, 
    FeedbackRequest, SessionStatusRequest, SessionResponse,
    LetterAddedResponse, WordCompletedResponse, SessionStatusResponse,
    FeedbackResponse
)
from api.services.bert_autocorrector_service import AutoCorrectorService

router = APIRouter()

# Instancia global del servicio
autocorrector_service = AutoCorrectorService()

@router.post(
    "/session/create",
    response_model=SessionResponse,
    summary="Create autocorrector session",
    description="Creates a new autocorrector session for a user",
)
async def create_session(request: SessionCreateRequest):
    try:
        result = autocorrector_service.create_session(request.session_id)
        return SessionResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/letter/add",
    response_model=LetterAddedResponse,
    summary="Add letter to session",
    description="Adds a detected letter to the session buffer",
)
async def add_letter(request: AddLetterRequest):
    try:
        result = autocorrector_service.add_letter(request.session_id, request.letter)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return LetterAddedResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/word/finish",
    response_model=WordCompletedResponse,
    summary="Finish current word",
    description="Finishes the current word and adds it to the sentence",
)
async def finish_word(request: FinishWordRequest):
    try:
        result = autocorrector_service.finish_word(request.session_id, request.force)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return WordCompletedResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/session/status",
    response_model=SessionStatusResponse,
    summary="Get session status",
    description="Gets the current status of the autocorrector session",
)
async def get_session_status(request: SessionStatusRequest):
    try:
        result = autocorrector_service.get_session_status(request.session_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return SessionStatusResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Provide feedback",
    description="Provides feedback to improve autocorrection",
)
async def provide_feedback(request: FeedbackRequest):
    try:
        result = autocorrector_service.provide_feedback(request.session_id, request.correct_word)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return FeedbackResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/session/reset",
    summary="Reset session",
    description="Resets the autocorrector session",
)
async def reset_session(request: SessionStatusRequest):
    try:
        result = autocorrector_service.reset_session(request.session_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete(
    "/session/{session_id}",
    summary="Delete session",
    description="Deletes the autocorrector session",
)
async def delete_session(session_id: str):
    try:
        result = autocorrector_service.delete_session(session_id)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))