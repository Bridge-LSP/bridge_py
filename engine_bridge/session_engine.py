"""
SessionEngine - Core state machine for per-session LSP detection and processing.

This module encapsulates the logic from main.py into a stateful, reusable engine
that can be used by WebSocket and REST endpoints without duplicating detection,
timing, autocorrection, translation, and TTS logic.
"""

import time
import cv2
import numpy as np
import base64
import logging
from typing import Optional, Dict, Any, List
from collections import deque
import mediapipe as mp

from engine_bridge.autocorrector.autocorrector_core import AutoCorrector
from engine_bridge.hand_tracker import create_hand_landmarker
from api.services.translation_service import translate_text
from api.services.hand_detection import extract_features
from engine_bridge.text_to_speech import bridge_tts

logger = logging.getLogger(__name__)


class SessionEngine:
    """
    Per-session state machine that replicates main.py behavior for production.
    
    Manages detection state, timers, word/sentence building, translation, and TTS
    for a single user session without UI dependencies.
    """
    
    def __init__(
        self, 
        session_id: str,
        hand_landmarker,
        rf_model,
        lstm_model=None,
        preferences: Optional[Dict] = None
    ):
        self.session_id = session_id
        self.hand_landmarker = hand_landmarker
        self.rf_model = rf_model
        self.lstm_model = lstm_model
        
        # Initialize AutoCorrector instance for this session
        self.autocorrector = AutoCorrector()
        
        # Running state and preferences
        self.is_running = False
        self.tts_enabled = True
        self.tts_muted = False
        self.text_language = "es"
        self.target_language = "en"
        self.auto_translate = False
        self.word_pause_ms = 4000  # 4 seconds
        self.phrase_pause_ms = 8000  # 8 seconds
        
        # Detection & timing state (from main.py)
        self.last_prediction: Optional[str] = None
        self.last_time = 0.0
        self.last_letter_time = 0.0
        self.phrase_active = False
        self.word_finalized = False
        self.sentence_completed = False
        self.letra_actual = ""
        self.completed_sentence = ""
        self.translated_sentence = ""
        self.translated_lang = ""
        
        # LSTM-specific state
        self.lstm_buffer: Optional[deque] = None
        if self.lstm_model is not None:
            self.lstm_buffer = deque(maxlen=30)  # SEQUENCE_LENGTH from main.py
        
        # Constants from main.py
        self.COOLDOWN_TIME = 1.0
        self.FEATURES_PER_FRAME = 63
        self.LABEL_MAP_LSTM = {0: 'j', 1: 'll', 2: 'rr', 3: 'z', 4: 'ny'}
        
        # TTS state
        self.current_tts_audio: Optional[str] = None
        self.tts_audio_mime = "audio/mpeg"
        
        # State tracking for "just_*" flags
        self._word_just_finished = False
        self._sentence_just_completed = False
        self._translation_just_completed = False
        self._tts_just_generated = False
        
        # Apply preferences if provided
        if preferences:
            self.update_preferences(preferences)
            
        logger.info(f"SessionEngine initialized for session {session_id}")
    
    def update_preferences(self, preferences: Dict) -> None:
        """Update session preferences without affecting current state."""
        if "tts_enabled" in preferences:
            self.tts_enabled = bool(preferences["tts_enabled"])
        if "tts_muted" in preferences:
            self.tts_muted = bool(preferences["tts_muted"])
        if "text_language" in preferences:
            self.text_language = str(preferences["text_language"])
        if "target_language" in preferences:
            self.target_language = str(preferences["target_language"])
        if "auto_translate" in preferences:
            self.auto_translate = bool(preferences["auto_translate"])
        if "word_pause_ms" in preferences:
            self.word_pause_ms = int(preferences["word_pause_ms"])
        if "phrase_pause_ms" in preferences:
            self.phrase_pause_ms = int(preferences["phrase_pause_ms"])
            
        logger.debug(f"Session {self.session_id} preferences updated")
    
    def set_running(self, is_running: bool) -> None:
        """Set the running state (PLAY/STOP)."""
        self.is_running = is_running
        logger.info(f"Session {self.session_id} running state: {is_running}")
    
    def clear_all(self) -> None:
        """Clear all word buffer, sentence, translation, and TTS state."""
        # Reset autocorrector state
        self.autocorrector.clear_buffer()
        if hasattr(self.autocorrector, 'sentence_words'):
            self.autocorrector.sentence_words.clear()
        
        # Reset detection state
        self.last_prediction = None
        self.last_time = 0.0
        self.last_letter_time = 0.0
        self.phrase_active = False
        self.word_finalized = False
        self.sentence_completed = False
        self.letra_actual = ""
        self.completed_sentence = ""
        self.translated_sentence = ""
        self.translated_lang = ""
        
        # Clear LSTM buffer if applicable
        if self.lstm_buffer is not None:
            self.lstm_buffer.clear()
        
        # Clear TTS state
        self.current_tts_audio = None
        
        # Reset "just_*" flags
        self._word_just_finished = False
        self._sentence_just_completed = False
        self._translation_just_completed = False
        self._tts_just_generated = False
        
        logger.info(f"Session {self.session_id} cleared all state")
    
    def process_frame_base64(self, frame_b64: str) -> Dict[str, Any]:
        """
        Core method called whenever a new frame arrives over WebSocket.
        Replicates the main detection loop from main.py.
        """
        current_time = time.time()
        
        # If not running, just return current state
        if not self.is_running:
            return self._build_state_payload()
        
        try:
            # Decode base64 frame
            image = self._decode_frame_base64(frame_b64)
            if image is None:
                logger.warning(f"Session {self.session_id}: Invalid frame received")
                return self._build_state_payload()
            
            # Run MediaPipe hand detection
            results = self._run_mediapipe(image, current_time)
            
            # Process detection results
            detected = False
            
            # Try LSTM first if available
            if self.lstm_model is not None and self.lstm_buffer is not None:
                detected = self._run_lstm_if_applicable(results, current_time)
            
            # Try Random Forest if LSTM didn't detect anything
            if not detected and results.hand_landmarks:
                detected = self._run_rf_if_applicable(results, current_time)
            
            # Run timeout logic for word and phrase completion
            self._check_word_timeout(current_time)
            self._check_phrase_timeout(current_time)
            
            return self._build_state_payload()
            
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error processing frame: {e}")
            return self._build_state_payload()
    
    def _decode_frame_base64(self, frame_b64: str) -> Optional[np.ndarray]:
        """Decode base64 frame to OpenCV image."""
        try:
            # Handle data URL prefix if present
            if frame_b64.startswith('data:image'):
                frame_b64 = frame_b64.split(',', 1)[1]
            
            img_bytes = base64.b64decode(frame_b64)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            return image
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error decoding frame: {e}")
            return None
    
    def _run_mediapipe(self, image: np.ndarray, current_time: float):
        """Run MediaPipe hand detection on the image."""
        try:
            # Flip and convert to RGB (like main.py)
            image = cv2.flip(image, 1)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Create MediaPipe Image and run detection
            timestamp = int(current_time * 1000)  # Convert to milliseconds
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            results = self.hand_landmarker.detect_for_video(mp_image, timestamp)
            
            return results
        except Exception as e:
            logger.error(f"Session {self.session_id}: MediaPipe error: {e}")
            return None
    
    def _run_lstm_if_applicable(self, results, current_time: float) -> bool:
        """Process LSTM detection if model is available and results contain landmarks."""
        if not results or not results.hand_world_landmarks:
            return False
        
        try:
            # Add frame features to LSTM buffer
            for landmarks in results.hand_world_landmarks:
                frame_features = [coord for point in landmarks for coord in (point.x, point.y, point.z)]
                self.lstm_buffer.append(frame_features)
            
            # Check if buffer is full for prediction
            if len(self.lstm_buffer) == self.lstm_buffer.maxlen:
                seq = np.array(self.lstm_buffer)
                pred = self.lstm_model.predict(np.expand_dims(seq, axis=0), verbose=0)
                pred_label = np.argmax(pred)
                prob = float(pred[0][pred_label])
                
                if prob > 0.85:  # Confidence threshold from main.py
                    letra_lstm = self.LABEL_MAP_LSTM.get(pred_label, None)
                    if letra_lstm and letra_lstm != self.last_prediction:
                        if (current_time - self.last_time) > self.COOLDOWN_TIME:
                            return self._accept_new_letter(letra_lstm.upper(), current_time, "lstm")
            
            return False
        except Exception as e:
            logger.error(f"Session {self.session_id}: LSTM processing error: {e}")
            return False
    
    def _run_rf_if_applicable(self, results, current_time: float) -> bool:
        """Process Random Forest detection if hand landmarks are available."""
        if not results or not results.hand_world_landmarks:
            return False
        
        try:
            # Process each detected hand
            for idx, landmarks in enumerate(results.hand_world_landmarks):
                features = self._extract_features(landmarks)
                prediction = self.rf_model.predict(features)[0]
                
                if prediction != self.last_prediction:
                    if (current_time - self.last_time) > self.COOLDOWN_TIME:
                        return self._accept_new_letter(prediction.upper(), current_time, "rf")
            
            return False
        except Exception as e:
            logger.error(f"Session {self.session_id}: Random Forest processing error: {e}")
            return False
    
    def _extract_features(self, landmarks) -> np.ndarray:
        """Extract features from hand landmarks for Random Forest model."""
        return extract_features(landmarks)
    
    def _accept_new_letter(self, letter: str, current_time: float, model: str) -> bool:
        """Accept a new detected letter and update state."""
        try:
            # Clear completed sentence to start new one
            if self.sentence_completed:
                self._clear_completed_sentence()
            
            # Update state
            self.letra_actual = letter
            self.autocorrector.add_letter(letter.lower())
            self.last_prediction = letter.lower()
            self.last_time = current_time
            self.last_letter_time = current_time
            self.phrase_active = True
            self.word_finalized = False
            
            logger.debug(f"Session {self.session_id}: Accepted letter '{letter}' from {model}")
            return True
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error accepting letter: {e}")
            return False
    
    def _check_word_timeout(self, current_time: float) -> None:
        """Check if word should be finalized due to timeout."""
        word_buffer = getattr(self.autocorrector, 'word_buffer', [])
        if (word_buffer and 
            current_time - self.last_letter_time > (self.word_pause_ms / 1000.0) and
            not self.word_finalized):
            
            try:
                word = self.autocorrector.finish_word()
                if word.strip():
                    logger.debug(f"Session {self.session_id}: Word completed by timeout: '{word}'")
                    self._word_just_finished = True
                self.word_finalized = True
                self.letra_actual = ""
            except Exception as e:
                logger.error(f"Session {self.session_id}: Error finishing word: {e}")
    
    def _check_phrase_timeout(self, current_time: float) -> None:
        """Check if phrase should be completed due to timeout."""
        if (self.phrase_active and 
            current_time - self.last_letter_time > (self.phrase_pause_ms / 1000.0)):
            
            logger.debug(f"Session {self.session_id}: Phrase timeout triggered")
            self._complete_sentence()
    
    def _complete_sentence(self) -> None:
        """Complete the current sentence and trigger translation/TTS if needed."""
        try:
            final_sentence = self.autocorrector.end_sentence()
            if final_sentence.strip():
                self.completed_sentence = final_sentence
                self.sentence_completed = True
                self.phrase_active = False
                self._sentence_just_completed = True
                
                logger.info(f"Session {self.session_id}: Sentence completed: '{final_sentence}'")
                
                # Run translation if needed
                self._run_translation_if_needed()
                
                # Prepare TTS audio if enabled
                self._prepare_tts_audio()
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error completing sentence: {e}")
    
    def _run_translation_if_needed(self) -> None:
        """Run translation if auto_translate is enabled and languages differ."""
        if not self.auto_translate or not self.completed_sentence:
            return
        
        if self.text_language == self.target_language:
            return
        
        try:
            translated = translate_text(self.completed_sentence, self.target_language)
            if translated:
                self.translated_sentence = translated
                self.translated_lang = self.target_language
                self._translation_just_completed = True
                logger.info(f"Session {self.session_id}: Translation completed: '{translated}'")
        except Exception as e:
            logger.error(f"Session {self.session_id}: Translation error: {e}")
    
    def _prepare_tts_audio(self) -> None:
        """Prepare TTS audio if enabled and not muted."""
        if not self.tts_enabled or self.tts_muted:
            return
        
        try:
            # Use translated sentence if available, otherwise original
            text_to_speak = self.translated_sentence if self.translated_sentence else self.completed_sentence
            language = self.translated_lang if self.translated_sentence else self.text_language
            
            if text_to_speak:
                # Generate TTS audio (assuming bridge_tts has a method to get base64)
                # This is a placeholder - you may need to adapt based on your TTS implementation
                audio_base64 = self._generate_tts_base64(text_to_speak, language)
                if audio_base64:
                    self.current_tts_audio = audio_base64
                    self._tts_just_generated = True
                    logger.info(f"Session {self.session_id}: TTS audio prepared for: '{text_to_speak}'")
        except Exception as e:
            logger.error(f"Session {self.session_id}: TTS preparation error: {e}")
    
    def _generate_tts_base64(self, text: str, language: str) -> Optional[str]:
        """Generate TTS audio and return as base64. Placeholder implementation."""
        try:
            # This is a placeholder - adapt based on your bridge_tts implementation
            # You may need to modify bridge_tts to return audio data instead of playing directly
            
            # For now, returning None - you'll need to implement actual TTS to base64 conversion
            # bridge_tts.speak_sentence_completion(text, language)
            return None
        except Exception as e:
            logger.error(f"Session {self.session_id}: TTS generation error: {e}")
            return None
    
    def _clear_completed_sentence(self) -> None:
        """Clear completed sentence state to start a new one."""
        self.completed_sentence = ""
        self.sentence_completed = False
        self.translated_sentence = ""
        self.translated_lang = ""
        self.current_tts_audio = None
        logger.debug(f"Session {self.session_id}: Completed sentence cleared")
    
    def _build_state_payload(self) -> Dict[str, Any]:
        """Build the current state payload for frontend consumption."""
        current_time = time.time()
        time_since_last = current_time - self.last_letter_time if self.last_letter_time > 0 else 0
        
        # Get current word state from autocorrector
        raw_word = ''.join(getattr(self.autocorrector, 'word_buffer', []))
        corrected_word = self.autocorrector.get_current_word_corrected() if hasattr(self.autocorrector, 'get_current_word_corrected') else raw_word
        
        # Get current sentence
        current_sentence = ""
        if hasattr(self.autocorrector, 'sentence_words'):
            current_sentence = " ".join(self.autocorrector.sentence_words)
        
        # Check if word/phrase timers should be active
        word_timer_active = bool(raw_word and not self.word_finalized)
        phrase_timer_active = bool(self.phrase_active)
        
        # Build payload with current state and "just_*" flags
        payload = {
            "type": "state_update",
            "session_id": self.session_id,
            "timestamp": current_time,
            
            "detection": {
                "letter": self.letra_actual,
                "confidence": None,  # Would need to be stored from detection
                "model": "rf"  # Would need to track which model detected
            },
            
            "word": {
                "raw_buffer": raw_word,
                "corrected": corrected_word,
                "just_finished": self._word_just_finished
            },
            
            "sentence": {
                "current": current_sentence,
                "completed": self.sentence_completed,
                "just_completed": self._sentence_just_completed
            },
            
            "translation": {
                "enabled": self.auto_translate,
                "target_language": self.target_language,
                "translated_sentence": self.translated_sentence if self.translated_sentence else None,
                "just_translated": self._translation_just_completed
            },
            
            "timers": {
                "time_since_last_letter": time_since_last,
                "word_timer_active": word_timer_active,
                "phrase_timer_active": phrase_timer_active
            },
            
            "tts": {
                "enabled": self.tts_enabled and not self.tts_muted,
                "muted": self.tts_muted,
                "audio_available": self.current_tts_audio is not None,
                "audio_base64": self.current_tts_audio,
                "audio_mime_type": self.tts_audio_mime,
                "just_generated": self._tts_just_generated
            }
        }
        
        # Reset "just_*" flags after building payload (they're only true for one frame)
        self._word_just_finished = False
        self._sentence_just_completed = False
        self._translation_just_completed = False
        self._tts_just_generated = False
        
        return payload
    
    def manual_finalize_phrase(self) -> Dict[str, Any]:
        """Manually trigger phrase completion and return state."""
        self._complete_sentence()
        return self._build_state_payload()