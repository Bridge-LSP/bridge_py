"""
WebSocket endpoint for real-time LSP detection using SessionEngine.

This module implements the main real-time interface for the frontend,
handling frame processing and control messages through a unified protocol.
"""

import json
import logging
import asyncio
import time
import cv2
import numpy as np
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from engine_bridge.session_manager import get_session_manager

router = APIRouter()
logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """Manages active WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session: {session_id}")
    
    def disconnect(self, session_id: str):
        """Remove WebSocket connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected for session: {session_id}")
    
    async def send_state_update(self, session_id: str, state_data: Dict[str, Any]):
        """Send state update to specific session."""
        if session_id in self.active_connections:
            try:
                json_data = json.dumps(state_data)
                await self.active_connections[session_id].send_text(json_data)
                print(f"📤 [WS] Sent state update | session: {session_id[:8]}... | letter: {state_data.get('detection', {}).get('letter', 'N/A')}")
            except Exception as e:
                logger.error(f"Error sending state update to {session_id}: {e}")
                print(f"❌ [WS] Failed to send state update: {e}")
                self.disconnect(session_id)
        else:
            print(f"⚠️  [WS] Cannot send state - session not in active_connections: {session_id[:8]}...")
    
    def get_connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.active_connections)


connection_manager = WebSocketConnectionManager()


@router.websocket("/ws/detection/{session_id}")
async def websocket_detection_endpoint(websocket: WebSocket, session_id: str):
    """
    Main WebSocket endpoint for real-time LSP detection.
    
    Handles:
    - Frame messages with base64-encoded images
    - Control messages (play/stop/preferences/clear)
    - State updates back to frontend
    """
    
    print(f"🔥 [WS] Connection attempt for session: {session_id}")
    logger.info(f"WebSocket connection attempt for session: {session_id}")
    
    from engine_bridge.bert_model_loader import is_loading
    if is_loading():
        logger.warning(f"BERT models still loading, accepting connection with limited autocorrection")
    
    await connection_manager.connect(websocket, session_id)
    print(f"✅ [WS] Connection accepted for session: {session_id}")
    session_manager = get_session_manager()
    
    session_engine = session_manager.get_or_create_session(session_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                print(f"🔥 [WS] Message received | type: {message_type} | session: {session_id[:8]}...")
                
                if message_type == "frame":
                    print(f"🔥 [WS] Processing FRAME message")
                    await handle_frame_message(session_id, message, session_engine)
                    
                elif message_type == "control":
                    await handle_control_message(session_id, message, session_engine)
                    
                else:
                    logger.warning(f"Unknown message type from {session_id}: {message_type}")
                    
            except json.JSONDecodeError:
                await handle_legacy_frame(session_id, data, session_engine)
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
        connection_manager.disconnect(session_id)
        session_engine.set_running(False)
        
    except Exception as e:
        logger.error(f"WebSocket error for {session_id}: {e}")
        connection_manager.disconnect(session_id)


async def handle_frame_message(session_id: str, message: Dict[str, Any], session_engine) -> None:
    """Handle frame processing message."""
    try:
        frame_base64 = message.get("frameBase64")
        # Optimización 1: Validar frameBase64 antes de procesamiento
        if not frame_base64 or not frame_base64.startswith("data:image"):
            logger.warning(f"Frame message from {session_id} invalid frameBase64 (empty or wrong format)")
            return
        
        print(f"🔥 [ROUTER] Received frame for session {session_id[:8]}... | base64 length: {len(frame_base64)}")
        
        start_time = time.time()
        
        state_data = session_engine.process_frame_base64(frame_base64)
        
        processing_time_ms = (time.time() - start_time) * 1000
        state_data["processing_time_ms"] = round(processing_time_ms, 2)
        
        await connection_manager.send_state_update(session_id, state_data)
        
        if processing_time_ms > 100:
            logger.warning(f"Slow frame processing for {session_id}: {processing_time_ms:.1f}ms")
            
    except Exception as e:
        logger.error(f"Error handling frame message for {session_id}: {e}")


async def handle_control_message(session_id: str, message: Dict[str, Any], session_engine) -> None:
    """Handle control message (play/stop/preferences/clear)."""
    try:
        action = message.get("action")
        payload = message.get("payload", {})
        
        if action == "play":
            session_engine.set_running(True)
            logger.info(f"Session {session_id}: Started detection")
            
        elif action == "stop":
            session_engine.set_running(False)
            logger.info(f"Session {session_id}: Stopped detection")
            
            # Limpieza del debug frame al detener la detección
            try:
                import os
                import numpy as np
                debug_frame_path = "debug_ws_frame.jpg"
                if os.path.exists(debug_frame_path):
                    # Crear un frame vacío (negro) para sobrescribir
                    empty_frame = np.zeros((720, 480, 3), dtype=np.uint8)
                    cv2.imwrite(debug_frame_path, empty_frame)
                    logger.info(f"🧹 Debug frame cleaned (overwritten with empty frame) for session {session_id}")
            except Exception as e:
                logger.warning(f"Failed to clean debug frame: {e} (non-critical)")
            
        elif action == "update_preferences":
            session_engine.update_preferences(payload)
            logger.info(f"Session {session_id}: Updated preferences")
            
        elif action == "clear_all":
            session_engine.clear_all()
            logger.info(f"Session {session_id}: Cleared all state")
            
        else:
            logger.warning(f"Unknown control action from {session_id}: {action}")
            return
        
        state_data = session_engine._build_state_payload()
        await connection_manager.send_state_update(session_id, state_data)
        
    except Exception as e:
        logger.error(f"Error handling control message for {session_id}: {e}")


async def handle_legacy_frame(session_id: str, frame_data: str, session_engine) -> None:
    """Handle legacy frame message (raw base64 without JSON wrapper)."""
    try:
        start_time = time.time()
        
        state_data = session_engine.process_frame_base64(frame_data)
        
        processing_time_ms = (time.time() - start_time) * 1000
        state_data["processing_time_ms"] = round(processing_time_ms, 2)
        
        await connection_manager.send_state_update(session_id, state_data)
        
    except Exception as e:
        logger.error(f"Error handling legacy frame for {session_id}: {e}")


@router.get("/ws/status")
async def websocket_status():
    """Get WebSocket status and active connections."""
    session_manager = get_session_manager()
    
    return {
        "status": "running",
        "active_connections": connection_manager.get_connection_count(),
        "active_sessions": session_manager.get_session_count(),
        "session_info": session_manager.get_session_info()
    }


@router.post("/ws/broadcast")
async def broadcast_message(message: Dict[str, Any]):
    """Broadcast a message to all connected WebSocket clients (admin/debug)."""
    try:
        for session_id, websocket in connection_manager.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to {session_id}: {e}")
        
        return {
            "status": "success", 
            "sent_to": len(connection_manager.active_connections),
            "message": message
        }
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        return {"status": "error", "detail": str(e)}


@router.post("/ws/cleanup")
async def cleanup_inactive_sessions():
    """Manually trigger cleanup of inactive sessions."""
    session_manager = get_session_manager()
    cleaned_count = session_manager.cleanup_inactive_sessions()
    
    return {
        "status": "success",
        "cleaned_sessions": cleaned_count,
        "remaining_sessions": session_manager.get_session_count()
    }