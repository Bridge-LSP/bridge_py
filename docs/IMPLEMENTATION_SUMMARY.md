# WebSocket Detection Pipeline - Diagnostic System Implementation

## Summary of Changes

This document describes all modifications made to implement comprehensive diagnostics and prepare the WebSocket detection pipeline for debugging and fixing.

## Files Modified

### 1. engine_bridge/session_engine.py

**Purpose:** Add deep diagnostic logging to track frame processing through the entire pipeline.

**Changes:**

#### A. Frame Decoding Diagnostics (_decode_frame_base64)
```python
# After successful decode, save frame and log pixel statistics
cv2.imwrite("debug_ws_frame.jpg", image)
print(f"[DEBUG][WS] Saved frame to debug_ws_frame.jpg | shape={image.shape}, dtype={image.dtype}")
print(f"[DEBUG][WS] Pixel stats: min={image.min()}, max={image.max()}, mean={image.mean():.2f}")
```

**What this reveals:**
- Frame successfully decoded? (debug_ws_frame.jpg exists)
- Correct dimensions? (should be ~480x640x3 for camera)
- Valid pixel range? (0-255 for uint8)
- Frame quality? (mean brightness, contrast check)

#### B. MediaPipe Detection Diagnostics (_run_mediapipe)
```python
print(f"[DEBUG][MP] Input frame shape for MediaPipe: {image.shape}, dtype={image.dtype}")

results = self.hand_landmarker.detect_for_video(mp_image, timestamp)

if results and results.handedness:
    print(f"[DEBUG][MP] MediaPipe detected {len(results.handedness)} hand(s)")
    for idx, handedness in enumerate(results.handedness):
        category = handedness[0].category_name
        score = handedness[0].score
        print(f"[DEBUG][MP]   Hand {idx}: {category} ({score:.3f})")
else:
    print("[DEBUG][MP] MediaPipe detected NO HANDS")
```

**What this reveals:**
- MediaPipe receiving correct frame format?
- Hands detected or not? ✅ vs ❌
- Which hand? (Left/Right)
- Detection confidence score (0.0-1.0)

#### C. Random Forest Diagnostics (_run_rf_if_applicable)
```python
flattened = features.flatten() if hasattr(features, 'flatten') else features
print(f"[DEBUG][RF] Input vector length: {len(flattened)}")
first_10 = flattened[:10].tolist() if hasattr(flattened, 'tolist') else list(flattened[:10])
print(f"[DEBUG][RF] First 10 values: {first_10}")

prediction = self.rf_model.predict(features)[0]
print(f"[DEBUG][RF] Prediction: {prediction}")
```

**What this reveals:**
- Feature vector correct length? (should be 63 for hand landmarks)
- Feature values in valid range? (normalized coordinates)
- RF model producing predictions?
- Predicted letter matches hand sign?

---

### 2. main_ws_visual.py

**Purpose:** Enhanced visual client with better diagnostics and proper display mirroring.

**Changes:**

#### A. WebSocket Message Logging (websocket_communication)
```python
# Parse and extract detailed state
detection = state.get("detection", {})
word = state.get("word", {})
sentence = state.get("sentence", {})

letra = detection.get("letter", "")
confidence = detection.get("confidence", None)
raw_buffer = word.get("raw_buffer", [])
corrected_word = word.get("corrected", "")
current_sentence = sentence.get("current", "")

# Update MediaPipe status for overlay
if letra:
    self.stats["mp_status"] = f"detected ('{letra}')"
elif raw_buffer:
    self.stats["mp_status"] = "building word..."
else:
    self.stats["mp_status"] = "no hands"

# Print detailed diagnostic info (only when active)
if letra or raw_buffer:
    print(f"📨 WS State Update:")
    print(f"   detection.letter: '{letra}' | confidence: {confidence}")
    print(f"   word.raw_buffer: {raw_buffer} | corrected: '{corrected_word}'")
    print(f"   sentence.current: '{current_sentence}'")
```

**What this reveals:**
- Backend sending valid state updates?
- Letters being detected? (detection.letter non-empty)
- Confidence scores? (should be >0.7 for good detections)
- Word building working? (raw_buffer accumulating)
- Sentence formation working?

#### B. Enhanced Visual Overlay (draw_detection_overlay)
```python
# Expanded panel with more info
panel_height = 240  # Increased from 200

# Detection with confidence
letter_text = f"Current Letter: {letra_actual if letra_actual else 'None'}"
if confidence is not None:
    letter_text += f" (conf: {confidence:.2f})"

# Raw and corrected word display
raw_display = f"Raw: {word_buffer if word_buffer else '(empty)'}"
corrected_display = f"Corrected: {corrected_word if corrected_word else '(none)'}"

# MediaPipe status indicator
mp_color = (0, 200, 0) if "hand" in mp_status.lower() else (0, 0, 200)
cv2.putText(display_frame, f"MediaPipe: {mp_status}", ...)
```

**What this reveals:**
- Real-time visual feedback of detection state
- MediaPipe status: "detected", "no hands", "waiting..."
- Current letter with confidence score
- Word building progress (raw vs corrected)
- Sentence accumulation

#### C. Display Mirror Mode (display_thread_func)
```python
# IMPORTANT: Flip frame for display ONLY (match main.py visual appearance)
# The frame sent to backend is NOT flipped - preprocessor handles that
frame = cv2.flip(frame, 1)
```

**Why this matters:**
- User sees MIRRORED view (like main.py and typical camera apps)
- Backend receives UN-FLIPPED frame
- Preprocessor applies flip (flip_horizontal=True)
- Total: 1 flip in processing pipeline (matches main.py)
- Display flip is purely cosmetic for user experience

---

### 3. api/services/frame_preprocessor.py

**Status:** Already had diagnostic infrastructure, no changes needed.

**Existing features:**
- `BYPASS_PREPROCESSOR` flag for testing
- Default `flip_horizontal=True` (matches main.py)
- Detailed statistics tracking
- Diagnostic prints available

---

## How the Pipeline Works Now

### Architecture Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    MAIN_WS_VISUAL.PY (Client)                   │
│                                                                  │
│  Camera → cap.read() → frame (BGR, RAW, NO FLIP)               │
│                           │                                      │
│                           ├─→ Queue → Display Thread            │
│                           │           ↓                          │
│                           │         cv2.flip(1) ← COSMETIC ONLY │
│                           │           ↓                          │
│                           │         UI Overlay                   │
│                           │           ↓                          │
│                           │         cv2.imshow()                 │
│                           │                                      │
│                           └─→ JPEG encode → base64 → WebSocket  │
└──────────────────────────────────────────────────┬──────────────┘
                                                    │
                                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│                    SESSION_ENGINE (Backend)                      │
│                                                                  │
│  WebSocket Receive                                              │
│         ↓                                                        │
│  process_frame_base64()                                         │
│    ├─ [DEBUG] Print frame size                                 │
│    ↓                                                            │
│  _decode_frame_base64()                                         │
│    ├─ base64.b64decode()                                       │
│    ├─ frame_preprocessor.decode_and_preprocess()               │
│    │     ├─ cv2.imdecode()                                     │
│    │     ├─ cv2.flip(1) if flip_horizontal=True ← HERE!        │
│    │     └─ return BGR image                                   │
│    ├─ cv2.imwrite("debug_ws_frame.jpg") ← DIAGNOSTIC           │
│    └─ [DEBUG] Print shape, dtype, pixel stats                  │
│         ↓                                                        │
│  _run_mediapipe()                                               │
│    ├─ [DEBUG] Print input frame details                        │
│    ├─ cv2.cvtColor(BGR → RGB)                                  │
│    ├─ MediaPipe.detect_for_video()                             │
│    ├─ [DEBUG] Print detection results ✅/❌                     │
│    └─ return results                                            │
│         ↓                                                        │
│  if hand_landmarks exists:                                      │
│    ↓                                                            │
│  _run_rf_if_applicable()                                        │
│    ├─ extract_features() → 63-dim vector                       │
│    ├─ [DEBUG] Print vector length and sample                   │
│    ├─ rf_model.predict()                                       │
│    ├─ [DEBUG] Print prediction                                 │
│    └─ _accept_new_letter() if conditions met                   │
│         ↓                                                        │
│  _build_state_payload()                                         │
│    └─ WebSocket Send                                            │
│         ↓                                                        │
│      Client receives and displays                               │
└─────────────────────────────────────────────────────────────────┘
```

### Key Points

1. **Single Flip Policy:**
   - Client sends RAW frame (no flip)
   - Preprocessor applies flip_horizontal=True
   - Total processing: 1 horizontal flip (matches main.py)
   - Display flip is separate (cosmetic)

2. **Diagnostic Checkpoints:**
   - Entry: Frame size received
   - Decode: Frame decoded successfully? Shape? Pixel stats?
   - MediaPipe: Hands detected? How many? Confidence?
   - RF: Feature vector valid? Prediction result?
   - Exit: State payload sent

3. **Debug Artifacts:**
   - `debug_ws_frame.jpg`: Last processed frame (POST-preprocessing)
   - Console logs: Real-time pipeline status
   - UI overlay: Visual feedback of detection state

---

## Testing Protocol

### Step 1: Start Backend
```powershell
cd C:\GithubRepos\bridge_py
.\myenv\Scripts\activate
python -m uvicorn api.api_main:app --reload --host 0.0.0.0 --port 8000
```

**Watch for:**
- Server starts successfully
- No import errors
- Listening on port 8000

### Step 2: Start Visual Client
```powershell
cd C:\GithubRepos\bridge_py
.\myenv\Scripts\activate
python main_ws_visual.py
```

**Watch for:**
- Session initialization successful
- WebSocket connection established
- Camera opened
- Window appears with mirrored view

### Step 3: Observe Diagnostics

**In Backend Terminal:**
```
📥 WS frame received | bytes: 45232
[DEBUG][WS] Saved frame to debug_ws_frame.jpg | shape=(480, 640, 3), dtype=uint8
[DEBUG][WS] Pixel stats: min=0, max=255, mean=127.45
➡️  Decoded image shape: (480, 640, 3)
➡️  dtype: uint8
[DEBUG][MP] Input frame shape for MediaPipe: (480, 640, 3), dtype=uint8
[DEBUG][MP] MediaPipe detected 1 hand(s)          ← LOOK FOR THIS! ✅
[DEBUG][MP]   Hand 0: Right (0.987)
✋ MediaPipe: detected 1 hand(s)
[DEBUG][RF] Input vector length: 63
[DEBUG][RF] First 10 values: [0.234, 0.567, ...]
[DEBUG][RF] Prediction: H
🌲 RF prediction result: 'H' (confidence: 0.892)
```

**In Client Terminal:**
```
📨 WS State Update:
   detection.letter: 'H' | confidence: 0.892     ← LOOK FOR THIS! ✅
   word.raw_buffer: ['h'] | corrected: 'h'
   sentence.current: ''
```

**In OpenCV Window:**
- Current Letter: H (conf: 0.89)
- Raw: h
- MediaPipe: detected ('H')

### Step 4: Analyze debug_ws_frame.jpg

```powershell
# Open the debug frame
start debug_ws_frame.jpg
```

**Compare with main.py camera view:**
- Hand orientation same? ✅
- Hand position similar? ✅
- Brightness/contrast OK? ✅
- Resolution adequate? ✅

---

## Troubleshooting Guide

### Problem: "MediaPipe detected NO HANDS" (Current Issue)

**Possible Causes:**

1. **Orientation Mismatch**
   - Debug frame shows hand rotated/upside-down
   - **Fix:** Adjust `frame_preprocessor.py` rotation_angle or flip settings

2. **Double Flip**
   - Debug frame shows hand mirrored wrong way
   - **Fix:** Set `frame_preprocessor.flip_horizontal = False` OR add flip in client

3. **Image Quality**
   - Debug frame too dark, blurry, or pixelated
   - **Fix:** Adjust JPEG quality, lighting, camera settings

4. **Wrong Frame Sent**
   - Debug frame doesn't show hand at all
   - **Fix:** Check camera capture, ensure hand visible in client window

### Problem: MediaPipe detects but no letters

**Check:**
- RF feature vector length (should be 63)
- RF prediction values (should be valid letters)
- Cooldown time not blocking (COOLDOWN_TIME = 1.0s)
- Confidence threshold (RF should have conf > 0.5)

### Problem: Letters detected but words don't form

**Check:**
- Autocorrector receiving letters (word.raw_buffer)
- Word timeout settings (word_pause_ms, phrase_pause_ms)
- Word finalization logic in SessionEngine

---

## Next Steps After Diagnostics

1. **Run the system** and collect diagnostic output
2. **Examine debug_ws_frame.jpg** visually
3. **Identify the exact mismatch** (flip, rotation, quality, etc.)
4. **Apply minimal fix** to align WebSocket with main.py
5. **Verify end-to-end** detection works
6. **Optionally disable** verbose diagnostics after fix confirmed

---

## Files Checklist

- ✅ `engine_bridge/session_engine.py` - Diagnostics added
- ✅ `main_ws_visual.py` - Enhanced logging and display
- ✅ `api/services/frame_preprocessor.py` - Already configured
- ✅ `DIAGNOSTIC_ANALYSIS.md` - Root cause analysis doc
- ✅ `IMPLEMENTATION_SUMMARY.md` - This file

---

## Preservation Rules

**DO NOT MODIFY:**
- `main.py` (working reference pipeline)
- WebSocket endpoint URLs
- SessionEngine architecture
- RF/LSTM model files

**SAFE TO MODIFY:**
- `frame_preprocessor.py` configuration
- `main_ws_visual.py` display/logging
- Diagnostic print statements
- Frame orientation settings

---

## Expected Outcome

After diagnostics reveal the issue and fix is applied:

```
✅ MediaPipe detects hands in WebSocket pipeline
✅ RF predicts letters accurately
✅ Words form correctly via autocorrector
✅ Sentences accumulate properly
✅ main_ws_visual.py behaves like main.py
✅ Production WebSocket endpoints work perfectly
```

## Documentation

See `DIAGNOSTIC_ANALYSIS.md` for detailed root cause analysis and solution strategies.
