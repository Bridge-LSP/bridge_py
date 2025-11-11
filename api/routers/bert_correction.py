from fastapi import APIRouter, HTTPException
from api.models.schemas import BERTCorrectionRequest, BERTCorrectionResponse
from api.services.bert_correction_service import bert_correction_service

router = APIRouter()

@router.post(
    "/correct-bert",
    response_model=BERTCorrectionResponse,
    summary="Correct word using BERT",
    description="Corrects a word using BERT model with contextual understanding"
)
async def correct_word_bert(request: BERTCorrectionRequest):

    try:
        result = bert_correction_service.correct_word(
            request.session_id,
            request.word,
            request.context
        )

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return BERTCorrectionResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))