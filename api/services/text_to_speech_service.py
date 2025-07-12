from fastapi.responses import FileResponse
from engine_bridge.text_to_speech import generar_audio

def generate_speech_file(texto: str, idioma: str) -> FileResponse:
    archivo = generar_audio(texto, idioma)
    return FileResponse(
        archivo, 
        media_type="audio/mpeg", 
        filename=f"speech_{idioma}_{texto}.mp3"
    )