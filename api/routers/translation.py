from fastapi import APIRouter, HTTPException
from api.services.translation_service import translate_text, LANG_MAP
from api.models.schemas import TranslationRequest, TranslationResponse

router = APIRouter()

@router.post(
    "/translate",
    response_model=TranslationResponse,
    summary="Translate Text",
    description="Translates text to the specified target language using DeepL API.",
    response_description="The translated text."
)
def translate_endpoint(request: TranslationRequest):
    if request.language.lower() not in LANG_MAP:
        raise HTTPException(
            status_code=400, 
            detail=f"Idioma no soportado. Use uno de: {', '.join(LANG_MAP.keys())}"
        )
    
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="El texto no puede estar vacío")
    
    translated_text = translate_text(request.text, request.language.lower())
    
    if translated_text is None:
        raise HTTPException(status_code=500, detail="Error al traducir el texto")
    
    return TranslationResponse(translation=translated_text)