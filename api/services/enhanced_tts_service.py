from typing import Dict, Optional
from fastapi.responses import StreamingResponse
import io
import tempfile
from engine_bridge.text_to_speech import bridge_tts

class EnhancedTTSService:
    def __init__(self):
        self.tts_engine = bridge_tts
        self.active_sessions = {}

    def generate_audio_for_phrase(
        self,
        text: str,
        language: str = "es",
        session_id: Optional[str] = None,
        voice_speed: float = 1.0,
        voice_pitch: float = 1.0
    ) -> Dict:

        try:
            if not text.strip():
                return {"error": "Text cannot be empty"}

            if hasattr(self.tts_engine.engine, 'setProperty'):
                original_rate = self.tts_engine.engine.getProperty('rate')
                new_rate = int(original_rate * voice_speed)
                self.tts_engine.engine.setProperty('rate', new_rate)

            success = self.tts_engine.speak_text_async(text, language)

            if success:
                if session_id:
                    self.active_sessions[session_id] = {
                        "last_text": text,
                        "last_language": language,
                        "is_playing": True
                    }

                return {
                    "success": True,
                    "text": text,
                    "language": language,
                    "session_id": session_id,
                    "audio_generated": True
                }
            else:
                return {"error": "Failed to generate audio"}

        except Exception as e:
            return {"error": str(e)}

    def stop_audio(self, session_id: Optional[str] = None) -> Dict:

        try:
            self.tts_engine.stop_current_audio()

            if session_id and session_id in self.active_sessions:
                self.active_sessions[session_id]["is_playing"] = False

            return {"success": True, "message": "Audio stopped"}

        except Exception as e:
            return {"error": str(e)}

    def get_tts_status(self, session_id: Optional[str] = None) -> Dict:

        try:
            general_status = self.tts_engine.get_status()

            session_info = {}
            if session_id and session_id in self.active_sessions:
                session_info = self.active_sessions[session_id]

            return {
                "general_status": general_status,
                "session_info": session_info,
                "available_languages": list(self.tts_engine.voices_map.keys())
            }

        except Exception as e:
            return {"error": str(e)}

enhanced_tts_service = EnhancedTTSService()