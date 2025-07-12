import deepl

# Tu clave de API de DeepL
API_KEY = '2e27de5f-2269-47fb-af2d-e373efdc6dcf:fx'

# Crear el objeto traductor de DeepL
translator = deepl.Translator(API_KEY)

# Mapeo de idiomas (DeepL usa codificaciones específicas como 'EN', 'ES', 'PT')
LANG_MAP = {
    "es": "ES",
    "en": "EN-US",  # Usa "EN" para inglés
    "pt": "PT-BR"   # Usa "PT" para portugués
}

def translate_text(text, target_lang):
    """
    Traduce el texto usando DeepL.
    :param text: El texto a traducir.
    :param target_lang: El idioma de destino (ej. 'es', 'en', 'pt')
    :return: El texto traducido o None en caso de error.
    """
    deepl_lang = LANG_MAP.get(target_lang.lower(), "EN")  # Usa 'EN' como predeterminado

    try:
        # Realizar la traducción con la API de DeepL
        result = translator.translate_text(text, target_lang=deepl_lang)
        return result.text
    except Exception as e:
        print(f"❌ Error al traducir con DeepL: {e}")
        return None
