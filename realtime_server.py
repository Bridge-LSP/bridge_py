import asyncio
import websockets
import json
import numpy as np
import cv2
import base64
import joblib
import time
import argparse
from engine_bridge.hand_tracker import create_hand_landmarker
from api.services.hand_detection import extract_features
import mediapipe as mp

class UltraFastRealtimeServer:
    def __init__(self):
        print("🚀 Iniciando servidor WebSocket ultra-rápido...")
        self.landmarker = create_hand_landmarker()
        self.model = joblib.load('models/forest_model_u.pkl')
        self.clients = set()
        self.processed_frames = 0
        self.start_time = time.time()
        print("✅ Modelos cargados - Servidor listo")

    async def register_client(self, websocket):
        self.clients.add(websocket)
        print(f"📱 Cliente conectado. Total activos: {len(self.clients)}")

    async def unregister_client(self, websocket):
        self.clients.discard(websocket)
        print(f"❌ Cliente desconectado. Total activos: {len(self.clients)}")

    async def process_detection_ultra_fast(self, websocket, path):

        await self.register_client(websocket)

        try:
            async for message in websocket:
                frame_start = time.time()

                try:
                    frame_data = base64.b64decode(message)
                    np_arr = np.frombuffer(frame_data, np.uint8)
                    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                    if image is None:
                        continue

                    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

                    results = self.landmarker.detect(mp_image)

                    response = {
                        "predictions": [],
                        "server_timestamp": time.time(),
                        "frame_id": self.processed_frames
                    }

                    if results.hand_world_landmarks:
                        for idx, landmarks in enumerate(results.hand_world_landmarks):
                            features = extract_features(landmarks)
                            prediction = self.model.predict(features)[0]
                            confidence = float(max(self.model.predict_proba(features)[0]))

                            if confidence > 0.8:
                                response["predictions"].append({
                                    "letter": prediction,
                                    "confidence": confidence,
                                    "handedness": results.handedness[idx][0].category_name.lower()
                                })

                    processing_time = (time.time() - frame_start) * 1000
                    response["processing_time_ms"] = round(processing_time, 2)

                    self.processed_frames += 1
                    if self.processed_frames % 100 == 0:
                        uptime = time.time() - self.start_time
                        fps = self.processed_frames / uptime
                        print(f"📊 Frames procesados: {self.processed_frames} | FPS promedio: {fps:.1f}")

                    await websocket.send(json.dumps(response))

                except Exception as e:
                    error_response = {
                        "error": f"Error procesando frame: {str(e)}",
                        "timestamp": time.time()
                    }
                    await websocket.send(json.dumps(error_response))

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"❌ Error en conexión: {e}")
        finally:
            await self.unregister_client(websocket)

server_instance = UltraFastRealtimeServer()

async def main():
    parser = argparse.ArgumentParser(description='Servidor WebSocket ultra-rápido para Bridge')
    parser.add_argument('--host', default='localhost', help='Host del servidor')
    parser.add_argument('--port', type=int, default=8765, help='Puerto del servidor')
    args = parser.parse_args()

    print(f"🌐 Iniciando servidor en ws://{args.host}:{args.port}")
    print("🚀 Optimizado para LSP conversacional - Latencia < 50ms")

    start_server = websockets.serve(
        server_instance.process_detection_ultra_fast,
        args.host,
        args.port,
        max_size=10**7,
        ping_interval=20,
        ping_timeout=10
    )

    await start_server
    print(f"✅ Servidor activo y esperando conexiones...")

    await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido por usuario")
    except Exception as e:
        print(f"❌ Error fatal del servidor: {e}")