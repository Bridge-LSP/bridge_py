# BERT Model Loading - Architecture Diagrams

## Before: Per-Request Loading ❌

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HTTP Request 1                                │
│                    (Create WebSocket Session)                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  SessionEngine.__init__()                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  AutoCorrector.__init__()                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│               AutoCorrector._load_bert_model()                       │
│                                                                      │
│  ❌ AutoTokenizer.from_pretrained(...)                              │
│  ❌ AutoModelForMaskedLM.from_pretrained(...)                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   🌐 Network Request to HuggingFace                  │
│                                                                      │
│  GET https://huggingface.co/.../resolve/main/config.json            │
│  GET https://huggingface.co/.../resolve/main/tokenizer.json         │
│  GET https://huggingface.co/.../resolve/main/model.bin              │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ⚠️ 429 Rate Limit Error                          │
│                                                                      │
│  "Too many requests from this IP"                                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              🔄 Exponential Backoff Retry Loop                       │
│                                                                      │
│  Retry 1: Wait 1s    → Fail                                         │
│  Retry 2: Wait 2s    → Fail                                         │
│  Retry 3: Wait 4s    → Fail                                         │
│  Retry 4: Wait 8s    → Fail                                         │
│  Retry 5: Wait 16s   → Fail                                         │
│                                                                      │
│  Total: 30-60 seconds wasted                                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   💥 Timeout or Error Response                       │
│                                                                      │
│  Response time: 30-60 seconds                                       │
└─────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                        HTTP Request 2                                │
│                    (Create Another Session)                          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
            🔁 ENTIRE PROCESS REPEATS (30-60s again!)

Memory Usage per Session: 500 MB
Network Calls per Session: 3-5 requests
Error Rate: High (429 errors)
User Experience: Terrible
```

---

## After: Global Singleton Loading ✅

```
┌─────────────────────────────────────────────────────────────────────┐
│                   🐳 Container Startup                               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Python Process Starts                              │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              import engine_bridge.bert_model_loader                  │
│                                                                      │
│  (Module import triggers _load_models() automatically)              │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      _load_models() [ONCE]                           │
│                                                                      │
│  🔒 Production Mode: local_files_only=True                          │
│  📂 Cache: /app/hf-cache                                            │
│  ❌ Network: DISABLED                                               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Load from Local Cache (5-10 seconds)                    │
│                                                                      │
│  ✅ Tokenizer: 10 MB                                                │
│  ✅ Model: 490 MB                                                   │
│  ✅ Pipeline: Created                                               │
│                                                                      │
│  Total: 500 MB loaded into RAM                                      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Store in Global Module Variables                        │
│                                                                      │
│  _TOKENIZER = <BertTokenizer object>                                │
│  _MODEL = <BertForMaskedLM object>                                  │
│  _PIPELINE = <FillMaskPipeline object>                              │
│  _LOAD_SUCCESS = True                                               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Startup Complete                          │
│                    ✅ Ready to Accept Requests                      │
└─────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                        HTTP Request 1                                │
│                    (Create WebSocket Session)                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  SessionEngine.__init__()                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  AutoCorrector.__init__()                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│          AutoCorrector._use_global_bert_models()                     │
│                                                                      │
│  ✅ self.tokenizer = get_bert_tokenizer()  ← Global reference       │
│  ✅ self.model = get_bert_model()          ← Global reference       │
│  ✅ self.nlp = get_bert_pipeline()         ← Global reference       │
│                                                                      │
│  Time: < 1 millisecond (just pointer assignment)                    │
│  Memory: 0 MB additional (shares global model)                      │
│  Network: 0 calls                                                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   ✅ Response (< 50ms)                               │
└─────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                        HTTP Request 2                                │
│                        HTTP Request 3                                │
│                        HTTP Request N                                │
│                    (All subsequent sessions)                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
          ✅ Same fast process (< 50ms each)
          ✅ All share the SAME global models
          ✅ Zero additional memory
          ✅ Zero network calls

Memory Usage: 500 MB total (shared across all sessions)
Network Calls: 0 during requests
Error Rate: Zero (no network access)
User Experience: Excellent
```

---

## Memory Architecture Comparison

### Before: Duplicate Models ❌

```
Process Memory Layout:

┌──────────────────────────────────┐
│  Session 1 - AutoCorrector       │
│  ├─ Tokenizer: 10 MB             │
│  ├─ Model: 490 MB                │
│  └─ Pipeline: refs                │
├──────────────────────────────────┤
│  Session 2 - AutoCorrector       │
│  ├─ Tokenizer: 10 MB (DUPLICATE) │
│  ├─ Model: 490 MB (DUPLICATE)    │
│  └─ Pipeline: refs                │
├──────────────────────────────────┤
│  Session 3 - AutoCorrector       │
│  ├─ Tokenizer: 10 MB (DUPLICATE) │
│  ├─ Model: 490 MB (DUPLICATE)    │
│  └─ Pipeline: refs                │
├──────────────────────────────────┤
│  Session N - AutoCorrector       │
│  ├─ Tokenizer: 10 MB (DUPLICATE) │
│  ├─ Model: 490 MB (DUPLICATE)    │
│  └─ Pipeline: refs                │
└──────────────────────────────────┘

Total Memory: N × 500 MB = 💥 HUGE
Example (10 sessions): 5,000 MB (5 GB)
Example (100 sessions): 50,000 MB (50 GB) ← Impossible!
```

### After: Shared Global Models ✅

```
Process Memory Layout:

┌──────────────────────────────────┐
│  Global Models (Singleton)       │
│  ├─ Tokenizer: 10 MB             │
│  ├─ Model: 490 MB                │
│  └─ Pipeline: refs                │
│                                   │
│  📍 Single copy in memory         │
└──────────────────────────────────┘
         ▲         ▲         ▲
         │         │         │
         │         │         └──────────┐
         │         │                    │
         │         └──────────┐         │
         │                    │         │
┌────────┴──────┐  ┌──────────┴──┐  ┌──┴─────────┐
│  Session 1    │  │  Session 2  │  │  Session N │
│  5 MB         │  │  5 MB       │  │  5 MB      │
│  (refs only)  │  │  (refs only)│  │  (refs only)│
└───────────────┘  └─────────────┘  └────────────┘

Total Memory: 500 MB + (N × 5 MB)
Example (10 sessions): 550 MB
Example (100 sessions): 1,000 MB (1 GB) ← Reasonable!

Savings: 89-98% less memory usage
```

---

## Network Call Flow

### Before: Per-Request Network Calls ❌

```
Time: 0s
├─ Request 1: Create Session
│  └─ Network calls to HuggingFace
│     ├─ GET config.json
│     ├─ GET tokenizer.json
│     └─ GET model.bin
│     Total: 30-60 seconds
│     Status: ❌ 429 Rate Limit
│
Time: 30-60s (after retries)
├─ Request 2: Create Session
│  └─ Network calls to HuggingFace (AGAIN!)
│     ├─ GET config.json
│     ├─ GET tokenizer.json
│     └─ GET model.bin
│     Total: 30-60 seconds
│     Status: ❌ 429 Rate Limit
│
Time: 60-120s
├─ Request 3: Create Session
│  └─ Network calls... (repeat indefinitely)
│
Total Network Calls: N × 3-5 calls = 💥 RATE LIMIT HELL
```

### After: Zero Network Calls ✅

```
Time: 0s (Container Startup)
├─ Load from local cache ONCE
│  ├─ Read /app/hf-cache/config.json
│  ├─ Read /app/hf-cache/tokenizer.json
│  └─ Read /app/hf-cache/model.bin
│  Total: 5-10 seconds
│  Network: ✅ None (local_files_only=True)
│
Time: 10s (Ready for Requests)
├─ Request 1: Create Session
│  └─ Use global model
│     Total: < 50ms
│     Network: ✅ None
│
├─ Request 2: Create Session
│  └─ Use global model
│     Total: < 50ms
│     Network: ✅ None
│
├─ Request N: Create Session
│  └─ Use global model
│     Total: < 50ms
│     Network: ✅ None
│
Total Network Calls: 0 during requests = ✅ NO RATE LIMITS
```

---

## Code Reference Flow

### Old Code Path (Per-Request) ❌

```python
# api/routers/realtime_websocket.py
@router.websocket("/ws/detection/{session_id}")
async def websocket_detection_endpoint(websocket, session_id):
    session_engine = session_manager.get_or_create_session(session_id)
                                    ↓
    # engine_bridge/session_engine.py
    class SessionEngine:
        def __init__(self, session_id):
            self.autocorrector = AutoCorrector()  ← Creates new instance
                                        ↓
    # engine_bridge/autocorrector/autocorrector_core.py
    class AutoCorrector:
        def __init__(self):
            self._load_bert_model()  ← ❌ LOADS MODEL EVERY TIME
                      ↓
        def _load_bert_model(self):
            # ❌ 30-60 seconds of network calls
            self.tokenizer = AutoTokenizer.from_pretrained(...)
            self.model = AutoModelForMaskedLM.from_pretrained(...)
```

### New Code Path (Global Singleton) ✅

```python
# Container starts → Python imports modules

# engine_bridge/bert_model_loader.py (imported first)
# ✅ Loads at module import time (ONCE)
_TOKENIZER = AutoTokenizer.from_pretrained(
    MODEL_NAME,
    cache_dir="/app/hf-cache",
    local_files_only=True  # ✅ No network
)
_MODEL = AutoModelForMaskedLM.from_pretrained(
    MODEL_NAME,
    cache_dir="/app/hf-cache",
    local_files_only=True  # ✅ No network
)

def get_bert_tokenizer():
    return _TOKENIZER  # ✅ Just returns reference


# api/routers/realtime_websocket.py
@router.websocket("/ws/detection/{session_id}")
async def websocket_detection_endpoint(websocket, session_id):
    session_engine = session_manager.get_or_create_session(session_id)
                                    ↓
    # engine_bridge/session_engine.py
    class SessionEngine:
        def __init__(self, session_id):
            self.autocorrector = AutoCorrector()  ← Creates new instance (fast!)
                                        ↓
    # engine_bridge/autocorrector/autocorrector_core.py
    class AutoCorrector:
        def __init__(self):
            self._use_global_bert_models()  ← ✅ Just gets references
                      ↓
        def _use_global_bert_models(self):
            # ✅ < 1ms (just pointer assignment)
            self.tokenizer = get_bert_tokenizer()  # Returns global
            self.model = get_bert_model()          # Returns global
            self.nlp = get_bert_pipeline()         # Returns global
```

---

## Production vs Development Flow

### Development Mode Flow

```
Developer runs: python -m uvicorn api.api_main:app

┌─────────────────────────────┐
│  ENV not set (defaults to   │
│  "dev")                      │
└─────────────────────────────┘
              ↓
┌─────────────────────────────┐
│  bert_model_loader imports  │
│  Detects: IS_PRODUCTION=False│
└─────────────────────────────┘
              ↓
┌─────────────────────────────┐
│  Attempts to load models    │
│  from cache (./hf-cache/)   │
└─────────────────────────────┘
              ↓
         Not found?
              ↓
┌─────────────────────────────┐
│  🌐 Downloads from          │
│  HuggingFace (allowed)      │
│  Saves to ./hf-cache/       │
│  Time: 2-5 minutes          │
└─────────────────────────────┘
              ↓
┌─────────────────────────────┐
│  ✅ Models loaded           │
│  Subsequent runs use cache  │
│  (fast)                     │
└─────────────────────────────┘
```

### Production Mode Flow

```
Cloud Run starts container with ENV=prod

┌─────────────────────────────┐
│  ENV=prod                    │
│  (set in Dockerfile or      │
│   Cloud Run config)          │
└─────────────────────────────┘
              ↓
┌─────────────────────────────┐
│  bert_model_loader imports  │
│  Detects: IS_PRODUCTION=True │
└─────────────────────────────┘
              ↓
┌─────────────────────────────┐
│  Attempts to load models    │
│  from cache (/app/hf-cache/)│
│  with local_files_only=True │
└─────────────────────────────┘
              ↓
         Found?
        ↙     ↘
      Yes      No
       ↓        ↓
    ✅ OK    ❌ FAIL FAST
       ↓        ↓
       │    Error: Model files
       │    not found in cache
       │        ↓
       │    Container fails to start
       │    (prevents silent failures)
       ↓
┌─────────────────────────────┐
│  ✅ Models loaded from      │
│  local cache                │
│  Time: 5-10 seconds         │
│  Network: Zero calls        │
└─────────────────────────────┘
```

---

## Docker Build Flow

### Dockerfile Structure

```dockerfile
FROM python:3.10-slim
WORKDIR /app

# Stage 1: Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Copy application code
COPY . .

# Stage 3: Copy pre-downloaded models
# ⚠️ CRITICAL: This step must happen BEFORE container runs
COPY hf-cache /app/hf-cache
# └─ Models downloaded locally via download_bert_models.py

# Stage 4: Set production environment
ENV ENV=prod
ENV HF_CACHE_DIR=/app/hf-cache

# Stage 5: Start application
CMD ["uvicorn", "api.api_main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build Process

```
Local Machine:
┌────────────────────────────┐
│ Run download_bert_models.py│
│ Downloads to ./hf-cache/   │
│ (~500 MB)                  │
└────────────────────────────┘
             ↓
┌────────────────────────────┐
│ docker build -t image:prod │
│ Copies hf-cache to image   │
│ Image size: ~2 GB          │
└────────────────────────────┘
             ↓
┌────────────────────────────┐
│ docker push to GCR         │
│ Uploads to Google Registry │
└────────────────────────────┘
             ↓
┌────────────────────────────┐
│ Cloud Run pulls image      │
│ Models already in image    │
│ No download needed         │
└────────────────────────────┘
             ↓
┌────────────────────────────┐
│ Container starts           │
│ Loads from /app/hf-cache/  │
│ Fast startup (5-10s)       │
│ Zero network calls         │
└────────────────────────────┘
```

---

**Diagrams Version**: 1.0  
**Last Updated**: November 21, 2025  
**Status**: ✅ Complete
