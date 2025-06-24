import pyttsx3
import tempfile

def generar_audio(texto: str, idioma: str = "es") -> str:
    engine = pyttsx3.init()
    voces = engine.getProperty('voices')
    for voice in voces:
        langs = [l.decode('utf-8') if isinstance(l, bytes) else l for l in voice.languages]
        if any(idioma in l for l in langs):
            engine.setProperty('voice', voice.id)
            break
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
        filename = f.name
    engine.save_to_file(texto, filename)
    engine.runAndWait()
    return filename