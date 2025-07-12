from fastapi import APIRouter, HTTPException
from api.services.translation_service import translate_text
from api.models.schemas import (TranslationRequest, TranslationResponse)

router = APIRouter()

@router.post(
    "/translate",
    response_model=TranslationResponse,
    summary="Translate Text",
    description="Translates Spanish text to the specified target language (en, pt).",
    response_description="The translated text."
)
def translate_endpoint(request: TranslationRequest):
    """
    Traduce texto del español al idioma especificado.
    """
    # Validar idioma soportado
    if request.language.lower() not in ["en", "pt"]:
        raise HTTPException(status_code=400, detail="Idioma no soportado. Use 'en' o 'pt'")
    
    # Realizar traducción
    translated_text = translate_text(request.text, request.language.lower())
    
    if translated_text is None:
        raise HTTPException(status_code=500, detail="Error al traducir el texto")
    
    return TranslationResponse(translation=translated_text)