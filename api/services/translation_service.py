import deepl
import asyncio

API_KEY = '2e27de5f-2269-47fb-af2d-e373efdc6dcf:fx'
translator = deepl.Translator(API_KEY, server_url="https://api-free.deepl.com")

LANG_MAP = {
    "ar": "AR",
    "bg": "BG",
    "cs": "CS",
    "da": "DA",
    "de": "DE",
    "el": "EL",
    "en": "EN-US",
    "en-gb": "EN-GB",
    "en-us": "EN-US",
    "es-419": "ES-419",
    "et": "ET",
    "fi": "FI",
    "fr": "FR",
    "he": "HE",
    "hu": "HU",
    "id": "ID",
    "it": "IT",
    "ja": "JA",
    "ko": "KO",
    "lt": "LT",
    "lv": "LV",
    "nb": "NB",
    "nl": "NL",
    "pl": "PL",
    "pt": "PT-BR",
    "pt-br": "PT-BR",
    "pt-pt": "PT-PT",
    "ro": "RO",
    "ru": "RU",
    "sk": "SK",
    "sl": "SL",
    "sv": "SV",
    "th": "TH",
    "tr": "TR",
    "uk": "UK",
    "vi": "VI",
    "zh": "ZH-HANS",
    "zh-hans": "ZH-HANS",
    "zh-hant": "ZH-HANT"
}

class TranslationService:
    def __init__(self):
        self.translator = translator

    async def translate_text(self, text: str, target_language: str = "en", source_language: str = "es"):
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._translate_sync, text, target_language, source_language)
            return result
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def _translate_sync(self, text: str, target_language: str, source_language: str):
        if not text or not text.strip():
            return {"status": "error", "detail": "Empty text"}

        deepl_lang = LANG_MAP.get(target_language.lower())

        if not deepl_lang:
            return {"status": "error", "detail": f"Unsupported language: {target_language}"}

        try:

            result = self.translator.translate_text(
                text,
                source_lang=source_language.upper(),
                target_lang=deepl_lang
            )

            translated_text = result.text
            detected_lang = result.detected_source_lang

            if translated_text.lower().strip() == text.lower().strip():
                if target_language.lower() == source_language.lower():
                    return {
                        "status": "success",
                        "data": {"translated_text": text}
                    }
                return {"status": "error", "detail": "Translation unchanged"}

            return {
                "status": "success",
                "data": {
                    "translated_text": translated_text,
                    "detected_source_lang": detected_lang,
                    "target_lang": deepl_lang
                }
            }

        except deepl.DeepLException as e:
            return {"status": "error", "detail": f"DeepL error: {str(e)}"}
        except Exception as e:
            return {"status": "error", "detail": f"Translation error: {str(e)}"}

def translate_text(text, target_lang):
    if not text or not text.strip():
        return None

    deepl_lang = LANG_MAP.get(target_lang.lower())

    if not deepl_lang:
        return None

    try:

        result = translator.translate_text(
            text,
            source_lang="ES",
            target_lang=deepl_lang
        )

        translated_text = result.text
        detected_lang = result.detected_source_lang

        if translated_text.lower().strip() == text.lower().strip():
            if target_lang.lower() == "es":
                return text
            return None

        return translated_text

    except deepl.DeepLException:
        return None
    except Exception:
        return None

translation_service = TranslationService()