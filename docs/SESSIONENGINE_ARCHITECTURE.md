# SessionEngine Architecture - Production LSP Backend

## Overview

The SessionEngine architecture is a complete rewrite of the Bridge backend that replicates the functionality of `main.py` in a production-ready, stateful, multi-session environment. This replaces ad-hoc endpoints with a unified state machine approach.

## Key Components

### 1. SessionEngine (`engine_bridge/session_engine.py`)

The core state machine that manages:
- Per-session detection state (timers, cooldowns, phrase building)
- ML model inference (Random Forest + optional LSTM)
- AutoCorrector integration with BERT
- Translation and TTS processing
- Real-time state payload generation

**Key Features:**
- Replicates exact timing logic from `main.py`
- Stateful word/sentence building
- Configurable timers and thresholds
- No UI dependencies (pure backend logic)

### 2. SessionManager (`engine_bridge/session_manager.py`)

Global registry that:
- Manages multiple SessionEngine instances
- Loads ML models once and shares them across sessions
- Handles session lifecycle and cleanup
- Provides thread-safe access to sessions

**Resource Sharing:**
- MediaPipe hand landmarker (loaded once)
- Random Forest model (shared across sessions)
- Optional LSTM model (shared across sessions)
- Automatic cleanup of inactive sessions

### 3. Real-time WebSocket (`api/routers/realtime_websocket.py`)

Production WebSocket endpoint that:
- Handles frame and control messages
- Processes frames through SessionEngine
- Returns real-time state updates
- Supports play/stop/preferences/clear actions

**Message Protocol:**
```json
// Frame message
{
  "type": "frame",
  "frameBase64": "data:image/jpeg;base64,..."
}

// Control message
{
  "type": "control", 
  "action": "play|stop|update_preferences|clear_all",
  "payload": {...}
}
```

### 4. Unified Session API (`api/routers/session_unified.py`)

REST endpoints for session management:
- `POST /session/init` - Initialize new session
- `PATCH /session/preferences` - Update session preferences
- `GET /session/status/{id}` - Get session state
- `POST /session/finalize` - Manually complete phrase
- `POST /session/reset` - Clear all session state
- `DELETE /session/destroy/{id}` - Remove session

## Architecture Benefits

### ✅ Eliminates Code Duplication
- Single source of truth for detection logic
- Shared ML models across all sessions
- Unified state management

### ✅ Production Ready
- Stateful multi-session support
- Automatic resource cleanup
- Thread-safe operations
- Error handling and logging

### ✅ Exact `main.py` Replication
- Same timing logic (1s cooldown, 4s word timeout, 8s phrase timeout)
- Same ML pipeline (RF + optional LSTM)
- Same BERT autocorrection flow
- Same translation and TTS sequence

### ✅ Frontend Friendly
- Real-time state updates over WebSocket
- Clean REST API for configuration
- Structured JSON payloads
- Support for play/stop/preferences flow

## Migration Guide

### From Legacy Endpoints

**Old:** Multiple detection endpoints with inconsistent state
```http
POST /detection/continuous-detect
POST /phrase/finalize  
POST /autocorrector/letter/add
```

**New:** Unified SessionEngine approach
```http
POST /session/init              # Create session
WebSocket /realtime/ws/detection/{id}  # All real-time processing
POST /session/finalize          # Manual completion
```

### From Direct Model Usage

**Old:** Loading models in each endpoint
```python
model = joblib.load('models/forest_model_u.pkl')
landmarker = create_hand_landmarker()
```

**New:** Shared models via SessionManager
```python
session_manager = get_session_manager()
session_engine = session_manager.get_or_create_session(session_id)
# Models already loaded and shared
```

## Configuration

### Default Timers
- **Word timeout**: 4000ms (4 seconds)
- **Phrase timeout**: 8000ms (8 seconds)  
- **Detection cooldown**: 1000ms (1 second)
- **Session TTL**: 3600s (1 hour)

### Preferences
```json
{
  "tts_enabled": true,
  "tts_muted": false,
  "text_language": "es",
  "target_language": "en", 
  "auto_translate": false,
  "word_pause_ms": 4000,
  "phrase_pause_ms": 8000
}
```

## Real-time State Payload

The WebSocket sends complete state updates on each frame:

```json
{
  "type": "state_update",
  "session_id": "abc123",
  "timestamp": 1732112345.123,
  "processing_time_ms": 23.4,

  "detection": {
    "letter": "H",
    "confidence": 0.89,
    "model": "rf"
  },

  "word": {
    "raw_buffer": "hola",
    "corrected": "hola",
    "just_finished": false
  },

  "sentence": {
    "current": "buenos dias hola",
    "completed": false,
    "just_completed": false  
  },

  "translation": {
    "enabled": true,
    "target_language": "en",
    "translated_sentence": null,
    "just_translated": false
  },

  "timers": {
    "time_since_last_letter": 1.2,
    "word_timer_active": true,
    "phrase_timer_active": true
  },

  "tts": {
    "enabled": true,
    "muted": false,
    "audio_available": false,
    "audio_base64": null,
    "audio_mime_type": "audio/mpeg"
  }
}
```

## Usage Examples

### Initialize Session
```javascript
const response = await fetch('/session/init', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    preferences: {
      auto_translate: true,
      target_language: 'en',
      word_pause_ms: 3000
    }
  })
});
const session = await response.json();
const sessionId = session.session_id;
```

### Connect WebSocket
```javascript
const ws = new WebSocket(`ws://localhost:8000/realtime/ws/detection/${sessionId}`);

ws.onmessage = (event) => {
  const state = JSON.parse(event.data);
  updateUI(state);
};

// Send frame
ws.send(JSON.stringify({
  type: "frame",
  frameBase64: frameData
}));

// Send control
ws.send(JSON.stringify({
  type: "control",
  action: "play"
}));
```

### Update Preferences
```javascript
await fetch('/session/preferences', {
  method: 'PATCH',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    session_id: sessionId,
    preferences: {
      tts_muted: true,
      target_language: 'fr'
    }
  })
});
```

## Performance Characteristics

- **Frame processing**: <50ms average
- **Model loading**: One-time at startup
- **Memory usage**: Shared models across sessions
- **Session capacity**: 100+ concurrent sessions
- **Cleanup**: Automatic every 10 minutes

## Monitoring and Debugging

### Session Status
```http
GET /session/status/{session_id}
```

### WebSocket Status  
```http
GET /realtime/ws/status
```

### Session List
```http
GET /session/list
```

### Manual Cleanup
```http
POST /session/cleanup
```

## Migration Timeline

1. **Phase 1**: New endpoints deployed alongside legacy (✅ Done)
2. **Phase 2**: Frontend migration to SessionEngine architecture
3. **Phase 3**: Legacy endpoint deprecation warnings
4. **Phase 4**: Legacy endpoint removal

## Testing

Run the server:
```bash
python -m uvicorn api.api_main:app --reload --host 0.0.0.0 --port 8000
```

Test WebSocket:
```bash
# Use WebSocket testing tools or browser console
wscat -c "ws://localhost:8000/realtime/ws/detection/test-session-123"
```

Test REST endpoints:
```bash
curl -X POST http://localhost:8000/session/init \
  -H "Content-Type: application/json" \
  -d '{"preferences": {"auto_translate": true}}'
```