# WebSocket Detection Pipeline Diagnostic Analysis

## Problem Statement

**Symptom:** MediaPipe detects hands perfectly in `main.py` (local OpenCV client) but reports "NO HANDS" in WebSocket pipeline (`main_ws_visual.py` → SessionEngine).

**Impact:** No letter detection, no word building, no sentence formation in WebSocket mode.

## Root Cause Analysis

### Working Pipeline (main.py)

```
Camera → cv2.VideoCapture.read()
    ↓
frame (BGR, no flip yet)
    ↓
cv2.flip(frame, 1) ← SINGLE HORIZONTAL FLIP (mirror effect)
    ↓
cv2.cvtColor(BGR → RGB)
    ↓
MediaPipe.detect_for_video() ← ✅ DETECTS HANDS
    ↓
Random Forest prediction
```

**Key insight:** main.py applies **ONE horizontal flip** to create mirror effect.

### Failing Pipeline (WebSocket)

```
Camera → cv2.VideoCapture.read() (in main_ws_visual.py)
    ↓
frame (BGR, raw from camera - NO FLIP in client)
    ↓
JPEG encode → base64
    ↓
WebSocket send
    ↓
SessionEngine.process_frame_base64()
    ↓
frame_preprocessor.decode_and_preprocess()
    ├─ decode base64
    ├─ cv2.imdecode()
    └─ if flip_horizontal=True: cv2.flip(image, 1)
    ↓
MediaPipe.detect_for_video() ← ❌ NO HANDS DETECTED
```

**Current config:** `frame_preprocessor.flip_horizontal = True` (default)

## Hypothesis

There are THREE possible scenarios:

### Scenario A: Preprocessing Mismatch (Most Likely)
- Frame orientation, flip, or rotation is different between main.py and WS pipeline
- MediaPipe expects a specific hand orientation
- If orientation is wrong, hand detection fails completely

### Scenario B: Image Quality/Format Issue
- JPEG encoding/decoding introduces artifacts
- Color space conversion issue
- Resolution mismatch

### Scenario C: Timing/Timestamp Issue
- MediaPipe VIDEO mode requires proper timestamps
- WebSocket timestamps might be incorrect

## Diagnostic Implementation

### Added Debug Logging

1. **session_engine.py - Frame Save**
   ```python
   cv2.imwrite("debug_ws_frame.jpg", image)
   print(f"[DEBUG][WS] Saved frame | shape={image.shape}, dtype={image.dtype}")
   print(f"[DEBUG][WS] Pixel stats: min={image.min()}, max={image.max()}, mean={image.mean():.2f}")
   ```

2. **session_engine.py - MediaPipe Detection**
   ```python
   print(f"[DEBUG][MP] Input frame shape: {frame.shape}, dtype={frame.dtype}")
   if results.handedness:
       for idx, handedness in enumerate(results.handedness):
           print(f"[DEBUG][MP]   Hand {idx}: {handedness[0].category_name} ({handedness[0].score:.3f})")
   else:
       print("[DEBUG][MP] MediaPipe detected NO HANDS")
   ```

3. **session_engine.py - Random Forest Input**
   ```python
   print(f"[DEBUG][RF] Input vector length: {len(flattened)}")
   print(f"[DEBUG][RF] First 10 values: {flattened[:10]}")
   print(f"[DEBUG][RF] Prediction: {pred}")
   ```

4. **main_ws_visual.py - State Updates**
   ```python
   detection = state.get("detection", {})
   print(f"   detection.letter: '{letra}' | confidence: {confidence}")
   print(f"   word.raw_buffer: {raw_buffer} | corrected: '{corrected_word}'")
   ```

## Solution Strategy

### Step 1: Capture Debug Frames
Run both pipelines and compare:
```bash
# Terminal 1 - Backend
python -m uvicorn api.api_main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - WebSocket client
python main_ws_visual.py

# This generates: debug_ws_frame.jpg
```

### Step 2: Visual Comparison
Compare `debug_ws_frame.jpg` with main.py camera view:
- Is hand visible and clear?
- Is hand mirrored correctly?
- Is hand rotated (0°, 90°, 180°, 270°)?
- Is resolution similar?

### Step 3: Apply Fix Based on Findings

**If double-flip detected:**
```python
# frame_preprocessor.py
self.flip_horizontal = False  # Let client handle flip
```

**If rotation needed:**
```python
# frame_preprocessor.py
self.rotation_angle = 90  # or 180, 270
```

**If no flip at all:**
```python
# main_ws_visual.py - camera_capture_thread()
frame = cv2.flip(frame, 1)  # Add flip in client before encoding
```

**If bypass needed for testing:**
```python
# frame_preprocessor.py
BYPASS_PREPROCESSOR = True  # Skip all preprocessing
```

## Expected Diagnostic Output

### When Working Correctly:
```
📥 WS frame received | bytes: 45232
[DEBUG][WS] Saved frame to debug_ws_frame.jpg | shape=(480, 640, 3), dtype=uint8
[DEBUG][WS] Pixel stats: min=0, max=255, mean=127.45
➡️  Decoded image shape: (480, 640, 3)
➡️  dtype: uint8
[DEBUG][MP] Input frame shape for MediaPipe: (480, 640, 3), dtype=uint8
[DEBUG][MP] MediaPipe detected 1 hand(s)
[DEBUG][MP]   Hand 0: Right (0.987)
✋ MediaPipe: detected 1 hand(s)
[DEBUG][RF] Input vector length: 63
[DEBUG][RF] First 10 values: [0.234, 0.567, ...]
[DEBUG][RF] Prediction: H
🌲 RF prediction result: 'H' (confidence: 0.892)

📨 WS State Update:
   detection.letter: 'H' | confidence: 0.892
   word.raw_buffer: ['h'] | corrected: 'h'
   sentence.current: ''
```

### When Failing (Current):
```
📥 WS frame received | bytes: 45232
[DEBUG][WS] Saved frame to debug_ws_frame.jpg | shape=(480, 640, 3), dtype=uint8
[DEBUG][WS] Pixel stats: min=0, max=255, mean=127.45
➡️  Decoded image shape: (480, 640, 3)
➡️  dtype: uint8
[DEBUG][MP] Input frame shape for MediaPipe: (480, 640, 3), dtype=uint8
[DEBUG][MP] MediaPipe detected NO HANDS
❌ MediaPipe: NO HANDS DETECTED
```

## Files Modified

1. **engine_bridge/session_engine.py**
   - Added frame saving to `debug_ws_frame.jpg`
   - Added detailed MediaPipe detection logging
   - Added Random Forest input/output logging

2. **api/services/frame_preprocessor.py**
   - Already has `BYPASS_PREPROCESSOR` flag for testing
   - Default config: `flip_horizontal=True` to match main.py

3. **main_ws_visual.py**
   - Enhanced console logging for WS state updates
   - Improved visual overlay with detection status
   - Added MediaPipe status indicator in UI
   - Only prints when detection activity occurs

## Next Steps

1. **Run diagnostics** and examine console output
2. **Compare debug_ws_frame.jpg** with main.py camera view
3. **Identify orientation mismatch** (flip/rotation)
4. **Apply minimal fix** to align WebSocket pipeline with main.py
5. **Verify** detection works end-to-end
6. **Remove diagnostic prints** once working (or make them conditional)

## Preservation Notes

- **DO NOT** modify main.py (it's the working reference)
- **DO NOT** change WebSocket endpoints or SessionEngine architecture
- **DO** keep main_ws_visual.py using production endpoints
- **DO** maintain RF-only mode (LSTM disabled)
