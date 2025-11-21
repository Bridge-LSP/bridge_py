"""
main_ws_visual.py - Visual WebSocket Test Client (Production Pipeline)

This script replicates main.py's visual interface but uses the PRODUCTION
SessionEngine WebSocket pipeline that Flutter uses.

CRITICAL FIX: This version ACTUALLY SENDS frames to the backend via WebSocket.
"""

import asyncio
import websockets
import json
import base64
import cv2
import time
import requests
import numpy as np
from threading import Thread, Event
from queue import Queue, Empty
import sys
from engine_bridge.text_to_speech import bridge_tts

BACKEND_BASE_URL = "http://127.0.0.1:8000"
SESSION_INIT_ENDPOINT = f"{BACKEND_BASE_URL}/session/init"
FPS_TARGET = 5  
CAMERA_INDEX = 0
WINDOW_NAME = "Bridge WebSocket Visual Test (Press Q to quit)"

TTS_ENABLED = True
TTS_AUTO_PLAY = True


def init_session() -> str:
    """Initialize session via REST API and return session_id."""
    try:
        print("\n🔄 Initializing session with backend...")
        
        payload = {
            "preferences": {
                "tts_enabled": True,  # Enable TTS
                "auto_translate": False,
                "word_pause_ms": 4000,
                "phrase_pause_ms": 8000
            }
        }
        
        response = requests.post(SESSION_INIT_ENDPOINT, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        session_id = data.get("session_id")
        
        if not session_id:
            raise ValueError("No session_id in response")
        
        print(f"✅ Session initialized: {session_id}")
        print(f"   Preferences: {data.get('preferences', {})}")
        
        return session_id
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to initialize session: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error during session init: {e}")
        sys.exit(1)


def encode_frame_to_base64(frame: np.ndarray) -> str:
    """Encode OpenCV frame to base64 JPEG (mimics Flutter)."""
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    base64_str = base64.b64encode(buffer).decode('utf-8')
    return base64_str

def create_websocket_message(frame_base64: str) -> str:
    """Create WebSocket message in SessionEngine format."""
    message = {
        "type": "frame",
        "frameBase64": frame_base64
    }
    return json.dumps(message)


def draw_detection_overlay(frame: np.ndarray, state: dict, stats: dict) -> np.ndarray:
    """
    Draw detection information overlay on frame (similar to main.py interface).
    
    Args:
        frame: BGR image from camera
        state: SessionEngine state payload from WebSocket
        stats: Local statistics (FPS, latency, etc.)
    
    Returns:
        Frame with overlay drawn
    """
    display_frame = frame.copy()
    height, width = display_frame.shape[:2]
    
    # Extract state information (new format with nested structure)
    detection = state.get("detection", {})
    word = state.get("word", {})
    sentence = state.get("sentence", {})
    events = state.get("events", {})
    
    letra_actual = detection.get("letter", "")
    confidence = detection.get("confidence", None)
    raw_buffer = word.get("raw_buffer", [])
    corrected_word = word.get("corrected", "")
    current_sentence = sentence.get("current", "")
    completed_sentence = sentence.get("completed", "")
    sentence_completed = events.get("sentence_completed", False)
    
    # Build display strings
    word_buffer = ''.join(raw_buffer) if raw_buffer else ""
    
    # Semi-transparent info panel at top
    panel_height = 240
    overlay = display_frame.copy()
    cv2.rectangle(overlay, (10, 10), (width - 10, panel_height), (250, 250, 250), -1)
    cv2.addWeighted(overlay, 0.7, display_frame, 0.3, 0, display_frame)
    cv2.rectangle(display_frame, (10, 10), (width - 10, panel_height), (80, 80, 80), 3)
    
    # Title
    cv2.putText(display_frame, "BRIDGE - WebSocket Visual Test (Production Pipeline)", 
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (50, 50, 50), 2)
    
    # Detection info with confidence
    letter_text = f"Current Letter: {letra_actual if letra_actual else 'None'}"
    if confidence is not None:
        letter_text += f" (conf: {confidence:.2f})"
    cv2.putText(display_frame, letter_text, 
                (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 100, 200), 2)
    
    # Word building
    raw_display = f"Raw: {word_buffer if word_buffer else '(empty)'}"
    cv2.putText(display_frame, raw_display, 
                (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 120, 120), 1)
    
    corrected_display = f"Corrected: {corrected_word if corrected_word else '(none)'}"
    cv2.putText(display_frame, corrected_display, 
                (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 140, 0), 1)
    
    # Sentence
    if sentence_completed and completed_sentence:
        cv2.putText(display_frame, f"Sentence: {completed_sentence}", 
                    (20, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 150, 0), 2)
    else:
        sentence_display = current_sentence if current_sentence else "(no sentence yet)"
        cv2.putText(display_frame, f"Sentence: {sentence_display}", 
                    (20, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 50, 200), 1)
    
    # Stats (FPS, latency, etc.)
    fps = stats.get("fps", 0)
    latency = stats.get("latency_ms", 0)
    frames_sent = stats.get("frames_sent", 0)
    mp_status = stats.get("mp_status", "unknown")
    
    stats_text = f"FPS: {fps:.1f} | Latency: {latency:.0f}ms | Frames: {frames_sent}"
    cv2.putText(display_frame, stats_text, 
                (20, 195), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
    
    # MediaPipe status
    mp_color = (0, 200, 0) if "hand" in mp_status.lower() else (0, 0, 200)
    cv2.putText(display_frame, f"MediaPipe: {mp_status}", 
                (20, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.5, mp_color, 1)
    
    # Large letter display in bottom-right corner (like main.py)
    if letra_actual:
        letter_size = 120
        letter_x = width - letter_size - 20
        letter_y = height - letter_size - 20
        
        # Shadow
        cv2.rectangle(display_frame, (letter_x + 5, letter_y + 5), 
                     (letter_x + letter_size + 5, letter_y + letter_size + 5), 
                     (100, 100, 100), -1)
        # Background
        cv2.rectangle(display_frame, (letter_x, letter_y), 
                     (letter_x + letter_size, letter_y + letter_size), 
                     (255, 255, 255), -1)
        # Border
        cv2.rectangle(display_frame, (letter_x, letter_y), 
                     (letter_x + letter_size, letter_y + letter_size), 
                     (0, 0, 0), 3)
        # Letter
        cv2.putText(display_frame, letra_actual, 
                   (letter_x + 25, letter_y + 85), 
                   cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 0, 0), 4)
    
    return display_frame

# ============================================================================
# WEBSOCKET CLIENT WITH VISUAL DISPLAY
# ============================================================================

class VisualWebSocketClient:
    """WebSocket client with live visual display (like main.py)."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.ws_url = f"ws://127.0.0.1:8000/realtime/ws/detection/{session_id}"
        
        # State
        self.running = True
        self.last_state = {}
        self.stats = {
            "fps": 0,
            "latency_ms": 0,
            "frames_sent": 0,
            "mp_status": "waiting..."
        }
        
        # Shared frame buffer
        self.current_frame = None
        self.frame_lock = Event()
        
        # Response queue
        self.response_queue = Queue(maxsize=10)
        self.stop_event = Event()
        
        # TTS tracking (to avoid playing same sentence multiple times)
        self.last_completed_sentence = ""
        self.last_tts_time = 0
        
        print(f"🎯 Session ID: {session_id}")
        print(f"🔗 WebSocket URL: {self.ws_url}")
    
    def _handle_tts_for_completed_sentence(self, state: dict):
        """
        Handle TTS playback when sentence is completed (replicates main.py behavior).
        
        Args:
            state: SessionEngine state payload from WebSocket
        """
        if not TTS_ENABLED or not TTS_AUTO_PLAY:
            return
        
        # Check if sentence was just completed
        sentence_data = state.get("sentence", {})
        just_completed = sentence_data.get("just_completed", False)
        
        if not just_completed:
            return
        
        # Get the completed sentence (it's the string value, not nested)
        completed_sentence = sentence_data.get("completed", "")
        
        # Handle if it's a boolean (should be string after backend fix)
        if isinstance(completed_sentence, bool):
            print(f"⚠️  Warning: sentence.completed is boolean ({completed_sentence}), expected string")
            return
        
        if not completed_sentence or not completed_sentence.strip():
            return
        
        # Avoid playing the same sentence multiple times
        current_time = time.time()
        if (completed_sentence == self.last_completed_sentence and 
            current_time - self.last_tts_time < 2.0):  # 2 second cooldown
            return
        
        # Update tracking
        self.last_completed_sentence = completed_sentence
        self.last_tts_time = current_time
        
        # Play TTS (like main.py does)
        print(f"\n🔊 Playing TTS for completed sentence: '{completed_sentence}'")
        try:
            # Check if there's a translation
            translation_data = state.get("translation", {})
            translated_text = translation_data.get("text", "")
            target_lang = translation_data.get("target_lang", "")
            
            if translated_text and target_lang:
                # Play translated version
                print(f"   🌍 Translation: '{translated_text}' ({target_lang})")
                bridge_tts.speak_sentence_completion(translated_text, target_lang)
            else:
                # Play original Spanish version
                bridge_tts.speak_sentence_completion(completed_sentence, 'es')
            
            print("   ✅ TTS playback initiated")
            
        except Exception as e:
            print(f"   ⚠️  TTS error: {e}")
    
    def camera_capture_thread(self):
        """Capture frames from camera continuously."""
        print("\n📷 Opening camera...")
        cap = cv2.VideoCapture(CAMERA_INDEX)
        
        if not cap.isOpened():
            print("❌ Failed to open camera")
            self.stop_event.set()
            return
        
        # Configure camera (match main.py)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        print("✅ Camera opened successfully")
        
        frame_count = 0
        while not self.stop_event.is_set():
            ret, frame = cap.read()
            
            if ret and frame is not None:
                # Store current frame (will be read by display and sender threads)
                self.current_frame = frame.copy()
                frame_count += 1
            
            time.sleep(0.01)  # Small sleep to avoid busy-wait
        
        cap.release()
        print(f"📷 Camera released (captured {frame_count} frames)")
    
    async def websocket_sender_receiver(self):
        """Send frames and receive responses via WebSocket (async)."""
        try:
            # Increase timeout for WebSocket handshake (default is 10s)
            async with websockets.connect(
                self.ws_url,
                open_timeout=30,  # 30 seconds for handshake
                close_timeout=10,
                ping_interval=20,
                ping_timeout=20
            ) as websocket:
                print("✅ WebSocket connected\n")
                
                # 🎯 CRITICAL: Send "play" control message to activate detection
                play_message = json.dumps({
                    "type": "control",
                    "action": "play"
                })
                await websocket.send(play_message)
                print("▶️  Sent PLAY control message - detection activated\n")
                
                # Wait for acknowledgment
                ack_response = await websocket.recv()
                print(f"✅ Received acknowledgment: {ack_response[:100]}...\n")
                
                print("📤 Starting to send frames...\n")
                
                frame_interval = 1.0 / FPS_TARGET
                last_send_time = time.time()
                send_times = {}
                frame_id = 0
                
                while not self.stop_event.is_set():
                    current_time = time.time()
                    
                    # Send frame at target FPS
                    if (current_time - last_send_time) >= frame_interval:
                        if self.current_frame is not None:
                            try:
                                # Encode frame (NO flip here - backend handles it)
                                frame_base64 = encode_frame_to_base64(self.current_frame)
                                message = create_websocket_message(frame_base64)
                                
                                # Send via WebSocket
                                send_time = time.time()
                                
                                # 🔥 DIAGNOSTIC: Print message structure before sending
                                if self.stats["frames_sent"] == 0:
                                    parsed = json.loads(message)
                                    print(f"🔥 FIRST MESSAGE STRUCTURE:")
                                    print(f"   type: {parsed.get('type')}")
                                    print(f"   has frameBase64: {'frameBase64' in parsed}")
                                    print(f"   frameBase64 length: {len(parsed.get('frameBase64', ''))} chars")
                                
                                await websocket.send(message)
                                
                                send_times[frame_id] = send_time
                                self.stats["frames_sent"] += 1
                                
                                # Print every 10 frames
                                if self.stats["frames_sent"] % 10 == 0:
                                    print(f"📤 Sent frame #{self.stats['frames_sent']} (base64 size: {len(frame_base64)} chars)")
                                
                                frame_id += 1
                                last_send_time = current_time
                                
                                # Clean old send times
                                if len(send_times) > 100:
                                    old_ids = sorted(send_times.keys())[:-100]
                                    for old_id in old_ids:
                                        del send_times[old_id]
                                
                            except Exception as e:
                                print(f"⚠️  Error encoding/sending frame: {e}")
                    
                    # Receive responses (non-blocking)
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=0.01)  # Increased timeout
                        receive_time = time.time()
                        
                        # 🔥 DIAGNOSTIC: Print RAW response (first 200 chars)
                        print(f"📥 RAW RESPONSE: {response[:200]}...")
                        
                        # Calculate latency
                        if send_times:
                            latest_send_time = max(send_times.values())
                            latency_ms = (receive_time - latest_send_time) * 1000
                            self.stats["latency_ms"] = latency_ms
                        
                        # Parse response
                        state = json.loads(response)
                        
                        # 🔥 DIAGNOSTIC: Print ALL top-level keys
                        print(f"📋 Response keys: {list(state.keys())}")
                        
                        # Update MediaPipe status for overlay
                        detection = state.get("detection", {})
                        word = state.get("word", {})
                        sentence = state.get("sentence", {})
                        
                        letra = detection.get("letter", "")
                        confidence = detection.get("confidence", None)
                        raw_buffer = word.get("raw_buffer", [])
                        corrected_word = word.get("corrected", "")
                        current_sentence = sentence.get("current", "")
                        
                        if letra:
                            self.stats["mp_status"] = f"detected ('{letra}')"
                            print(f"✅ LETTER DETECTED: '{letra}' (conf: {confidence})")
                        elif raw_buffer:
                            self.stats["mp_status"] = "building word..."
                        else:
                            self.stats["mp_status"] = "no hands"
                        
                        # Print diagnostic info ALWAYS (not just when active)
                        sentence_just_completed = sentence.get("just_completed", False)
                        sentence_completed_text = sentence.get("completed", "")
                        
                        print(f"📨 WS State Update:")
                        print(f"   detection.letter: '{letra}' | confidence: {confidence}")
                        print(f"   word.raw_buffer: {raw_buffer} | corrected: '{corrected_word}'")
                        print(f"   sentence.current: '{current_sentence}'")
                        print(f"   sentence.just_completed: {sentence_just_completed} | completed: '{sentence_completed_text}'")
                        print(f"   mp_status: {self.stats['mp_status']}")
                        print()  # Blank line for readability
                        
                        # Store for overlay
                        if not self.response_queue.full():
                            self.response_queue.put(state)
                        
                        # 🔊 TTS: Play audio when sentence is completed (like main.py)
                        self._handle_tts_for_completed_sentence(state)
                        
                    except asyncio.TimeoutError:
                        pass  # No response yet
                    except json.JSONDecodeError as e:
                        print(f"⚠️  JSON decode error: {e}")
                    except Exception as e:
                        print(f"⚠️  Error receiving: {e}")
                    
                    # Small async sleep
                    await asyncio.sleep(0.001)
                
        except websockets.exceptions.WebSocketException as e:
            print(f"\n❌ WebSocket error: {e}")
            self.stop_event.set()
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.stop_event.set()
    
    def display_thread_func(self):
        """Display window with overlays (runs in main thread for OpenCV compatibility)."""
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 1000, 700)
        
        fps_tracker = []
        
        print(f"🖥️  Display window opened")
        print(f"   Press Q to quit\n")
        
        while not self.stop_event.is_set():
            # Get current frame
            if self.current_frame is not None:
                frame = self.current_frame.copy()
                
                # Flip for display (mirror mode like main.py)
                frame = cv2.flip(frame, 1)
                
                # Get latest state
                while not self.response_queue.empty():
                    try:
                        self.last_state = self.response_queue.get_nowait()
                    except Empty:
                        break
                
                # Calculate FPS
                current_time = time.time()
                fps_tracker.append(current_time)
                fps_tracker = [t for t in fps_tracker if current_time - t < 1.0]
                self.stats["fps"] = len(fps_tracker)
                
                # Draw overlay
                display_frame = draw_detection_overlay(frame, self.last_state, self.stats)
                
                # Show frame
                cv2.imshow(WINDOW_NAME, display_frame)
            
            # Check for quit key
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q'):
                print("\n🛑 Quit key pressed")
                self.stop_event.set()
                break
        
        cv2.destroyAllWindows()
        
        # Stop TTS playback if active (like main.py)
        if TTS_ENABLED:
            try:
                bridge_tts.stop_current_audio()
                print("🔇 TTS audio stopped")
            except Exception as e:
                pass
        
        print("🖥️  Display window closed")
    
    def run(self):
        """Run the visual WebSocket client."""
        try:
            # Start camera capture thread
            camera_thread = Thread(target=self.camera_capture_thread, daemon=True)
            camera_thread.start()
            
            # Wait for camera to initialize
            time.sleep(1)
            
            # Start WebSocket communication (async)
            async def ws_task():
                await self.websocket_sender_receiver()
            
            ws_thread = Thread(target=lambda: asyncio.run(ws_task()), daemon=True)
            ws_thread.start()
            
            # Run display in main thread (required for OpenCV on Windows)
            self.display_thread_func()
            
            # Wait for threads to finish
            print("\n⏳ Waiting for background threads...")
            camera_thread.join(timeout=2)
            ws_thread.join(timeout=2)
            
            print("\n📊 SUMMARY:")
            print(f"   Total frames sent: {self.stats['frames_sent']}")
            print(f"   Final FPS: {self.stats['fps']:.1f}")
            print(f"   Final latency: {self.stats['latency_ms']:.0f}ms")
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            self.stop_event.set()
        except Exception as e:
            print(f"\n❌ Error in main loop: {e}")
            import traceback
            traceback.print_exc()
            self.stop_event.set()
        finally:
            # Ensure TTS is stopped on exit (like main.py)
            if TTS_ENABLED:
                try:
                    bridge_tts.stop_current_audio()
                except Exception:
                    pass

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    print("=" * 70)
    print("BRIDGE - Visual WebSocket Test Client (Production Pipeline)")
    print("=" * 70)
    print()
    print("This client uses the EXACT SAME WebSocket endpoints as Flutter:")
    print("  1. POST /session/init → Initialize session")
    print("  2. ws:///realtime/ws/detection/{session_id} → Send frames")
    print("  3. Receive SessionEngine state payloads")
    print()
    print("Use this to diagnose detection issues without Flutter/Android Studio.")
    print()
    
    # Initialize session
    session_id = init_session()
    
    # Create and run client
    client = VisualWebSocketClient(session_id)
    client.run()
    
    print("\n✅ Client shutdown complete")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
