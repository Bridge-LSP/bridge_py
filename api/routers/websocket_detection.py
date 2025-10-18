from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import json
import numpy as np
import cv2
import base64
import time
import asyncio
from typing import Dict, Set
from api.dependencies import get_hand_landmarker, get_forest_model
from api.services.hand_detection import extract_features
import mediapipe as mp

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.landmarker = get_hand_landmarker()
        self.model = get_forest_model()
        print("🚀 WebSocket Manager inicializado con modelos cargados")
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"📱 Cliente {client_id} conectado. Total: {len(self.active_connections)}")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"❌ Cliente {client_id} desconectado. Total: {len(self.active_connections)}")
    
    async def process_frame_ultra_fast(self, websocket: WebSocket, frame_data: str):
        """Procesamiento ultra-optimizado para tiempo real conversacional"""
        try:
            start_time = time.time()
            
            # Decodificar imagen base64
            image_data = base64.b64decode(frame_data)
            np_arr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            if image is None:
                await websocket.send_text(json.dumps({"error": "Imagen inválida"}))
                return
            
            # Convertir a RGB para MediaPipe
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
            
            # Detección de manos ultra-rápida
            results = self.landmarker.detect(mp_image)
            
            response = {
                "predictions": [],
                "timestamp": time.time(),
                "processing_time_ms": 0
            }
            
            # Procesar landmarks si se detectan manos
            if results.hand_world_landmarks and results.handedness:
                for idx, landmarks in enumerate(results.hand_world_landmarks):
                    # Extracción rápida de características
                    features = extract_features(landmarks)
                    
                    # Predicción con Random Forest (ultra-rápido)
                    prediction = self.model.predict(features)[0]
                    probabilities = self.model.predict_proba(features)[0]
                    confidence = float(max(probabilities))
                    
                    # Solo enviar predicciones con alta confianza
                    if confidence > 0.75:
                        handedness = results.handedness[idx][0].category_name.lower()
                        
                        response["predictions"].append({
                            "letter": prediction,
                            "confidence": confidence,
                            "handedness": handedness,
                            "hand_index": idx
                        })
            
            # Calcular tiempo de procesamiento
            processing_time = (time.time() - start_time) * 1000
            response["processing_time_ms"] = round(processing_time, 2)
            
            # Enviar respuesta
            await websocket.send_text(json.dumps(response))
            
        except Exception as e:
            error_response = {
                "error": str(e),
                "timestamp": time.time()
            }
            await websocket.send_text(json.dumps(error_response))

# Manager global
manager = ConnectionManager()

@router.websocket("/ws/detection/{client_id}")
async def websocket_detection_endpoint(websocket: WebSocket, client_id: str):
    """Endpoint WebSocket para detección de señas en tiempo real"""
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Recibir frame como base64
            data = await websocket.receive_text()
            
            # Procesar inmediatamente
            await manager.process_frame_ultra_fast(websocket, data)
            
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        print(f"❌ Error en WebSocket {client_id}: {e}")
        manager.disconnect(client_id)

@router.get("/ws/status")
async def websocket_status():
    """Estado del servidor WebSocket"""
    return {
        "active_connections": len(manager.active_connections),
        "connected_clients": list(manager.active_connections.keys()),
        "status": "running"
    }