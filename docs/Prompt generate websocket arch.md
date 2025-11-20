You are an AI pair programmer working inside the backend project "bridge_py" for Bridge, a real-time Peruvian Sign Language (LSP) → text → translation → TTS system.

Your task is to DESIGN AND IMPLEMENT a robust architecture that replicates the behavior of an existing local lab script (`main.py`, which uses OpenCV and a local camera) but for a production backend exposed via FastAPI + WebSockets.

IMPORTANT CONSTRAINT:
- Do NOT modify `main.py`. It is a local playground and must remain intact.
- You must implement everything in the backend code used by the frontend (bridge_py API), using a clean architecture, without duplicating logic inconsistently.

==================================================
HIGH-LEVEL GOAL
==================================================

Build a backend that:

1. Receives camera frames from a Flutter frontend over WebSockets (base64-encoded).
2. Runs the LSP pipeline:
   - MediaPipe hand landmarks
   - Random Forest (and optionally LSTM) classification of letters
   - Cooldown logic between detections
   - Timers for:
     - end of word after X seconds of inactivity
     - end of sentence after Y seconds of inactivity
   - Word building and autocorrection with BERT / AutoCorrector
   - Sentence aggregation
   - Optional translation (DeepL) to a target language selected in the frontend
   - Optional TTS (Text-to-Speech), with mute/unmute behavior
3. Sends back to the frontend, in REAL TIME:
   - Detected letter (per frame)
   - Raw word buffer (sequence of letters)
   - Corrected word (BERT/autocorrect result)
   - Current sentence text
   - When a sentence ends, the translated sentence (if enabled)
   - Optionally, TTS audio in base64
4. Supports:
   - A PLAY/STOP flow: front can start/stop detection.
   - MUTE/UNMUTE TTS.
   - Clean/reset all text (word + sentence) via a “clear” action.

All this must be implemented as a stateful, per-session engine instead of ad-hoc logic per endpoint.

==================================================
ARCHITECTURE TO IMPLEMENT
==================================================

Implement the following core components:

1) SessionEngine (per-session state machine)
2) SessionManager (global registry of sessions)
3) WebSocket endpoint for real-time detection
4) A minimal, clean set of REST endpoints to:
   - initialize sessions
   - update preferences
   - manually finalize/reset phrases if needed

Do not duplicate logic across endpoints; instead, everything related to detection, timers, word/sentence building, translation, and TTS should live inside SessionEngine and be reused.

==================================================
SESSIONENGINE DESIGN
==================================================

Create a class, e.g. `SessionEngine`, in a module such as:
- `engine_bridge/session_engine.py`

This class represents the server-side "brain" of one translation session. It must encapsulate the logic currently present as global state and loop behavior in `main.py` (but without any OpenCV UI or camera access).

Key responsibilities for SessionEngine:

- Maintain per-session state:
  - Running flags and preferences:
    - `is_running: bool` (true when PLAY, false when STOP)
    - `tts_enabled: bool` (global switch for TTS usage)
    - `tts_muted: bool` (mute/unmute audio)
    - `text_language: str` (base language of sentence, e.g. "es")
    - `target_language: str` (language to translate to, e.g. "en")
    - `auto_translate: bool` (if true and text_language != target_language, translate sentence on completion)
    - `word_pause_ms: int` (e.g. 4000 ms = 4s without new letter → end of word)
    - `phrase_pause_ms: int` (e.g. 8000 ms = 8s without new letter → end of sentence)
  - Detection & timing state (similar to main.py):
    - `last_prediction: Optional[str]`
    - `last_time: float` (last detection time)
    - `last_letter_time: float` (last time a letter was accepted)
    - `phrase_active: bool`
    - `word_finalized: bool`
    - `sentence_completed: bool`
    - `letra_actual: str`
    - `completed_sentence: str`
    - `translated_sentence: str`
    - `translated_lang: str`
  - ML/Autocorrect/TTS components:
    - An instance of `AutoCorrector` (same type you use in `main.py`)
    - Access to shared ML models:
      - Random Forest model (required)
      - Optional LSTM model and its frame buffer (like lstm_buffer in main.py)
    - Access to translation service (`translate_text`) and TTS (`bridge_tts`).

- Expose methods:
  - `update_preferences(preferences: dict) -> None`
    - Merge changes (tts_muted, target_language, word_pause_ms, phrase_pause_ms, etc.).
  - `set_running(is_running: bool) -> None`
    - This is called on PLAY/STOP.
  - `clear_all() -> None`
    - Clears word buffer, sentence, translation, TTS audio, etc. Used by “clear” button.
  - `process_frame_base64(frame_b64: str) -> dict`
    - Core method called whenever a new frame arrives over WebSocket.
    - Steps:
      1) If `not is_running`, do NOT run inference; just return current state snapshot.
      2) Decode base64, convert to image (OpenCV, BGR → RGB).
      3) Run MediaPipe hand detection (using shared hand_landmarker).
      4) Run ML inference:
         - Try LSTM if configured, using its sequence buffer logic.
         - If no LSTM result, run RF on the hand_world_landmarks, like in main.py.
         - Enforce cooldown (e.g., COOLDOWN_TIME ~ 1.0s) before accepting a new letter.
         - If a new valid letter is detected:
           - If the previous sentence was completed, clear it to start a new one.
           - Update `letra_actual`, call `autocorrector.add_letter(...)`.
           - Update `last_prediction`, `last_time`, `last_letter_time`.
           - Set `phrase_active = True`, `word_finalized = False`.
      5) Run timeout logic for word and phrase:
         - If there is content in the current word buffer AND
           `now - last_letter_time >= word_pause_ms / 1000.0` AND
           `not word_finalized`:
             - Call `autocorrector.finish_word()`.
             - Mark `word_finalized = True`.
             - Clear `letra_actual`.
         - If phrase is active AND `now - last_letter_time >= phrase_pause_ms / 1000.0`:
             - Complete the sentence:
               - Use `autocorrector.end_sentence()` to finalize.
               - Set `completed_sentence`, `sentence_completed = True`, `phrase_active = False`.
               - Trigger translation logic if `auto_translate` and languages differ.
               - Prepare TTS audio if enabled and not muted.
      6) Build and return a JSON-serializable dict with current state (see PAYLOAD FORMAT section).

  - Internal helper methods:
    - `_run_mediapipe(...)`
    - `_run_lstm_if_applicable(...)`
    - `_run_rf_if_applicable(...)`
    - `_check_word_timeout(now: float) -> None`
    - `_check_phrase_timeout(now: float) -> None`
    - `_complete_sentence() -> None`
    - `_run_translation_if_needed() -> None`
    - `_prepare_tts_audio() -> None` (optional, if you want TTS on the backend side)
    - `_build_state_payload() -> dict` (see payload format below)

Implementation hint:
- You should copy the logic from `main.py` (cooldowns, timers, AutoCorrector usage, translation + TTS sequence) and adapt it to methods of `SessionEngine` WITH NO UI and NO camera loops. Do NOT call cv2.imshow or any OpenCV window functions.

==================================================
SESSIONMANAGER
==================================================

Implement a global `SessionManager` responsible for:

- Holding a dict: `session_id -> SessionEngine`.
- Creating new SessionEngine instances with shared models/resources.
- Optionally managing TTL/cleanup of inactive sessions.

Example responsibilities:

- `get_or_create_session(session_id: str, preferences: dict) -> SessionEngine`
- `get_session(session_id: str) -> Optional[SessionEngine]`
- `remove_session(session_id: str) -> None`

This manager should be initialized at app startup, where:
- RF model is loaded once
- Optional LSTM model is loaded once
- MediaPipe hand_landmarker is created once
- Those shared objects are passed into each SessionEngine instance.

==================================================
WEBSOCKET ENDPOINT DESIGN
==================================================

Create or refactor a WebSocket endpoint, e.g.:

- `@app.websocket("/realtime/ws/detection/{session_id}")`

This WebSocket will be the MAIN real-time interface for the frontend. The frontend will:

- Open the WebSocket when the user presses PLAY.
- Send messages at ~200ms intervals with frames (base64 JPEG).
- Also send "control" messages for play/stop/mute/preferences.

On the backend, implement the following protocol:

Incoming messages from the client MUST be JSON with a `type` field:

1) Frame messages:
```json
{
  "type": "frame",
  "frameBase64": "data:image/jpeg;base64,..."
}
```json

2) Control messages:
{
  "type": "control",
  "action": "play" | "stop" | "update_preferences" | "clear_all",
  "payload": { ... } // optional, depending on action
}

Behavior by action:

play:
- Mark the session’s is_running = True.

stop:
- Mark is_running = False. No more detection should be processed until play again.

update_preferences:
- Merge provided fields: target_language, auto_translate, tts_muted, tts_enabled, word_pause_ms, phrase_pause_ms, etc. into the SessionEngine preferences.

clear_all:
- Call SessionEngine.clear_all() to clear word buffer, sentence, translation, TTS state.

For each frame message:
- Use SessionManager to get/create the SessionEngine for the session_id.
- Call engine.process_frame_base64(frameBase64).
- Send back the resulting state payload over WebSocket as JSON.

==================================================
STATE PAYLOAD FORMAT (BACKEND → FRONTEND)
==================================================

Every time a frame is processed, the WebSocket should send a JSON response with the full state snapshot, for example:

{
  "type": "state_update",
  "session_id": "abc123",
  "timestamp": 1732112345.123,

  "detection": {
    "letter": "H",
    "confidence": 0.89,
    "model": "rf"     // or "lstm"
  },

  "word": {
    "raw_buffer": "hnla",       // as typed by letters
    "corrected": "hola",        // result from BERT/autocorrector
    "just_finished": false      // true only on the frame where the word finished
  },

  "sentence": {
    "current": "hola soy yo",   // current sentence string
    "completed": false,
    "just_completed": false     // true only when the sentence is finished (timeout or manual)
  },

  "translation": {
    "enabled": true,            // based on auto_translate and language preferences
    "target_language": "en",
    "translated_sentence": null,
    "just_translated": false    // true only on the frame where translation happened
  },

  "timers": {
    "time_since_last_letter": 1.2,
    "word_timer_active": true,
    "phrase_timer_active": true
  },

  "tts": {
    "enabled": true,            // tts_enabled && !tts_muted
    "muted": false,
    "audio_available": false,   // true only when audio is generated
    "audio_base64": null,       // base64 audio when sentence completes and TTS is generated
    "audio_mime_type": "audio/mpeg"
  }
}

When a sentence completes and translation + TTS are triggered, the payload should include:

- sentence.completed = true
- sentence.just_completed = true

If translation applies:
- translation.translated_sentence = "hi it's me"
- translation.just_translated = true

If TTS and not muted:
- tts.audio_available = true
- tts.audio_base64 = "<base64-encoded audio>"
- tts.audio_mime_type = "audio/mpeg"

The frontend will:
- Render letter-by-letter updates (detection.letter).
- Render word.raw_buffer and word.corrected in real time.
- Render sentence.current as the user signs.
- On sentence completion, if translation is enabled, show translation.translated_sentence.
- On TTS audio, decode tts.audio_base64 and play it (if not muted).

==================================================
REST ENDPOINTS TO KEEP / IMPLEMENT
==================================================

Define a minimal and clean REST API:

1) POST /session/init

Input:
- optional session_id,
- preferences object.

Behavior:
- If session_id is provided, try to attach or recreate.
- If not, generate a new session_id.
- Initialize a SessionEngine with given preferences:
  - tts_enabled
  - tts_muted
  - text_language
  - target_language
  - auto_translate
  - word_pause_ms (default 4000)
  - phrase_pause_ms (default 8000)

Output:
- { "session_id": "...", "preferences": {...} }.

2) PATCH /session/preferences

Input:
- session_id,
- partial preferences.

Behavior:
- Get SessionEngine and call update_preferences.
- Use this if you want to change language, TTS behavior, or timers via REST instead of WebSocket.

3) POST /phrase/finalize

Input:
- session_id.

Behavior:
- Manually trigger _complete_sentence() in the SessionEngine, same as if phrase timeout happened.

Output:
- The final sentence, translation (if any), and TTS flags/audio as part of a state-like response.

4) POST /phrase/reset

Input:
- session_id.

Behavior:
- Call SessionEngine.clear_all().

Output:
- A clean state snapshot (empty word, sentence, translation, etc.).

5) GET /session/status/{session_id}

Behavior:
- Returns SessionEngine._build_state_payload() without processing frames.
- This can be used as debug/admin, not necessarily by the mobile app.

All other existing endpoints that duplicate detection, timeline, word-builder, or BERT logic should either:
- Be removed if not used by any client, OR
- Be refactored to call the SessionEngine methods instead of having their own independent logic.

Goal: avoid dead code and avoid multiple inconsistent codepaths.

==================================================
TIMING AND PERFORMANCE PARAMETERS
==================================================

Implement the following defaults (configurable via preferences):

- Frame sending interval from client: ~200 ms (5 FPS).
  - This is a good compromise between latency, CPU usage, and network bandwidth for static hand gestures.

- Word timeout (end of word):
  - word_pause_ms = 4000 → 4 seconds after the last accepted letter.

- Phrase timeout (end of sentence):
  - phrase_pause_ms = 8000 → 8 seconds after the last accepted letter.

- Cooldown between letter detections (to avoid duplicates from jitter):
  - Around 1.0 second, similar to COOLDOWN_TIME in main.py.

These values MUST be enforced on the backend using time.time() deltas and last_letter_time, not by the frontend. The backend is the source of truth for when a word or sentence is considered finished.

==================================================
CLEANUP AND REFACTORING EXPECTATIONS
==================================================

- Do NOT modify main.py. All new logic lives in API/backend modules (bridge_py).

Identify any existing endpoints that:
- duplicate detection logic,
- manually manipulate word buffers, or
- perform separate BERT/AutoCorrector actions.

Refactor those endpoints so they delegate to SessionEngine OR remove them if they are no longer needed.

Remove dead code, unused utilities, and anything that is not part of the new WebSocket + SessionEngine flow.

Ensure there is a single source of truth for:
- detection (RF/LSTM)
- word building
- sentence completion
- translation
- TTS
- timers and cooldowns

==================================================
DELIVERABLES
==================================================

- A fully implemented SessionEngine class with:
  - state management
  - detection logic (RF/LSTM)
  - timers (word, phrase)
  - word and sentence construction via AutoCorrector
  - translation and TTS support
  - state payload builder

- A SessionManager that shares ML models and MediaPipe resources across sessions.

- A WebSocket endpoint that:
  - supports frame and control messages,
  - uses SessionManager + SessionEngine,
  - returns state_update payloads on each processed frame.

- A minimal REST API (/session/init, /session/preferences, /phrase/finalize, /phrase/reset, /session/status) all implemented using SessionEngine, with no duplicate logic.

- Removal or refactor of any obsolete endpoints or codepaths that are no longer needed with the SessionEngine/WebSocket approach.

Apply best practices:
- Type hints
- Clear separation between transport (FastAPI/WS) and domain logic (SessionEngine)
- No blocking operations in the WebSocket loop
- Reuse loaded models instead of re-loading per session or per frame
- Keep the code readable and maintainable by a backend/ML engineer team.
