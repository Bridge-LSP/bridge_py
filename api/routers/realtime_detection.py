from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Header
from pydantic import BaseModel
import json
import numpy as np
import cv2
import base64
import time
import asyncio
import uuid
import io
import logging
from typing import Dict, Optional
from api.dependencies import get_hand_landmarker, get_forest_model
from api.services.hand_detection import extract_features
from engine_bridge.text_to_speech import bridge_tts
import mediapipe as mp

CONFIDENCE_THRESHOLD = 0.70
FRAME_MIN_INTERVAL_MS = 200
MAX_INFLIGHT_FRAMES = 1
PHRASE_IDLE_SECONDS = 5
WS_MAX_MESSAGE_BYTES = 10_485_760
HEARTBEAT_INTERVAL_SECONDS = 10
HEARTBEAT_TIMEOUT_SECONDS = 20

router = APIRouter()
logger = logging.getLogger(__name__)

SESSIONS = {}
PREFS = {}
WS_CONNECTIONS = {}

class SessionState:
    def __init__(self):
        self.letters_buffer = []
        self.current_word = ""
        self.sentence_words = []
        self.sentence_so_far = ""
        self.last_activity = time.time()
        self.is_building_word = False

    def has_words(self):
        return len(self.sentence_words) > 0 or self.current_word != ""

    def reset_for_new_sentence(self):
        self.letters_buffer = []
        self.current_word = ""
        self.sentence_words = []
        self.sentence_so_far = ""
        self.is_building_word = False

class UserPreferences:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.tts_enabled = True
        self.voice_language = "es"
        self.auto_translate = False
        self.client_token: Optional[str] = None

class SessionCreateRequest(BaseModel):
    session_id: Optional[str] = None

class DetectRequest(BaseModel):
    frameBase64: str
    clientId: str

class ConnectionManager:
    def __init__(self):
        self.landmarker = get_hand_landmarker()
        self.model = get_forest_model()
        logger.info("🚀 Hardened WebSocket Manager initialized")

manager = ConnectionManager()

async def heartbeat_monitor(websocket: WebSocket, client_id: str):

    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)

            await websocket.send_json({"type": "ping"})
            logger.debug(f"[WS] ping sent to {client_id}")

            if client_id in WS_CONNECTIONS:
                WS_CONNECTIONS[client_id]["last_ping"] = time.time()

            if client_id in WS_CONNECTIONS:
                conn_info = WS_CONNECTIONS[client_id]
                last_pong = conn_info.get("last_pong", time.time())
                if time.time() - last_pong > HEARTBEAT_TIMEOUT_SECONDS:
                    logger.warning(f"[WS] client {client_id} inactive >{HEARTBEAT_TIMEOUT_SECONDS}s — closing connection")
                    await websocket.close(code=1001, reason="Heartbeat timeout")
                    break

    except asyncio.CancelledError:
        logger.debug(f"[WS] heartbeat monitor cancelled for {client_id}")
    except Exception as e:
        logger.error(f"[WS] heartbeat monitor error for {client_id}: {e}")

def handle_pong_message(client_id: str):

    if client_id in WS_CONNECTIONS:
        WS_CONNECTIONS[client_id]["last_pong"] = time.time()
        logger.debug(f"[WS] pong received from {client_id}")

def cleanup_connection(client_id: str):

    if client_id in WS_CONNECTIONS:
        conn_info = WS_CONNECTIONS[client_id]
        if "heartbeat_task" in conn_info and conn_info["heartbeat_task"]:
            conn_info["heartbeat_task"].cancel()
        del WS_CONNECTIONS[client_id]
        logger.info(f"[WS] connection cleaned up for {client_id}")

@router.post("/session/create")
async def create_session(
    req: SessionCreateRequest,
    x_client_token: Optional[str] = Header(None)
):

    try:
        sid = req.session_id or str(uuid.uuid4())
        if sid not in SESSIONS:
            SESSIONS[sid] = SessionState()
            PREFS[sid] = UserPreferences(sid)

            if x_client_token:
                PREFS[sid].client_token = x_client_token

            logger.info(f"[Bridge] Session created: {sid}")

        return {
            "status": "success",
            "data": {
                "message": "Session created successfully",
                "session_id": sid
            }
        }
    except Exception as e:
        logger.error(f"[Bridge] Error creating session: {e}")
        return {
            "status": "error",
            "detail": str(e)
        }

@router.websocket("/ws/echo")
async def echo_ws(websocket: WebSocket):

    await websocket.accept()
    print("[WS/echo] Connected")
    try:
        while True:
            msg = await websocket.receive_text()
            print(f"[WS/echo] Received text len={len(msg)}")
            await websocket.send_text(f"echo:{len(msg)}")
    except WebSocketDisconnect:
        print("[WS/echo] Disconnected")
    except Exception as e:
        print(f"[WS/echo] Error: {e}")

@router.post("/detect")
async def detect_fallback(req: DetectRequest):

    try:
        t0 = time.time()
        img_bytes = base64.b64decode(req.frameBase64, validate=True)
        logger.debug(f"[HTTP/detect] Frame bytes={len(img_bytes)}")

        image = decode_image(img_bytes)
        if image is None:
            return {
                "status": "error",
                "detail": "Invalid image format"
            }

        pred = run_mediapipe_and_get_top_prediction(image)
        latency_ms = int((time.time() - t0) * 1000)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[HTTP/detect] Latency={latency_ms}ms")

        if not pred or pred["confidence"] < CONFIDENCE_THRESHOLD:
            return {
                "status": "success",
                "data": {
                    "predictions": [],
                    "latency_ms": latency_ms
                }
            }

        return {
            "status": "success",
            "data": {
                "predictions": [pred],
                "latency_ms": latency_ms
            }
        }

    except Exception as e:
        logger.error(f"[HTTP/detect] Error: {e}")
        return {
            "status": "error",
            "detail": str(e)
        }

@router.websocket("/ws/detection/{client_id}")
async def detection_ws(websocket: WebSocket, client_id: str):

    await websocket.accept()
    logger.info(f"[WS/detection] Connected: {client_id}")

    WS_CONNECTIONS[client_id] = {
        "websocket": websocket,
        "last_pong": time.time(),
        "last_ping": time.time()
    }

    session_id = map_client_to_session(client_id)
    if session_id not in SESSIONS:
        SESSIONS[session_id] = SessionState()
        PREFS[session_id] = UserPreferences(session_id)

    inflight = 0
    last_ts_ms = 0
    lock = asyncio.Lock()

    async def dec_inflight():
        nonlocal inflight
        async with lock:
            inflight = max(0, inflight - 1)

    heartbeat_task = asyncio.create_task(heartbeat_monitor(websocket, client_id))
    WS_CONNECTIONS[client_id]["heartbeat_task"] = heartbeat_task

    idle_task = asyncio.create_task(_phrase_idle_watchdog(websocket, session_id))

    try:
        while True:
            msg = await websocket.receive()

            if msg.get("type") == "websocket.receive" and "text" in msg:
                raw = msg["text"]

                try:
                    json_msg = json.loads(raw)
                    if json_msg.get("type") == "pong":
                        handle_pong_message(client_id)
                        continue
                    elif json_msg.get("type") == "frame":
                        b64 = json_msg.get("data", "")
                    else:
                        continue
                except json.JSONDecodeError:
                    b64 = raw

            elif msg.get("type") == "websocket.receive" and "bytes" in msg:
                b64 = base64.b64encode(msg["bytes"]).decode("ascii")
            else:
                continue

            if not b64:
                continue

            now = int(time.time() * 1000)
            if now - last_ts_ms < FRAME_MIN_INTERVAL_MS:
                continue

            async with lock:
                if inflight >= MAX_INFLIGHT_FRAMES:
                    continue
                inflight += 1

            last_ts_ms = now

            asyncio.create_task(_process_frame_and_emit(websocket, session_id, b64, dec_inflight))

    except WebSocketDisconnect:
        logger.info(f"[WS/detection] Disconnected: {client_id}")
    except Exception as e:
        logger.error(f"[WS/detection] Error for {client_id}: {e}")
        await _safe_send_json(websocket, {"type": "error", "message": str(e)})
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
        if idle_task:
            idle_task.cancel()
        cleanup_connection(client_id)

def map_client_to_session(client_id: str) -> str:

    return client_id

def extract_base64_from_message(raw: str) -> str:

    if not raw:
        return ""

    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if obj.get("type") == "frame":
                return obj.get("data", "")
            return ""
        except:
            pass

    return raw

def decode_image(img_bytes: bytes):

    try:
        np_arr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return image
    except Exception:
        return None

def run_mediapipe_and_get_top_prediction(image):

    try:
        if image is None:
            return None

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

        results = manager.landmarker.detect(mp_image)

        if results.hand_world_landmarks and results.handedness:
            landmarks = results.hand_world_landmarks[0]
            features = extract_features(landmarks)

            prediction = manager.model.predict(features)[0]
            probabilities = manager.model.predict_proba(features)[0]
            confidence = float(max(probabilities))

            return {
                "letter": prediction,
                "confidence": confidence
            }

        return None

    except Exception as e:
        print(f"[mediapipe] Error: {e}")
        return None

def update_word_buffers(session_id: str, letter: str):

    session = SESSIONS[session_id]

    session.letters_buffer.append(letter)
    session.current_word = "".join(session.letters_buffer)
    session.is_building_word = True

    word_finalized = False
    if len(session.letters_buffer) >= 4:
        word_finalized = True
        session.sentence_words.append(session.current_word)
        session.sentence_so_far = " ".join(session.sentence_words)
        session.letters_buffer = []
        session.current_word = ""
        session.is_building_word = False

    return True, word_finalized

def bert_correct(word: str, context: str) -> str:

    return word

def complete_phrase(session_id: str) -> str:

    session = SESSIONS[session_id]

    if session.is_building_word and session.current_word:
        session.sentence_words.append(session.current_word)
        session.current_word = ""
        session.is_building_word = False

    phrase = " ".join(session.sentence_words)
    return phrase

def generate_tts(text: str, language: str) -> str:

    try:
        return ""
    except Exception as e:
        print(f"[TTS] Error: {e}")
        return ""

async def _process_frame_and_emit(ws: WebSocket, session_id: str, b64: str, done_cb):

    t0 = time.time()
    frame_id = int(t0 * 1000) % 100000

    try:
        img_bytes = base64.b64decode(b64, validate=True)
        logger.debug(f"[WS/process] Frame {frame_id} bytes={len(img_bytes)}")

        image = decode_image(img_bytes)
        if image is None:
            await _safe_send_json(ws, {"type": "error", "message": "Imagen inválida"})
            return

        pred = run_mediapipe_and_get_top_prediction(image)

        if pred and pred["confidence"] >= CONFIDENCE_THRESHOLD:
            letter = pred["letter"]
            SESSIONS[session_id].last_activity = time.time()

            from api.services.timer_manager_service import timer_manager_service

            result = timer_manager_service.autocorrector_service.add_letter(session_id, letter)
            if "error" not in result:
                timer_manager_service.reset_timers(session_id)
                timer_manager_service.start_word_timer(session_id)

                await _safe_send_json(ws, {
                    "type": "letter_added",
                    "letter": letter.upper(),
                    "confidence": pred["confidence"],
                    "word_timer_started": True
                })

                await _safe_send_json(ws, {
                    "type": "word_updated",
                    "word": result["current_buffer"].upper()
                })

                latency_ms = int((time.time() - t0) * 1000)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"[Detect] Frame {frame_id} | latency={latency_ms}ms | confidence={pred['confidence']:.2f} | letter={letter.upper()}")
        else:
            latency_ms = int((time.time() - t0) * 1000)
            if logger.isEnabledFor(logging.DEBUG):
                confidence = pred['confidence'] if pred else None
                logger.debug(f"[Detect] Frame {frame_id} | latency={latency_ms}ms | no detection (conf: {confidence})")

    except Exception as e:
        logger.error(f"[WS/process] Frame {frame_id} error: {e}")
        await _safe_send_json(ws, {"type": "error", "message": str(e)})
    finally:
        await done_cb()

async def _phrase_idle_watchdog(ws: WebSocket, session_id: str):

    while True:
        try:
            await asyncio.sleep(1)

            if session_id not in SESSIONS:
                continue

            session = SESSIONS[session_id]
            idle_time = time.time() - session.last_activity

            if idle_time >= PHRASE_IDLE_SECONDS and session.has_words():
                phrase_start_time = time.time()

                phrase = complete_phrase(session_id)
                if phrase.strip():
                    await _safe_send_json(ws, {
                        "type": "phrase_updated",
                        "phrase": phrase
                    })

                    completion_time = time.time() - phrase_start_time
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f'[Phrase] Auto-finished in {idle_time:.1f}s | phrase="{phrase}" | processing={completion_time*1000:.0f}ms')

                    prefs = PREFS.get(session_id, UserPreferences(session_id))
                    if prefs.tts_enabled:
                        tts_b64 = generate_tts(phrase, prefs.voice_language)
                        if tts_b64:
                            await _safe_send_json(ws, {
                                "type": "tts_ready",
                                "audioBase64": tts_b64,
                                "lang": prefs.voice_language
                            })

                    session.reset_for_new_sentence()

        except asyncio.CancelledError:
            logger.debug(f"[WS/idle] Watchdog cancelled for session {session_id}")
            break
        except Exception as e:
            logger.error(f"[WS/idle] Watchdog error for {session_id}: {e}")

async def _safe_send_json(ws: WebSocket, payload: dict):

    try:
        await ws.send_json(payload)
    except Exception as e:
        print(f"[WS/send] Error: {e}")

@router.get("/ws/status")
async def ws_status():

    return {
        "status": "success",
        "data": {
            "active_sessions": len(SESSIONS),
            "session_ids": list(SESSIONS.keys()),
            "active_websockets": len(WS_CONNECTIONS),
            "websocket_clients": list(WS_CONNECTIONS.keys()),
            "status": "running",
            "heartbeat_config": {
                "interval_seconds": HEARTBEAT_INTERVAL_SECONDS,
                "timeout_seconds": HEARTBEAT_TIMEOUT_SECONDS
            }
        }
    }