import pyttsx3
import tempfile

def generar_audio(texto, idioma="es"):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    for voice in voices:
        lang_match = False
        # Verifica que voice.languages tenga al menos un elemento
        if hasattr(voice, "languages") and len(voice.languages) > 0:
            try:
                lang = voice.languages[0].decode().lower()
                if idioma in lang:
                    lang_match = True
            except Exception:
                pass
        # También verifica en el id de la voz
        if idioma in voice.id.lower():
            lang_match = True
        if lang_match:
            engine.setProperty('voice', voice.id)
            break
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    engine.save_to_file(texto, temp_file.name)
    engine.runAndWait()
    return temp_file.name