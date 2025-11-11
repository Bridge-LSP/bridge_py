from fastapi import APIRouter, HTTPException, Body, Header
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
import time
import logging
from api.services.timer_manager_service import timer_manager_service
from api.dependencies import get_hand_landmarker, get_forest_model
from api.services.hand_detection import extract_features
import cv2
import numpy as np
import base64
import mediapipe as mp

router = APIRouter()
logger = logging.getLogger(__name__)

class ContinuousDetectionRequest(BaseModel):
    session_id: str
    frameBase64: str
    enable_timers: Optional[bool] = True
    confidence_threshold: Optional[float] = 0.70

class DetectionStateResponse(BaseModel):
    status: str = "success"
    changed: List[str] = []
    letter_detected: Optional[str] = None
    confidence: Optional[float] = None
    word_buffer: str
    predicted_word: str
    sentence: str
    word_timer_active: bool
    phrase_timer_active: bool
    time_since_last_detection: float
    should_auto_finish_word: bool
    should_auto_finish_phrase: bool

detection_state = {
    "landmarker": get_hand_landmarker(),
    "model": get_forest_model(),
    "last_predictions": {},
    "last_times": {},
    "cooldown_time": 1.0
}

class SessionStateCache:
    def __init__(self, ttl_seconds=30):
        self.cache = {}
        self.ttl = ttl_seconds

    def cleanup_expired(self):

        current_time = time.time()
        expired_sessions = [
            session_id for session_id, data in self.cache.items()
            if current_time - data["timestamp"] > self.ttl
        ]
        for session_id in expired_sessions:
            del self.cache[session_id]

    def get_last_state(self, session_id: str) -> Optional[Dict[str, Any]]:

        self.cleanup_expired()
        return self.cache.get(session_id, {}).get("state")

    def update_state(self, session_id: str, new_state: Dict[str, Any]) -> List[str]:

        self.cleanup_expired()
        last_state = self.get_last_state(session_id)

        self.cache[session_id] = {
            "state": new_state.copy(),
            "timestamp": time.time()
        }

        if last_state is None:
            return list(new_state.keys())

        changed_fields = []
        for key, value in new_state.items():
            if key not in last_state or last_state[key] != value:
                changed_fields.append(key)

        return changed_fields

session_cache = SessionStateCache(ttl_seconds=30)

@router.post(
    "/continuous-detect",
    response_model=DetectionStateResponse,
    summary="Continuous detection with automatic timers",
    description="Processes frame with automatic timer management (replicates main.py loop)"
)
async def continuous_detect(
    request: ContinuousDetectionRequest,
    x_client_token: Optional[str] = Header(None)
):

    start_time = time.time()
    frame_id = int(start_time * 1000) % 100000

    try:
        session_id = request.session_id
        current_time = time.time()

        if x_client_token and session_id in timer_manager_service.autocorrector_service.sessions:
            timer_manager_service.autocorrector_service.sessions[session_id]["client_token"] = x_client_token

        try:
            img_bytes = base64.b64decode(request.frameBase64, validate=True)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Invalid image")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image: {str(e)}")

        if session_id not in timer_manager_service.autocorrector_service.sessions:
            timer_manager_service.autocorrector_service.create_session(session_id)

        session = timer_manager_service.autocorrector_service.sessions[session_id]
        autocorrector = session["autocorrector"]

        letter_detected = None
        confidence = None
        detected = False

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

        results = detection_state["landmarker"].detect(mp_image)

        if results.hand_world_landmarks and results.handedness:
            for idx, landmarks in enumerate(results.hand_world_landmarks):
                features = extract_features(landmarks)
                prediction = detection_state["model"].predict(features)[0]
                probabilities = detection_state["model"].predict_proba(features)[0]
                confidence = float(max(probabilities))

                if confidence >= request.confidence_threshold:
                    last_prediction = detection_state["last_predictions"].get(session_id)
                    last_time = detection_state["last_times"].get(session_id, 0)

                    if prediction != last_prediction and (current_time - last_time) > detection_state["cooldown_time"]:
                        letter_detected = prediction.upper()
                        detected = True

                        detection_state["last_predictions"][session_id] = prediction
                        detection_state["last_times"][session_id] = current_time

                        result = timer_manager_service.autocorrector_service.add_letter(session_id, letter_detected.lower())

                        if "error" not in result and request.enable_timers:
                            timer_manager_service.reset_timers(session_id)
                            timer_manager_service.start_word_timer(session_id)

                            if autocorrector.sentence_words:
                                timer_manager_service.start_phrase_timer(session_id)

                        latency_ms = int((time.time() - start_time) * 1000)
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"[Detect] Frame {frame_id} | latency={latency_ms}ms | confidence={confidence:.2f} | letter={letter_detected}")
                        break

        session_status = timer_manager_service.autocorrector_service.get_session_status(session_id)
        timer_status = timer_manager_service.get_timer_status(session_id)

        last_time = detection_state["last_times"].get(session_id, current_time)
        time_since_last = current_time - last_time

        should_auto_finish_word = (
            bool(autocorrector.word_buffer) and
            time_since_last > timer_manager_service.PAUSE_THRESHOLD and
            not session.get("word_finalized", False)
        )

        should_auto_finish_phrase = (
            bool(autocorrector.sentence_words) and
            time_since_last > timer_manager_service.PHRASE_TIMEOUT
        )

        current_state = {
            "letter_detected": letter_detected,
            "confidence": confidence,
            "word_buffer": session_status.get("current_buffer", ""),
            "predicted_word": session_status.get("predicted_word", ""),
            "sentence": session_status.get("sentence", ""),
            "word_timer_active": timer_status.get("word_timer", False),
            "phrase_timer_active": timer_status.get("phrase_timer", False),
            "time_since_last_detection": time_since_last,
            "should_auto_finish_word": should_auto_finish_word,
            "should_auto_finish_phrase": should_auto_finish_phrase
        }

        changed_fields = session_cache.update_state(session_id, current_state)

        total_latency_ms = int((time.time() - start_time) * 1000)
        if not detected and logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[Detect] Frame {frame_id} | latency={total_latency_ms}ms | no detection")

        return DetectionStateResponse(
            status="success",
            changed=changed_fields,
            **current_state
        )

    except Exception as e:
        logger.error(f"[Detect] Frame {frame_id} | error={str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/session-timeline/{session_id}",
    summary="Get session timeline and timing status",
    description="Returns detailed timing information for a session (main.py state)"
)
async def get_session_timeline(session_id: str):

    try:
        current_time = time.time()

        last_prediction = detection_state["last_predictions"].get(session_id)
        last_time = detection_state["last_times"].get(session_id, current_time)
        time_since_last = current_time - last_time

        session_status = timer_manager_service.autocorrector_service.get_session_status(session_id)
        timer_status = timer_manager_service.get_timer_status(session_id)

        session_exists = session_id in timer_manager_service.autocorrector_service.sessions
        session_data = timer_manager_service.autocorrector_service.sessions.get(session_id, {}) if session_exists else {}

        data = {
            "session_id": session_id,
            "session_exists": session_exists,
            "detection_state": {
                "last_prediction": last_prediction,
                "last_detection_time": last_time,
                "time_since_last_detection": time_since_last,
                "cooldown_time": detection_state["cooldown_time"]
            },
            "session_state": session_status,
            "timer_state": timer_status,
            "timing_thresholds": {
                "pause_threshold": timer_manager_service.PAUSE_THRESHOLD,
                "phrase_timeout": timer_manager_service.PHRASE_TIMEOUT
            },
            "auto_finish_checks": {
                "should_auto_finish_word": time_since_last > timer_manager_service.PAUSE_THRESHOLD,
                "should_auto_finish_phrase": time_since_last > timer_manager_service.PHRASE_TIMEOUT,
                "word_finalized": session_data.get("word_finalized", False)
            }
        }

        return {
            "status": "success",
            "data": data
        }

    except Exception as e:
        logger.error(f"[Timeline] Error getting session timeline for {session_id}: {str(e)}")
        return {
            "status": "error",
            "detail": str(e)
        }

@router.post(
    "/reset-detection-state",
    summary="Reset detection state for session",
    description="Resets detection state and timers (equivalent to 'R' key in main.py)"
)
async def reset_detection_state(payload: dict = Body(...)):

    try:
        session_id = payload.get("session_id")
        if not session_id:
            return {
                "status": "error",
                "detail": "session_id required"
            }

        if session_id in detection_state["last_predictions"]:
            del detection_state["last_predictions"][session_id]
        if session_id in detection_state["last_times"]:
            del detection_state["last_times"][session_id]

        timer_manager_service.reset_timers(session_id)

        if session_id in timer_manager_service.autocorrector_service.sessions:
            session = timer_manager_service.autocorrector_service.sessions[session_id]
            autocorrector = session["autocorrector"]
            autocorrector.clear_buffer()
            autocorrector.end_sentence()
            session["word_finalized"] = False
            session["sentence_completed"] = False
            session.pop("completed_sentence", None)
            session.pop("translated_sentence", None)

        if session_id in session_cache.cache:
            del session_cache.cache[session_id]

        logger.info(f"[Reset] Detection state and timers reset for session {session_id}")

        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "reset_complete": True,
                "message": "Detection state, timers, and session reset (equivalent to main.py 'R' key)"
            }
        }

    except Exception as e:
        logger.error(f"[Reset] Error resetting session {session_id}: {str(e)}")
        return {
            "status": "error",
            "detail": str(e)
        }