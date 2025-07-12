from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
from api.models.schemas import (
    SessionCreateRequest, AddLetterRequest, FinishWordRequest,
    SessionStatusRequest, SessionResponse,
    LetterAddedResponse, WordCompletedResponse, SessionStatusResponse
)
from api.services.bert_autocorrector_service import AutoCorrectorService

router = APIRouter()
autocorrector_service = AutoCorrectorService()


def validate_required_fields(data: dict, required: list):
    for field in required:
        if data.get(field) is None:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")


@router.post(
    "/session/create",
    response_model=SessionResponse,
    summary="Create autocorrector session",
    description="Creates a new autocorrector session for a user",
)
async def create_session(request: SessionCreateRequest):
    try:
        return SessionResponse(**autocorrector_service.create_session(request.session_id))
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/sentence/end",
    summary="End current sentence",
    description="Finalizes the current sentence and resets for a new one",
)
async def end_sentence(payload: dict = Body(...)):
    try:
        validate_required_fields(payload, ["session_id"])
        result = autocorrector_service.end_sentence(payload["session_id"])
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return JSONResponse(content=result)
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 7. ELIMINAR PALABRA (Funcionalidad avanzada)
@router.delete(
    "/word/remove",
    summary="Remove word from sentence",
    description="Removes a specific word from the current sentence",
)
async def remove_word(payload: dict = Body(...)):
    try:
        validate_required_fields(payload, ["session_id", "word_position"])
        result = autocorrector_service.remove_word(payload["session_id"], payload["word_position"])
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/word/feedback",
    summary="Provide feedback for specific word",
    description="Provides feedback for a specific word in the sentence",
)
async def feedback_word(payload: dict = Body(...)):
    try:
        validate_required_fields(payload, ["session_id", "word_position", "correct_word"])
        result = autocorrector_service.provide_feedback_for_word(
            payload["session_id"], payload["word_position"], payload["correct_word"]
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))