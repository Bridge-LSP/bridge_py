#!/usr/bin/env python3
"""
Test TTS functionality via WebSocket
"""

import asyncio
import websocket
import json
import base64
import time
from PIL import Image
import io

async def test_tts_functionality():
    """Test TTS audio generation via WebSocket"""
    
    def create_dummy_frame():
        """Create a simple dummy frame for testing"""
        # Create a simple black image
        img = Image.new('RGB', (640, 480), color='black')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        img_bytes = buffer.getvalue()
        return base64.b64encode(img_bytes).decode('utf-8')
    
    def on_message(ws, message):
        """Handle WebSocket messages"""
        try:
            data = json.loads(message)
            print(f"📨 Received: {data['type']}")
            
            if data['type'] == 'audio_ready' and 'audioBase64' in data:
                print(f"🔊 TTS AUDIO RECEIVED! Length: {len(data['audioBase64'])} chars")
                
                # Save audio for testing (optional)
                if data['audioBase64'].startswith('data:audio/wav;base64,'):
                    audio_data = data['audioBase64'].split(',')[1]
                    with open('test_tts_output.wav', 'wb') as f:
                        f.write(base64.b64decode(audio_data))
                    print("💾 Audio saved as 'test_tts_output.wav'")
                
                # Stop test after receiving audio
                print("✅ TTS test completed successfully!")
                ws.close()
                
            elif data['type'] == 'session_completed':
                print(f"🎯 Session completed: {data.get('finalText', 'N/A')}")
                
            elif data['type'] == 'debug_info':
                print(f"🔍 Debug: {data.get('message', 'N/A')}")
                
            else:
                print(f"ℹ️  Other message: {data}")
                
        except Exception as e:
            print(f"❌ Error processing message: {e}")
    
    def on_error(ws, error):
        print(f"❌ WebSocket error: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        print("🔌 WebSocket connection closed")
    
    def on_open(ws):
        print("✅ WebSocket connection opened")
        
        # Start session
        start_message = {
            "type": "start_session",
            "sessionId": "test_tts_session"
        }
        ws.send(json.dumps(start_message))
        print("🚀 Session started")
        
        # Send a few frames to simulate detection
        dummy_frame = create_dummy_frame()
        
        def send_frames():
            for i in range(30):  # Send 30 frames to simulate detection
                if ws.sock and ws.sock.connected:
                    frame_message = {
                        "type": "frame_data",
                        "frameBase64": dummy_frame,
                        "timestamp": int(time.time() * 1000)
                    }
                    ws.send(json.dumps(frame_message))
                    print(f"📷 Frame {i+1}/30 sent")
                    time.sleep(0.1)  # 10 FPS
                else:
                    break
            
            # After frames, wait for timeout to trigger sentence completion
            print("⏰ Waiting for sentence completion timeout (5 seconds)...")
        
        # Start sending frames in a separate thread
        import threading
        frame_thread = threading.Thread(target=send_frames)
        frame_thread.start()
    
    # Create WebSocket connection
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp(
        "ws://localhost:8000/ws/realtime",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    print("🔌 Connecting to WebSocket...")
    ws.run_forever()

if __name__ == "__main__":
    print("🧪 Testing TTS functionality via WebSocket")
    asyncio.run(test_tts_functionality())