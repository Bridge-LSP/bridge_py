import asyncio
import websockets
import json
import cv2
import base64
import time

class BridgeMobileClient:

    def __init__(self, server_url="ws://localhost:8765"):
        self.server_url = server_url
        self.client_id = f"mobile_{int(time.time())}"
        self.websocket = None
        self.is_connected = False
        self.stats = {
            'predictions_received': 0,
            'stable_predictions': 0,
            'avg_response_time': 0
        }

    async def connect(self):

        try:
            self.websocket = await websockets.connect(f"{self.server_url}/{self.client_id}")
            self.is_connected = True
            asyncio.create_task(self.listen_messages())
            return True
        except Exception:
            return False

    async def listen_messages(self):

        try:
            async for message in self.websocket:
                data = json.loads(message)
                await self.handle_server_message(data)
        except websockets.exceptions.ConnectionClosed:
            self.is_connected = False
        except Exception:
            self.is_connected = False

    async def handle_server_message(self, data):
        msg_type = data.get("type", "unknown")

        if msg_type == "prediction":
            self.stats['predictions_received'] += 1
            stable = data.get("stable_prediction")
            if stable:
                self.stats['stable_predictions'] += 1

    async def send_frame(self, frame):

        if not self.is_connected:
            return False

        try:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame_base64 = base64.b64encode(buffer).decode('utf-8')

            await self.websocket.send(frame_base64)
            return True

        except Exception:
            return False

    async def send_frame_json(self, frame, metadata=None):

        if not self.is_connected:
            return False

        try:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame_base64 = base64.b64encode(buffer).decode('utf-8')

            message = {
                "frame": frame_base64,
                "timestamp": time.time(),
                "client_id": self.client_id
            }

            if metadata:
                message.update(metadata)

            await self.websocket.send(json.dumps(message))
            return True

        except Exception:
            return False

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()
        self.is_connected = False

    def get_stats(self):

        return self.stats

async def demo_with_camera():
    client = BridgeMobileClient("ws://localhost:8765")

    if not await client.connect():
        return

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    try:
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % 3 == 0:
                await client.send_frame(frame)

            cv2.imshow("Bridge Mobile Client Demo", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            frame_count += 1

            await asyncio.sleep(0.033)

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(demo_with_camera())