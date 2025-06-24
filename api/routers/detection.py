from fastapi import APIRouter, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from api.dependencies import get_hand_landmarker, get_forest_model
from api.services.hand_detection import process_image_detection

router = APIRouter()

@router.post(
    "/detect",
    summary="Detect hand landmarks",
    description=(
        "Receives an image in multipart/form-data format, detects the hands present, "
        "and returns the prediction (letter/number) and handedness (left/right)."
    ),
    response_description="A JSON with the prediction and hand classification.",
)
async def detect_hand(
    file: UploadFile = File(...),
    hand_landmarker=Depends(get_hand_landmarker),
    model=Depends(get_forest_model)
):
    contents = await file.read()
    response_data = await process_image_detection(contents, hand_landmarker, model)
    return JSONResponse(content=response_data)