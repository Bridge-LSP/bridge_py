import pyttsx3
import pygame
import tempfile
import os
import threading
import time
from typing import Optional, Dict

class RealtimeTTS:

    def __init__(self):
        self.engine = pyttsx3.init()
        self._setup_engine()
        self._setup_audio_player()
        self.is_playing = False
        self.current_file = None

    def _setup_engine(self):
        self.engine.setProperty('rate', 180)
        self.engine.setProperty('volume', 0.9)
        self.voices_map = self._map_available_voices()

    def _setup_audio_player(self):
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=1024)
        except Exception:
            pass

    def _map_available_voices(self) -> Dict[str, str]:

        voices_map = {}
        voices = self.engine.getProperty('voices')

        lang_patterns = {
            'es': ['spanish', 'españa', 'mexico', 'es_'],
            'en': ['english', 'united states', 'en_'],
            'fr': ['french', 'france', 'fr_'],
            'de': ['german', 'deutsch', 'de_'],
            'it': ['italian', 'italy', 'it_'],
            'pt': ['portuguese', 'brasil', 'pt_'],
            'ru': ['russian', 'russia', 'ru_'],
            'zh': ['chinese', 'mandarin', 'zh_'],
            'ja': ['japanese', 'japan', 'ja_'],
            'ko': ['korean', 'korea', 'ko_']
        }

        for voice in voices:
            voice_id = voice.id.lower()
            voice_name = voice.name.lower() if voice.name else ""

            for lang_code, patterns in lang_patterns.items():
                if any(pattern in voice_id or pattern in voice_name for pattern in patterns):
                    if lang_code not in voices_map:
                        voices_map[lang_code] = voice.id
                        break

        if voices and 'es' not in voices_map:
            voices_map['es'] = voices[0].id

        return voices_map

    def _set_voice_for_language(self, lang_code: str):
        voice_id = self.voices_map.get(lang_code, self.voices_map.get('es'))
        if voice_id:
            self.engine.setProperty('voice', voice_id)

    def speak_text_async(self, text: str, language: str = 'es') -> bool:

        if not text.strip():
            return False

        thread = threading.Thread(
            target=self._speak_text_sync,
            args=(text, language),
            daemon=True
        )
        thread.start()
        return True

    def _speak_text_sync(self, text: str, language: str):
        try:
            self._set_voice_for_language(language)

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            temp_path = temp_file.name
            temp_file.close()

            self.engine.save_to_file(text, temp_path)
            self.engine.runAndWait()

            if os.path.exists(temp_path):
                self._play_audio_file(temp_path)
                try:
                    os.unlink(temp_path)
                except:
                    pass

        except Exception:
            pass

    def _play_audio_file(self, file_path: str):

        try:
            self.is_playing = True
            self.current_file = file_path

            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                time.sleep(0.1)

            self.is_playing = False
            self.current_file = None

        except Exception:
            self.is_playing = False

    def stop_current_audio(self):
        if self.is_playing:
            pygame.mixer.music.stop()
            self.is_playing = False

    def speak_sentence_completion(self, sentence: str, language: str = 'es'):
        return self.speak_text_async(sentence, language)

    def get_status(self) -> Dict:

        return {
            "is_playing": self.is_playing,
            "current_file": self.current_file,
            "available_languages": list(self.voices_map.keys()),
            "engine_ready": self.engine is not None
        }

bridge_tts = RealtimeTTS()