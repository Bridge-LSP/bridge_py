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
from threading import Timer

from engine_bridge.autocorrector.autocorrector_core import AutoCorrector
from engine_bridge.hand_tracker import create_hand_landmarker
from api.services.translation_service import translate_text
from api.services.hand_detection import extract_features
from engine_bridge.text_to_speech import bridge_tts
from engine_bridge.bert_model_loader import is_loading, is_bert_available

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
        
        if is_loading():
            logger.warning(f"Session {session_id}: BERT models still loading, autocorrection may be limited")
        
        self.autocorrector = AutoCorrector()
        
        # Performance optimization: Pre-allocate Random Forest feature buffer
        # 21 landmarks * 3 coordinates (x, y, z) = 63 features
        self._rf_feature_buffer = np.zeros((1, 63), dtype=np.float32)
        
        self.is_running = False
        self.tts_enabled = True
        self.tts_muted = False
        self.text_language = "es"
        self.target_language = "en"
        self.auto_translate = False
        self.word_pause_ms = 3000 
        self.phrase_pause_ms = 5000
        
        # Background timer for timeout checking
        self._timeout_timer = None
        self._timer_interval = 1.0  # Check every 1 second
        
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
        
        self.lstm_buffer: Optional[deque] = None
        if self.lstm_model is not None:
            self.lstm_buffer = deque(maxlen=30)
        
        self.COOLDOWN_TIME = 1.0
        self.FEATURES_PER_FRAME = 63
        self.LABEL_MAP_LSTM = {0: 'j', 1: 'll', 2: 'rr', 3: 'z', 4: 'ny'}
        
        self.current_tts_audio: Optional[str] = None
        self.tts_audio_mime = "audio/mpeg"
        
        self._word_just_finished = False
        self._sentence_just_completed = False
        self._translation_just_completed = False
        self._tts_just_generated = False
        
        if preferences:
            self.update_preferences(preferences)
            
        logger.info(f"SessionEngine initialized for session {session_id}")
        
        # Iniciar timer de background para timeouts
        self._start_background_timer()
    
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
        self.autocorrector.clear_buffer()
        if hasattr(self.autocorrector, 'sentence_words'):
            self.autocorrector.sentence_words.clear()
        
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
        
        if self.lstm_buffer is not None:
            self.lstm_buffer.clear()
        
        self.current_tts_audio = None
        
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
        print(f"📥 WS frame received | bytes: {len(frame_b64)}")
        
        current_time = time.time()
        
        if not self.is_running:
            return self._build_state_payload()
        
        try:
            image = self._decode_frame_base64(frame_b64)
            if image is None:
                logger.warning(f"Session {self.session_id}: Invalid frame received")
                return self._build_state_payload()
            
            results = self._run_mediapipe(image, current_time)
            
            detected = False
            
            if results.hand_landmarks:
                detected = self._run_rf_if_applicable(results, current_time)
            
            self._check_word_timeout(current_time)
            self._check_phrase_timeout(current_time)
            
            return self._build_state_payload()
            
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error processing frame: {e}")
            return self._build_state_payload()
    
    def _decode_frame_base64(self, frame_b64: str) -> Optional[np.ndarray]:
        """Decode base64 frame to OpenCV image with centralized preprocessing."""
        print("🟢 _decode_frame_base64 ENTERED")
        
        # Optimización 1: Validar frameBase64 antes de decodificar
        if not frame_b64 or not frame_b64.startswith("data:image"):
            print("❌ Invalid frameBase64: empty or missing data:image prefix")
            return None
            
        try:
            from api.services.frame_preprocessor import frame_preprocessor
            print("🟡 frame_preprocessor imported")
            
            if frame_b64.startswith('data:image'):
                print("🟣 Stripping data: prefix")
                frame_b64 = frame_b64.split(',', 1)[1]
            
            print(f"🔵 Decoding base64 | length: {len(frame_b64)}")
            img_bytes = base64.b64decode(frame_b64)
            print(f"🟠 Decoded to {len(img_bytes)} bytes")
            image = frame_preprocessor.decode_and_preprocess(img_bytes)
            print(f"🟤 Preprocessor returned: {image.shape if image is not None else 'None'}")
            
            if image is not None:
                # Controlar guardado de debug frame con variable de entorno
                try:
                    import os
                    debug_enabled = os.getenv("BRIDGE_DEBUG_FRAMES", "true").lower() == "true"
                    if debug_enabled:
                        cv2.imwrite("debug_ws_frame.jpg", image)
                        print(f"[DEBUG][WS] Saved frame to debug_ws_frame.jpg | shape={image.shape}, dtype={image.dtype}")
                        print(f"[DEBUG][WS] Pixel stats: min={image.min()}, max={image.max()}, mean={image.mean():.2f}")
                    else:
                        print(f"[DEBUG][WS] Debug frame saving disabled via BRIDGE_DEBUG_FRAMES=false")
                except Exception as e:
                    print(f"[DEBUG][WS] Error saving debug frame: {e}")
                
                print(f"➡️  Decoded image shape: {image.shape}")
                print(f"➡️  dtype: {image.dtype}")
                logger.debug(f"Session {self.session_id}: Decoded frame shape={image.shape}, dtype={image.dtype}")
            else:
                print("⚠️  WARNING: frame_preprocessor.decode_and_preprocess() returned None!")
                logger.warning(f"Session {self.session_id}: frame_preprocessor returned None")
            
            return image
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error decoding frame: {e}")
            return None
    
    def _run_mediapipe(self, image: np.ndarray, current_time: float):
        """Run MediaPipe hand detection on the image.
        
        IMPORTANT: frame_preprocessor already handles flipping if configured.
        We DO NOT flip again here to avoid double-flip bug.
        main.py flips directly from camera, but WebSocket frames come pre-processed.
        """
        try:
            print(f"[DEBUG][MP] Input frame shape for MediaPipe: {image.shape}, dtype={image.dtype}")
            logger.debug(f"Session {self.session_id}: MediaPipe input shape={image.shape}")
            
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            timestamp = int(current_time * 1000)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            results = self.hand_landmarker.detect_for_video(mp_image, timestamp)
            
            if results and results.handedness:
                print(f"[DEBUG][MP] MediaPipe detected {len(results.handedness)} hand(s)")
                for idx, handedness in enumerate(results.handedness):
                    category = handedness[0].category_name
                    score = handedness[0].score
                    print(f"[DEBUG][MP]   Hand {idx}: {category} ({score:.3f})")
            else:
                print("[DEBUG][MP] MediaPipe detected NO HANDS")
            
            if not results or not results.hand_landmarks:
                print("❌ MediaPipe: NO HANDS DETECTED")
            else:
                hands_detected = len(results.hand_landmarks)
                print(f"✋ MediaPipe: detected {hands_detected} hand(s)")
            
            hands_detected = len(results.hand_landmarks) if results and results.hand_landmarks else 0
            logger.debug(f"Session {self.session_id}: MediaPipe detected {hands_detected} hand(s)")
            
            return results
        except Exception as e:
            logger.error(f"Session {self.session_id}: MediaPipe error: {e}", exc_info=True)
            return None
    
    def _run_lstm_if_applicable(self, results, current_time: float) -> bool:
        """Process LSTM detection if model is available and results contain landmarks."""
        if self.lstm_model is None:
            return False
            
        if not results or not results.hand_world_landmarks:
            return False
        
        if self.lstm_buffer is None:
            return False
        
        try:
            for landmarks in results.hand_world_landmarks:
                frame_features = [coord for point in landmarks for coord in (point.x, point.y, point.z)]
                self.lstm_buffer.append(frame_features)
            
            if len(self.lstm_buffer) == self.lstm_buffer.maxlen:
                seq = np.array(self.lstm_buffer)
                pred = self.lstm_model.predict(np.expand_dims(seq, axis=0), verbose=0)
                pred_label = np.argmax(pred)
                prob = float(pred[0][pred_label])
                
                if prob > 0.85:
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
            for idx, landmarks in enumerate(results.hand_world_landmarks):
                features = self._extract_features(landmarks)
                
                flattened = features.flatten() if hasattr(features, 'flatten') else features
                print(f"[DEBUG][RF] Input vector length: {len(flattened)}")
                first_10 = flattened[:10].tolist() if hasattr(flattened, 'tolist') else list(flattened[:10])
                print(f"[DEBUG][RF] First 10 values: {first_10}")
                print(f"🌲 RF input vector length: {len(features[0]) if len(features.shape) > 1 else len(features)}")
                
                prediction = self.rf_model.predict(features)[0]
                proba = self.rf_model.predict_proba(features)[0]
                confidence = max(proba)
                
                print(f"[DEBUG][RF] Prediction: {prediction}")
                print(f"🌲 RF prediction result: '{prediction}' (confidence: {confidence:.3f})")
                
                if prediction != self.last_prediction:
                    if (current_time - self.last_time) > self.COOLDOWN_TIME:
                        return self._accept_new_letter(prediction.upper(), current_time, "rf")
            
            return False
        except Exception as e:
            logger.error(f"Session {self.session_id}: Random Forest processing error: {e}")
            return False
    
    def _extract_features(self, landmarks) -> np.ndarray:
        """Extract features from hand landmarks for Random Forest model.
        
        Optimized version using pre-allocated buffer to avoid memory allocation overhead.
        """
        # Use pre-allocated buffer instead of creating new arrays
        feature_idx = 0
        for lm in landmarks:
            self._rf_feature_buffer[0, feature_idx] = lm.x
            self._rf_feature_buffer[0, feature_idx + 1] = lm.y  
            self._rf_feature_buffer[0, feature_idx + 2] = lm.z
            feature_idx += 3
        
        return self._rf_feature_buffer
    
    def _accept_new_letter(self, letter: str, current_time: float, model: str) -> bool:
        """Accept a new detected letter and update state."""
        try:
            if self.sentence_completed:
                self._clear_completed_sentence()
            
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
                
                self._run_translation_if_needed()
                
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
        logger.debug(f"🔊 TTS check: enabled={self.tts_enabled}, muted={self.tts_muted}")
        if not self.tts_enabled or self.tts_muted:
            logger.warning(f"🔇 TTS skipped: enabled={self.tts_enabled}, muted={self.tts_muted}")
            return
        
        try:
            text_to_speak = self.translated_sentence if self.translated_sentence else self.completed_sentence
            language = self.translated_lang if self.translated_sentence else self.text_language
            
            if text_to_speak:
                audio_base64 = self._generate_tts_base64(text_to_speak, language)
                if audio_base64:
                    self.current_tts_audio = audio_base64
                    self._tts_just_generated = True
                    logger.info(f"Session {self.session_id}: TTS audio prepared for: '{text_to_speak}'")
        except Exception as e:
            logger.error(f"Session {self.session_id}: TTS preparation error: {e}")
    
    def _generate_tts_base64(self, text: str, language: str) -> Optional[str]:
        """Generate TTS audio and return as base64."""
        try:
            logger.info(f"🔊 Generating TTS for: '{text}' in language: {language}")
            
            # Usar bridge_tts para generar audio
            audio_base64 = bridge_tts.generate_audio_base64(text, language)
            
            if audio_base64:
                logger.info(f"✅ TTS audio generated successfully (length: {len(audio_base64)} chars)")
                return audio_base64
            else:
                logger.warning(f"❌ TTS generation failed - no audio returned")
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
    
    def _start_background_timer(self) -> None:
        """Iniciar timer de background para verificar timeouts independientemente de frames."""
        if self._timeout_timer is not None:
            self._timeout_timer.cancel()
        
        self._timeout_timer = Timer(self._timer_interval, self._background_timeout_check)
        self._timeout_timer.daemon = True
        self._timeout_timer.start()
    
    def _background_timeout_check(self) -> None:
        """Verificación periódica de timeouts en background."""
        if not self.is_running:
            return
            
        try:
            current_time = time.time()
            
            # Solo verificar timeouts si hay actividad reciente
            if (hasattr(self, 'last_letter_time') and 
                current_time - self.last_letter_time > 0.5):  # 500ms después de última letra
                
                old_word_finalized = self.word_finalized
                old_sentence_completed = self.sentence_completed
                
                self._check_word_timeout(current_time)
                self._check_phrase_timeout(current_time)
                
                # Si hubo cambios, log para debug
                if (self.word_finalized != old_word_finalized or 
                    self.sentence_completed != old_sentence_completed):
                    logger.debug(f"⏰ Background timer triggered timeout: word_finalized={self.word_finalized}, sentence_completed={self.sentence_completed}")
                    
        except Exception as e:
            logger.error(f"Error in background timeout check: {e}")
        finally:
            # Continuar el timer si la sesión sigue activa
            if self.running:
                self._start_background_timer()
    
    def _start_background_timer(self) -> None:
        """Iniciar timer de background para verificar timeouts independientemente de frames."""
        if self._timeout_timer is not None:
            self._timeout_timer.cancel()
        
        self._timeout_timer = Timer(self._timer_interval, self._background_timeout_check)
        self._timeout_timer.daemon = True
        self._timeout_timer.start()
    
    def _background_timeout_check(self) -> None:
        """Verificación periódica de timeouts en background."""
        if not self.is_running:
            return
            
        try:
            current_time = time.time()
            
            # Verificar timeouts si hay actividad de letras detectadas
            if hasattr(self, 'last_letter_time') and self.last_letter_time > 0:
                
                logger.debug(f"⏰ Background timer check: last_letter_time={current_time - self.last_letter_time:.1f}s ago")
                
                old_word_finalized = self.word_finalized
                old_sentence_completed = self.sentence_completed
                
                self._check_word_timeout(current_time)
                self._check_phrase_timeout(current_time)
                
                # Si hubo cambios, log para debug
                if (self.word_finalized != old_word_finalized or 
                    self.sentence_completed != old_sentence_completed):
                    logger.info(f"⏰ Background timer triggered timeout: word_finalized={self.word_finalized}, sentence_completed={self.sentence_completed}")
                    
        except Exception as e:
            logger.error(f"Error in background timeout check: {e}")
        finally:
            # Continuar el timer si la sesión sigue activa
            if self.running:
                self._start_background_timer()
    
    def _build_state_payload(self) -> Dict[str, Any]:
        """Build the current state payload for frontend consumption."""
        current_time = time.time()
        time_since_last = current_time - self.last_letter_time if self.last_letter_time > 0 else 0
        
        raw_word = ''.join(getattr(self.autocorrector, 'word_buffer', []))
        corrected_word = self.autocorrector.get_current_word_corrected() if hasattr(self.autocorrector, 'get_current_word_corrected') else raw_word
        
        current_sentence = ""
        if hasattr(self.autocorrector, 'sentence_words'):
            current_sentence = " ".join(self.autocorrector.sentence_words)
        
        word_timer_active = bool(raw_word and not self.word_finalized)
        phrase_timer_active = bool(self.phrase_active)
        
        payload = {
            "type": "state_update",
            "session_id": self.session_id,
            "timestamp": current_time,
            
            "detection": {
                "letter": self.letra_actual,
                "confidence": None,
                "model": "rf"
            },
            
            "word": {
                "raw_buffer": raw_word,
                "corrected": corrected_word,
                "just_finished": self._word_just_finished
            },
            
            "sentence": {
                "current": current_sentence,
                "completed": self.completed_sentence,
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
        
        self._word_just_finished = False
        self._sentence_just_completed = False
        self._translation_just_completed = False
        self._tts_just_generated = False
        
        return payload
    
    def manual_finalize_phrase(self) -> Dict[str, Any]:
        """Manually trigger phrase completion and return state."""
        self._complete_sentence()
        return self._build_state_payload()