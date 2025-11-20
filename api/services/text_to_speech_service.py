from fastapi.responses import FileResponse
from engine_bridge.text_to_speech import bridge_tts
import tempfile
import os

def generate_speech_file(texto: str, idioma: str = "es") -> FileResponse:

    try:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_path = temp_file.name
        temp_file.close()

        bridge_tts._set_voice_for_language(idioma)

        bridge_tts.engine.save_to_file(texto, temp_path)
        bridge_tts.engine.runAndWait()

        if os.path.exists(temp_path):
            return FileResponse(
                temp_path,
                media_type="audio/wav",
                filename=f"speech_{idioma}_{hash(texto)}.wav"
            )
        else:
            raise Exception("No se pudo generar el archivo de audio")

    except Exception as e:
        print(f"Error generating audio: {e}")
        return FileResponse(
            "static/error.wav" if os.path.exists("static/error.wav") else temp_path,
            media_type="audio/wav",
            filename="error.wav"
        )