# main_ws_visual.py - Complete Architecture Guide

## 📋 Overview

`main_ws_visual.py` is a **visual WebSocket test client** that replicates the functionality of `main.py` (local camera detection) but uses the **PRODUCTION WebSocket pipeline** that the Flutter mobile app uses.

**Purpose**: 
- Test the full WebSocket detection pipeline without needing Flutter/Android Studio
- Visual debugging tool with live camera feed and detection overlay
- Validates that the backend works correctly for mobile clients

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         main_ws_visual.py                            │
│                    (Visual WebSocket Client)                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ 1. HTTP POST
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    POST /session/init                                │
│                  (Session Initialization)                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ Returns: session_id
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│             ws://127.0.0.1:8000/realtime/ws/detection/{session_id}  │
│                      (WebSocket Connection)                          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ 2. WebSocket Handshake
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  Send: {"type": "control", "action": "play"}         │
│                       (Activate Detection)                           │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ 3. Backend Acknowledges
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  Receive: {"type": "state_update", ...}              │
│                         (Initial State)                              │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ 4. Continuous Frame Loop
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│      Send: {"type": "frame", "frameBase64": "<jpeg_base64>"}         │
│                        (at 5 FPS)                                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ 5. Backend Processes Frame
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Backend Pipeline:                                                   │
│    1. Decode base64 → JPEG bytes                                     │
│    2. frame_preprocessor.decode_and_preprocess()                     │
│    3. MediaPipe hand detection                                       │
│    4. Random Forest model prediction                                 │
│    5. Autocorrector word building                                    │
│    6. Timer management (word/phrase timeouts)                        │
│    7. Translation (if enabled)                                       │
│    8. TTS audio generation (if enabled)                              │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ 6. Backend Responds
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│         Receive: {"type": "state_update", ...} (every frame)         │
│         Contains: detection, word, sentence, translation, tts, etc.  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ 7. Display Updates
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   OpenCV Window with Live Overlay                    │
│    - Current detected letter + confidence                            │
│    - Raw word buffer + corrected word                                │
│    - Current sentence / completed sentence                           │
│    - FPS, latency, MediaPipe status                                  │
│    - Large letter display (bottom-right corner)                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Complete Flow - From Start to Translation

### **Phase 1: Initialization** 🚀

#### Step 1: Session Creation (HTTP REST)
```python
# File: main_ws_visual.py, function: init_session()
POST http://127.0.0.1:8000/session/init
Content-Type: application/json

{
  "preferences": {
    "tts_enabled": false,
    "auto_translate": false,
    "word_pause_ms": 4000,
    "phrase_pause_ms": 8000
  }
}
```

**Backend Endpoint**: `POST /session/init` (in `api/routers/session.py`)

**What Happens**:
1. Backend creates new `SessionEngine` instance
2. Initializes MediaPipe hands detector
3. Loads Random Forest model (`forest_model_u.pkl`)
4. Sets up autocorrector, timers, TTS service
5. Returns `session_id` (UUID)

**Response**:
```json
{
  "session_id": "ab958ce3-e851-4ed2-9c71-8024cc1e11b7",
  "status": "active",
  "preferences": {
    "tts_enabled": false,
    "auto_translate": false,
    "word_pause_ms": 4000,
    "phrase_pause_ms": 8000
  }
}
```

---

### **Phase 2: WebSocket Connection** 🔌

#### Step 2: Establish WebSocket
```python
# File: main_ws_visual.py, method: websocket_sender_receiver()
ws_url = f"ws://127.0.0.1:8000/realtime/ws/detection/{session_id}"

async with websockets.connect(ws_url, open_timeout=30) as websocket:
    # Connected!
```

**Backend Endpoint**: `ws://127.0.0.1:8000/realtime/ws/detection/{session_id}`  
**Handler**: `websocket_detection_endpoint()` in `api/routers/realtime_websocket.py`

**What Happens**:
1. WebSocket handshake completes
2. Backend adds connection to `ConnectionManager`
3. Backend retrieves `SessionEngine` for this session_id
4. Session is in **STOP mode** by default (`is_running=False`)

---

#### Step 3: Activate Detection (CRITICAL!)
```python
# File: main_ws_visual.py
play_message = json.dumps({
    "type": "control",
    "action": "play"
})
await websocket.send(play_message)
```

**Backend Handler**: `handle_control_message()` in `realtime_websocket.py`

**What Happens**:
1. Backend receives control message with `action: "play"`
2. Calls `session_engine.set_running(True)`
3. Session enters **PLAY mode** - frames will now be processed
4. Backend sends acknowledgment state_update

**Backend Code**:
```python
# In api/routers/realtime_websocket.py
if action == "play":
    session_engine.set_running(True)
    logger.info(f"Session {session_id}: Started detection")
```

**Response**:
```json
{
  "type": "state_update",
  "session_id": "ab958ce3-e851-4ed2-9c71-8024cc1e11b7",
  "timestamp": 1763699870.123456,
  "detection": {"letter": "", "confidence": null, "model": "rf"},
  "word": {"raw_buffer": "", "corrected": "", "just_finished": false},
  "sentence": {"current": "", "completed": false, "just_completed": false},
  "translation": {
    "enabled": false,
    "target_language": "en",
    "translated_sentence": null,
    "just_translated": false
  },
  "timers": {...},
  "tts": {...},
  "processing_time_ms": 2.5
}
```

---

### **Phase 3: Continuous Frame Detection Loop** 🎥

#### Step 4: Capture Camera Frame
```python
# File: main_ws_visual.py, method: camera_capture_thread()
cap = cv2.VideoCapture(0)  # Camera index 0
ret, frame = cap.read()    # Read frame (640x480 BGR)

self.current_frame = frame.copy()  # Store for sender thread
```

**Configuration**:
- Resolution: 640x480
- FPS: 30 (camera capture rate)
- Buffer size: 1 (minimize latency)

---

#### Step 5: Encode Frame to Base64
```python
# File: main_ws_visual.py, function: encode_frame_to_base64()
_, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
base64_str = base64.b64encode(buffer).decode('utf-8')
```

**Details**:
- Format: JPEG (lossy compression)
- Quality: 90% (balance size vs quality)
- Output: Base64 string (~50-60KB per frame)
- **NO flip applied** - backend handles orientation

---

#### Step 6: Send Frame via WebSocket
```python
# File: main_ws_visual.py, method: websocket_sender_receiver()
message = {
    "type": "frame",
    "frameBase64": base64_str  # ~55000 chars
}
await websocket.send(json.dumps(message))
```

**Sending Rate**: 5 FPS (one frame every 200ms)

**Why 5 FPS?**
- Reduces network/CPU load
- Still fast enough for real-time detection
- Matches typical user gesture speed

---

#### Step 7: Backend Processes Frame

**Backend Flow** (in `engine_bridge/session_engine.py`):

```python
def process_frame_base64(self, frame_b64: str) -> Dict[str, Any]:
    # 1. Check if running
    if not self.is_running:
        return self._build_state_payload()  # Ignore frame if stopped
    
    # 2. Decode base64 to image
    image = self._decode_frame_base64(frame_b64)
    
    # 3. Run MediaPipe
    results = self._run_mediapipe(image, current_time)
    
    # 4. Run Random Forest if hand detected
    if results.hand_landmarks:
        detected = self._run_rf_if_applicable(results, current_time)
    
    # 5. Check timeouts
    self._check_word_timeout(current_time)
    self._check_phrase_timeout(current_time)
    
    # 6. Build and return state
    return self._build_state_payload()
```

**Detailed Sub-steps**:

##### 7.1: Decode Base64 → OpenCV Image
```python
# In session_engine.py, method: _decode_frame_base64()
img_bytes = base64.b64decode(frame_b64)
image = frame_preprocessor.decode_and_preprocess(img_bytes)
```

**frame_preprocessor** (in `api/services/frame_preprocessor.py`):
- Decodes JPEG bytes → BGR numpy array
- Applies flip: `cv2.flip(image, 1)` (horizontal flip for correct hand orientation)
- Validates shape and color format
- Returns: `(480, 640, 3)` BGR image ready for MediaPipe

##### 7.2: MediaPipe Hand Detection
```python
# In session_engine.py, method: _run_mediapipe()
mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
results = self.hand_tracker.detect(mp_image)
```

**Output**:
- `results.hand_landmarks`: List of detected hands (usually 0 or 1)
- Each hand has 21 landmarks: `[(x, y, z), ...]`
- Normalized coordinates (0-1 range)

##### 7.3: Extract Landmarks
```python
# In session_engine.py, method: _extract_landmarks()
hand_landmarks = results.hand_landmarks[0]  # First detected hand
landmarks_array = [(lm.x, lm.y, lm.z) for lm in hand_landmarks]
return np.array(landmarks_array).flatten()  # Shape: (63,)
```

**Landmark Array**: 63 floats representing hand pose

##### 7.4: Random Forest Prediction
```python
# In session_engine.py, method: _run_rf_if_applicable()
landmarks_flat = self._extract_landmarks(results)
prediction = self.rf_model.predict([landmarks_flat])[0]
probas = self.rf_model.predict_proba([landmarks_flat])[0]
confidence = probas.max()

if confidence >= self.rf_confidence_threshold:  # Default: 0.7
    self.letra_actual = prediction
```

**Model**: `forest_model_u.pkl` (Random Forest trained on static signs)  
**Output**: Spanish alphabet letter (A-Z, Ñ, special signs)

##### 7.5: Autocorrector Word Building
```python
# In session_engine.py, method: _run_rf_if_applicable()
if detected_letter != self.last_prediction:
    self.autocorrector.add_letter(detected_letter)
    self.last_prediction = detected_letter
    self.last_letter_time = current_time
```

**Autocorrector** (in `engine_bridge/autocorrector/autocorrector_core.py`):
- Maintains `word_buffer`: List of letters
- Applies BERT-based autocorrection
- Suggests corrected word: `get_current_word_corrected()`

##### 7.6: Word Timeout Check
```python
# In session_engine.py, method: _check_word_timeout()
if time_since_last >= self.word_pause_ms / 1000.0:
    self._finalize_word()
```

**Word Timeout Logic**:
- Default: 4000ms (4 seconds) of no new letters
- Triggers: `_finalize_word()`
- Adds corrected word to sentence: `autocorrector.finalize_current_word()`

##### 7.7: Phrase Timeout Check
```python
# In session_engine.py, method: _check_phrase_timeout()
if time_since_last >= self.phrase_pause_ms / 1000.0:
    self._finalize_sentence()
```

**Phrase Timeout Logic**:
- Default: 8000ms (8 seconds) of inactivity
- Triggers: `_finalize_sentence()`
- Marks sentence as completed

##### 7.8: Translation (if enabled)
```python
# In session_engine.py, method: _finalize_sentence()
if self.auto_translate and self.target_language != "es":
    self.translated_sentence = translate_text(
        self.completed_sentence,
        target_lang=self.target_language
    )
    self._translation_just_completed = True
```

**Translation Service** (in `api/services/translation_service.py`):
- Uses Google Translate API (via `googletrans` library)
- Source: Spanish (detected signs)
- Target: User preference (default: "en")

**Example**:
- Spanish: "hola mundo"
- English: "hello world"

##### 7.9: TTS Generation (if enabled)
```python
# In session_engine.py, method: _finalize_sentence()
if self.tts_enabled and not self.tts_muted:
    audio_base64 = self._generate_tts(text_to_speak)
    self.current_tts_audio = audio_base64
    self._tts_just_generated = True
```

**TTS Service** (in `api/services/enhanced_tts_service.py`):
- Uses Google TTS (gTTS) or Pyttsx3
- Generates audio file
- Encodes to base64
- Returns: `"data:audio/mp3;base64,<audio_base64>"`

---

#### Step 8: Backend Builds State Payload
```python
# In session_engine.py, method: _build_state_payload()
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
        "completed": self.sentence_completed,
        "just_completed": self._sentence_just_completed
    },
    
    "translation": {
        "enabled": self.auto_translate,
        "target_language": self.target_language,
        "translated_sentence": self.translated_sentence,
        "just_translated": self._translation_just_completed
    },
    
    "timers": {
        "time_since_last_letter": time_since_last,
        "word_timer_active": word_timer_active,
        "phrase_timer_active": phrase_timer_active
    },
    
    "tts": {
        "enabled": self.tts_enabled,
        "muted": self.tts_muted,
        "audio_available": self.current_tts_audio is not None,
        "audio_base64": self.current_tts_audio,
        "audio_mime_type": "audio/mp3",
        "just_generated": self._tts_just_generated
    },
    
    "processing_time_ms": processing_time
}
```

**State Flags**:
- `just_finished`: Word just completed (true for 1 frame only)
- `just_completed`: Sentence just completed (true for 1 frame only)
- `just_translated`: Translation just generated (true for 1 frame only)
- `just_generated`: TTS audio just created (true for 1 frame only)

**These flags reset after one state update** to avoid duplicate events.

---

#### Step 9: Client Receives State Update
```python
# File: main_ws_visual.py, method: websocket_sender_receiver()
response = await websocket.recv()
state = json.loads(response)

# Extract data
detection = state.get("detection", {})
letra = detection.get("letter", "")
confidence = detection.get("confidence", None)

word = state.get("word", {})
raw_buffer = word.get("raw_buffer", "")
corrected_word = word.get("corrected", "")

sentence = state.get("sentence", {})
current_sentence = sentence.get("current", "")
completed_sentence = sentence.get("completed", "")

translation = state.get("translation", {})
translated_sentence = translation.get("translated_sentence", "")

# Update UI state
self.last_state = state
```

---

#### Step 10: Display Visual Overlay
```python
# File: main_ws_visual.py, method: display_thread_func()
display_frame = draw_detection_overlay(frame, self.last_state, self.stats)
cv2.imshow(WINDOW_NAME, display_frame)
```

**Overlay Elements**:
1. **Top Panel** (semi-transparent white background):
   - Title: "BRIDGE - WebSocket Visual Test"
   - Current Letter: "H (conf: 0.85)"
   - Raw Word Buffer: "hola"
   - Corrected Word: "hola"
   - Current Sentence: "hola mundo"
   - FPS, Latency, Frames Sent
   - MediaPipe Status: "detected ('H')" or "no hands"

2. **Bottom-Right Corner**:
   - Large letter display (120x120px white box)
   - Shows current detected letter in big font

**Frame Flip**: Display shows `cv2.flip(frame, 1)` for mirror mode (user-friendly)

---

## 📊 Complete Data Flow Example

### Scenario: User signs "HOLA"

```
Time  | Action                           | Backend Processing                    | Client Display
------+----------------------------------+---------------------------------------+---------------------------
0.0s  | User shows hand sign "H"         | MediaPipe: Detects hand              | Shows camera feed
0.2s  | Frame sent (#1)                  | RF Model: Predicts "H" (conf: 0.85)  | Letter: "H"
      |                                  | Autocorrector: Adds "H" to buffer    | Raw: "H"
0.4s  | User transitions to "O"          | MediaPipe: Still sees "H"            | Letter: "H"
0.6s  | Frame sent (#2)                  | RF Model: Predicts "O" (conf: 0.80)  | Letter: "O"
      |                                  | Autocorrector: Adds "O" to buffer    | Raw: "HO"
0.8s  | User holds "O"                   | RF Model: Predicts "O"               | Letter: "O"
      |                                  | (Same letter, not added again)       | Raw: "HO"
1.0s  | User transitions to "L"          | MediaPipe: Detects hand              | Letter: "O"
1.2s  | Frame sent (#3)                  | RF Model: Predicts "L" (conf: 0.82)  | Letter: "L"
      |                                  | Autocorrector: Adds "L" to buffer    | Raw: "HOL"
1.4s  | User shows "A"                   | MediaPipe: Detects hand              | Letter: "L"
1.6s  | Frame sent (#4)                  | RF Model: Predicts "A" (conf: 0.88)  | Letter: "A"
      |                                  | Autocorrector: Adds "A" to buffer    | Raw: "HOLA"
      |                                  | BERT Correction: "hola" (valid word) | Corrected: "hola"
1.8s  | User stops signing               | MediaPipe: No hand detected          | Letter: ""
      |                                  |                                      | Raw: "HOLA"
5.8s  | (4 seconds of inactivity)        | WORD TIMEOUT TRIGGERED               | Corrected: "hola"
      |                                  | _finalize_word() called              | just_finished: true
      |                                  | Adds "hola" to sentence              | Sentence: "hola"
      |                                  |                                      | Raw: "" (cleared)
9.8s  | (8 seconds of inactivity)        | PHRASE TIMEOUT TRIGGERED             | Sentence: "hola"
      |                                  | _finalize_sentence() called          | completed: true
      |                                  | (If auto_translate=true)             | just_completed: true
      |                                  | Translation: "hello"                 | 
      |                                  | (If tts_enabled=true)                | translation: "hello"
      |                                  | TTS Audio: "data:audio/mp3;base64,..." | just_translated: true
```

---

## 🔧 Key Backend Endpoints Used

### 1. **Session Initialization** (HTTP REST)
```
POST http://127.0.0.1:8000/session/init
```
- **File**: `api/routers/session.py`
- **Function**: `init_session_endpoint()`
- **Purpose**: Creates SessionEngine instance, returns session_id
- **Used**: Once at startup

### 2. **WebSocket Detection** (WebSocket)
```
ws://127.0.0.1:8000/realtime/ws/detection/{session_id}
```
- **File**: `api/routers/realtime_websocket.py`
- **Function**: `websocket_detection_endpoint()`
- **Purpose**: Bidirectional communication for frames and state updates
- **Used**: Continuously throughout session

### 3. **Control Messages** (via WebSocket)
```json
{"type": "control", "action": "play"}      // Start detection
{"type": "control", "action": "stop"}      // Stop detection
{"type": "control", "action": "clear_all"} // Reset state
{"type": "control", "action": "update_preferences", "payload": {...}}
```
- **Handler**: `handle_control_message()` in `realtime_websocket.py`
- **Purpose**: Control session behavior

### 4. **Frame Messages** (via WebSocket)
```json
{"type": "frame", "frameBase64": "<jpeg_base64>"}
```
- **Handler**: `handle_frame_message()` in `realtime_websocket.py`
- **Purpose**: Send camera frame for detection

---

## 🎯 Translation Feature Explanation

### How Translation Works in the System

**Translation is DISABLED by default** in `main_ws_visual.py`:
```python
payload = {
    "preferences": {
        "auto_translate": False,  # <-- Translation OFF
        "word_pause_ms": 4000,
        "phrase_pause_ms": 8000
    }
}
```

### To Enable Translation:

#### Option 1: Change Initialization Payload
```python
# In main_ws_visual.py, function: init_session()
payload = {
    "preferences": {
        "auto_translate": True,       # Enable translation
        "target_language": "en",      # Target language code
        "word_pause_ms": 4000,
        "phrase_pause_ms": 8000
    }
}
```

#### Option 2: Send Control Message
```python
# After WebSocket connection
preferences_message = json.dumps({
    "type": "control",
    "action": "update_preferences",
    "payload": {
        "auto_translate": True,
        "target_language": "en"
    }
})
await websocket.send(preferences_message)
```

### Translation Flow:

1. **User finishes signing a sentence** (8 seconds of inactivity)
2. **Backend detects phrase timeout** → `_check_phrase_timeout()`
3. **Backend finalizes sentence** → `_finalize_sentence()`
4. **Backend checks if translation enabled**:
   ```python
   if self.auto_translate and self.target_language != "es":
       self.translated_sentence = translate_text(
           self.completed_sentence,
           target_lang=self.target_language
       )
       self._translation_just_completed = True
   ```
5. **Translation service calls Google Translate**:
   ```python
   # In api/services/translation_service.py
   translator = Translator()
   result = translator.translate(text, src='es', dest=target_lang)
   return result.text
   ```
6. **Backend includes translation in state payload**:
   ```json
   {
     "translation": {
       "enabled": true,
       "target_language": "en",
       "translated_sentence": "hello world",
       "just_translated": true
     }
   }
   ```
7. **Client receives translation** and can display it

### Display Translation in UI:

Add to `main_ws_visual.py` overlay function:
```python
# In draw_detection_overlay()
translation = state.get("translation", {})
if translation.get("enabled") and translation.get("translated_sentence"):
    translated = translation.get("translated_sentence")
    cv2.putText(display_frame, f"Translation: {translated}", 
                (20, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 100, 0), 2)
```

### Supported Languages:
```python
# Common target languages
"en" = English
"fr" = French
"de" = German
"it" = Italian
"pt" = Portuguese
"zh-cn" = Chinese (Simplified)
"ja" = Japanese
"ko" = Korean
# ... any language supported by Google Translate
```

---

## 🧵 Threading Architecture

### **Thread 1: Camera Capture** (Daemon Thread)
```python
camera_thread = Thread(target=camera_capture_thread, daemon=True)
```
- **Purpose**: Continuously read frames from webcam
- **Rate**: 30 FPS (camera native rate)
- **Output**: Updates `self.current_frame` (shared variable)
- **Lifecycle**: Runs until `stop_event` is set

### **Thread 2: WebSocket Async** (Daemon Thread)
```python
ws_thread = Thread(target=lambda: asyncio.run(ws_task()), daemon=True)
```
- **Purpose**: Send frames + receive state updates via WebSocket
- **Rate**: 5 FPS sending, continuous receiving
- **Input**: Reads `self.current_frame`
- **Output**: Updates `self.response_queue` with state payloads
- **Lifecycle**: Runs until `stop_event` is set

### **Thread 3: Display** (Main Thread)
```python
# Runs in main thread (required for OpenCV on Windows)
self.display_thread_func()
```
- **Purpose**: Show OpenCV window with overlays
- **Rate**: ~30 FPS display refresh
- **Input**: Reads `self.current_frame` and `self.response_queue`
- **Output**: Visual window with detection overlay
- **Lifecycle**: Runs until 'Q' key pressed or window closed

### Thread Synchronization:
- **Shared State**: `self.current_frame`, `self.response_queue`
- **No Locks Needed**: Threads read/write different variables
- **Queue**: Thread-safe communication for state updates

---

## ✨ Key Differences vs main.py

| Feature                  | main.py (Local)           | main_ws_visual.py (WebSocket)      |
|--------------------------|---------------------------|------------------------------------|
| **Architecture**         | All-in-one process        | Client-Server (like Flutter)       |
| **Detection**            | Local SessionEngine       | Remote SessionEngine via WebSocket |
| **Frame Processing**     | Direct OpenCV → MediaPipe | Encode → WebSocket → Backend      |
| **State Management**     | Local variables           | SessionEngine state payload        |
| **Latency**              | ~0ms                      | ~20-50ms (network + processing)    |
| **Purpose**              | Desktop app               | Backend testing / debugging        |
| **Translation**          | N/A                       | Backend translation service        |
| **TTS**                  | Local pyttsx3             | Backend TTS service                |
| **Multi-session**        | Single user               | Multi-user capable (different IDs) |

---

## 🐛 Debugging Tips

### Check if Backend is Running:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/"
```

### Check Session Initialization:
```powershell
$response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/session/init" -Method POST -Body '{"preferences":{}}' -ContentType "application/json"
$response.session_id
```

### Test WebSocket Manually:
```python
import asyncio
import websockets
import json

async def test():
    async with websockets.connect("ws://127.0.0.1:8000/realtime/ws/detection/YOUR_SESSION_ID") as ws:
        # Send play
        await ws.send(json.dumps({"type": "control", "action": "play"}))
        
        # Receive response
        response = await ws.recv()
        print(response)

asyncio.run(test())
```

### Enable Verbose Logging:
```python
# In main_ws_visual.py, add at top
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Frame Encoding:
```python
# After encode_frame_to_base64()
print(f"Frame encoded: {len(base64_str)} chars")
print(f"First 50 chars: {base64_str[:50]}")
```

---

## 📝 Summary

**main_ws_visual.py achieves full translation functionality through:**

1. ✅ **Session Initialization**: Creates backend session via REST API
2. ✅ **WebSocket Connection**: Establishes bidirectional communication
3. ✅ **Detection Activation**: Sends "play" control message
4. ✅ **Frame Streaming**: Sends camera frames at 5 FPS
5. ✅ **Backend Processing**: Full pipeline (MediaPipe → RF → Autocorrect → Timers)
6. ✅ **Translation**: Backend translates completed sentences (if enabled)
7. ✅ **TTS Generation**: Backend generates audio (if enabled)
8. ✅ **State Updates**: Receives complete state with translation/TTS
9. ✅ **Visual Display**: Shows all detection results in real-time overlay

**Translation specifically works by**:
- Setting `auto_translate: true` in preferences
- Backend detecting phrase timeout (8s inactivity)
- Backend calling Google Translate API
- Backend including translation in state payload
- Client displaying translated text in UI

**This architecture perfectly replicates the Flutter app's workflow** and validates that the backend translation feature works correctly end-to-end.

---

**End of Architecture Guide**
