from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import json
import numpy as np
import cv2
import base64
import time
import asyncio
import traceback
import logging
from typing import Dict, Set
from api.dependencies import get_hand_landmarker, get_forest_model
from api.services.hand_detection import extract_features
from api.services.frame_preprocessor import frame_preprocessor
import mediapipe as mp

router = APIRouter()
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.landmarker = get_hand_landmarker()
        self.rf_model = get_forest_model()
        print("[WebSocket] ConnectionManager initialized - RANDOM FOREST ONLY mode")

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def process_frame_ultra_fast(self, websocket: WebSocket, frame_data: str, client_id: str = "unknown"):
        """Process frame with comprehensive error handling and logging."""
        start_time = time.time()
        
        try:
            # Stage 1: Base64 decoding
            try:
                image_data = base64.b64decode(frame_data)
            except Exception as e:
                error_msg = f"Base64 decode failed: {str(e)}"
                logger.error(f"[{client_id}] {error_msg}")
                await websocket.send_text(json.dumps({
                    "error": "base64_decode_failed",
                    "details": error_msg,
                    "timestamp": time.time()
                }))
                return
            
            # Stage 2: Preprocessing (decode + flip/rotate)
            try:
                image = frame_preprocessor.decode_and_preprocess(image_data)
                
                if image is None:
                    error_msg = "Preprocessing returned None - check frame_preprocessor configuration"
                    logger.error(f"[{client_id}] {error_msg}")
                    await websocket.send_text(json.dumps({
                        "error": "preprocessing_failed",
                        "details": error_msg,
                        "preprocessing_config": frame_preprocessor.get_stats().get("configuration", {}),
                        "timestamp": time.time()
                    }))
                    return
                    
            except Exception as e:
                error_msg = f"Preprocessing exception: {str(e)}"
                logger.error(f"[{client_id}] {error_msg}")
                logger.error(f"[{client_id}] Traceback: {traceback.format_exc()}")
                await websocket.send_text(json.dumps({
                    "error": "preprocessing_exception",
                    "details": error_msg,
                    "timestamp": time.time()
                }))
                return

            # Stage 3: Convert to RGB and MediaPipe format
            try:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
            except Exception as e:
                error_msg = f"Image format conversion failed: {str(e)}"
                logger.error(f"[{client_id}] {error_msg}")
                await websocket.send_text(json.dumps({
                    "error": "image_conversion_failed",
                    "details": error_msg,
                    "timestamp": time.time()
                }))
                return

            # Stage 4: MediaPipe hand detection
            try:
                results = self.landmarker.detect(mp_image)
            except Exception as e:
                error_msg = f"MediaPipe detection failed: {str(e)}"
                logger.error(f"[{client_id}] {error_msg}")
                await websocket.send_text(json.dumps({
                    "error": "mediapipe_detection_failed",
                    "details": error_msg,
                    "timestamp": time.time()
                }))
                return

            # Stage 5: Random Forest prediction
            response = {
                "predictions": [],
                "timestamp": time.time(),
                "processing_time_ms": 0
            }

            if results.hand_world_landmarks and results.handedness:
                for idx, landmarks in enumerate(results.hand_world_landmarks):
                    try:
                        features = extract_features(landmarks)
                        prediction = self.rf_model.predict(features)[0]
                        probabilities = self.rf_model.predict_proba(features)[0]
                        confidence = float(max(probabilities))

                        if confidence > 0.75:
                            handedness = results.handedness[idx][0].category_name.lower()

                            response["predictions"].append({
                                "letter": prediction,
                                "confidence": confidence,
                                "handedness": handedness,
                                "hand_index": idx,
                                "model": "random_forest"
                            })
                    except Exception as e:
                        logger.error(f"[{client_id}] RF prediction error for hand {idx}: {str(e)}")
                        # Continue processing other hands

            processing_time = (time.time() - start_time) * 1000
            response["processing_time_ms"] = round(processing_time, 2)

            await websocket.send_text(json.dumps(response))

        except Exception as e:
            # Catch-all for unexpected errors
            error_msg = f"Unexpected error in frame processing: {str(e)}"
            logger.error(f"[{client_id}] {error_msg}")
            logger.error(f"[{client_id}] Full traceback:\n{traceback.format_exc()}")
            
            try:
                await websocket.send_text(json.dumps({
                    "error": "unexpected_error",
                    "details": error_msg,
                    "timestamp": time.time()
                }))
            except:
                # WebSocket might be closed
                logger.error(f"[{client_id}] Failed to send error response - connection may be closed")

manager = ConnectionManager()

@router.websocket("/ws/detection/{client_id}")
async def websocket_detection_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint with comprehensive error logging."""
    connection_start = time.time()
    logger.info(f"[{client_id}] WebSocket connection initiated")
    
    await manager.connect(websocket, client_id)
    logger.info(f"[{client_id}] WebSocket connection established")

    try:
        frame_count = 0
        while True:
            data = await websocket.receive_text()
            frame_count += 1
            await manager.process_frame_ultra_fast(websocket, data, client_id)

    except WebSocketDisconnect:
        connection_duration = time.time() - connection_start
        logger.info(f"[{client_id}] WebSocket disconnected normally | Duration: {connection_duration:.2f}s | Frames: {frame_count}")
        manager.disconnect(client_id)
        
    except Exception as e:
        connection_duration = time.time() - connection_start
        logger.error(f"[{client_id}] WebSocket error | Duration: {connection_duration:.2f}s | Frames: {frame_count}")
        logger.error(f"[{client_id}] Error: {str(e)}")
        logger.error(f"[{client_id}] Traceback:\n{traceback.format_exc()}")
        manager.disconnect(client_id)

@router.get("/ws/status")
async def websocket_status():

    return {
        "active_connections": len(manager.active_connections),
        "connected_clients": list(manager.active_connections.keys()),
        "status": "running"
    }