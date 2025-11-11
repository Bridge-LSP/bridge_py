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
    "nb": "NB",        # Norwegian Bokmål - Noruego bokmål
    "nl": "NL",        # Dutch - Holandés
    "pl": "PL",        # Polish - Polaco
    "pt": "PT-BR",     # Portuguese - Portugués
    "pt-br": "PT-BR",  # Portuguese (Brazilian) - Portugués brasileño
    "pt-pt": "PT-PT",  # Portuguese (European) - Portugués europeo
    "ro": "RO",        # Romanian - Rumano
    "ru": "RU",        # Russian - Ruso
    "sk": "SK",        # Slovak - Eslovaco
    "sl": "SL",        # Slovenian - Esloveno
    "sv": "SV",        # Swedish - Sueco
    "th": "TH",        # Thai - Tailandés
    "tr": "TR",        # Turkish - Turco
    "uk": "UK",        # Ukrainian - Ucraniano
    "vi": "VI",        # Vietnamese - Vietnamita
    "zh": "ZH-HANS",   # Chinese - Chino
    "zh-hans": "ZH-HANS", # Chinese (Simplified) - Chino simplificado
    "zh-hant": "ZH-HANT"  # Chinese (Traditional) - Chino tradicional
}

class TranslationService:
    def __init__(self):
        self.translator = translator
    
    async def translate_text(self, text: str, target_language: str = "en", source_language: str = "es"):
        """Async wrapper for translation"""
        try:
            # Run the sync translation in a thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._translate_sync, text, target_language, source_language)
            return result
        except Exception as e:
            print(f"❌ Async translation error: {e}")
            return {"status": "error", "detail": str(e)}
    
    def _translate_sync(self, text: str, target_language: str, source_language: str):
        """Synchronous translation logic"""
        if not text or not text.strip():
            print("❌ Texto vacío para traducir")
            return {"status": "error", "detail": "Empty text"}
            
        deepl_lang = LANG_MAP.get(target_language.lower())
        
        if not deepl_lang:
            print(f"❌ Idioma no soportado: {target_language}")
            return {"status": "error", "detail": f"Unsupported language: {target_language}"}

        try:
            print(f"🔍 DEBUG: Traduciendo '{text}' de {source_language.upper()} a {deepl_lang}")
            
            result = self.translator.translate_text(
                text, 
                source_lang=source_language.upper(),
                target_lang=deepl_lang
            )
            
            translated_text = result.text
            detected_lang = result.detected_source_lang
            
            print(f"🔍 DEBUG: Idioma fuente detectado: {detected_lang}")
            print(f"🔍 DEBUG: Resultado: '{translated_text}'")
            
            if translated_text.lower().strip() == text.lower().strip():
                print(f"⚠️ La traducción es igual al original")
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
            print(f"❌ Error específico de DeepL: {e}")
            return {"status": "error", "detail": f"DeepL error: {str(e)}"}
        except Exception as e:
            print(f"❌ Error general al traducir: {e}")
            return {"status": "error", "detail": f"Translation error: {str(e)}"}

# Legacy function for backward compatibility
def translate_text(text, target_lang):
    if not text or not text.strip():
        print("❌ Texto vacío para traducir")
        return None
        
    deepl_lang = LANG_MAP.get(target_lang.lower())
    
    if not deepl_lang:
        print(f"❌ Idioma no soportado: {target_lang}")
        return None

    try:
        print(f"🔍 DEBUG: Traduciendo '{text}' de ES a {deepl_lang}")
        
        result = translator.translate_text(
            text, 
            source_lang="ES",
            target_lang=deepl_lang
        )
        
        translated_text = result.text
        detected_lang = result.detected_source_lang
        
        print(f"🔍 DEBUG: Idioma fuente forzado: ES")
        print(f"🔍 DEBUG: Resultado: '{translated_text}'")
        
        if translated_text.lower().strip() == text.lower().strip():
            print(f"⚠️ La traducción es igual al original")
            if target_lang.lower() == "es":
                return text
            return None
            
        return translated_text
        
    except deepl.DeepLException as e:
        print(f"❌ Error específico de DeepL: {e}")
        return None
    except Exception as e:
        print(f"❌ Error general al traducir: {e}")
        return None

# Global service instance
translation_service = TranslationService()