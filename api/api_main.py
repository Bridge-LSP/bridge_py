from fastapi import FastAPI
import time
import logging
from fastapi.middleware.cors import CORSMiddleware
from api.routers import (
    detection, text_to_speech, autocorrector, translation, 
    websocket_detection, realtime_detection, timer_management, continuous_detection,
    session, phrase_finalization
)

# Configuration constants
CONFIDENCE_THRESHOLD = 0.70
FRAME_MIN_INTERVAL_MS = 200     # throttle
MAX_INFLIGHT_FRAMES = 1         # backpressure: drop extra
PHRASE_IDLE_SECONDS = 5
WS_MAX_MESSAGE_BYTES = 10_485_760  # 10MB
PING_INTERVAL_SECONDS = 25

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Set DEBUG level for performance logging if needed
# logging.getLogger("api.routers.continuous_detection").setLevel(logging.DEBUG)
# logging.getLogger("api.routers.realtime_detection").setLevel(logging.DEBUG)
# logging.getLogger("api.routers.phrase_finalization").setLevel(logging.DEBUG)

try:
    from api.routers import word_builder, phrase_completion, bert_correction, enhanced_tts
    NEW_ROUTERS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Algunos routers nuevos no están disponibles: {e}")
    NEW_ROUTERS_AVAILABLE = False

app = FastAPI(
    title="Bridge Landmark Detection API",
    description=(
        "Production-grade API for real-time Peruvian Sign Language (LSP) detection. "
        "Features WebSocket communication, automatic timers, incremental state updates, "
        "unified session management, and optimized Flutter integration."
    ),
    version="3.0.0",
    contact={
        "name": "LUMIX Team",
        "url": "https://bridge.com.pe",
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_performance_headers(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Processing-Time"] = str(process_time)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

@app.get("/", tags=["root"])
async def root():
    return {
        "message": "🚀 Bridge API v3.0 - Production Ready!",
        "version": "3.0.0",
        "features": [
            "websocket_realtime", 
            "heartbeat_monitoring",
            "incremental_state_updates",
            "unified_session_init",
            "phrase_finalization",
            "autocorrection", 
            "translation", 
            "conversational_lsp",
            "performance_logging",
            "client_authentication",
            "word_builder" if NEW_ROUTERS_AVAILABLE else "basic_mode",
            "phrase_completion" if NEW_ROUTERS_AVAILABLE else "basic_mode",
            "bert_correction" if NEW_ROUTERS_AVAILABLE else "basic_mode",
            "enhanced_tts" if NEW_ROUTERS_AVAILABLE else "basic_tts"
        ],
        "endpoints": {
            "websocket": "/realtime/ws/detection/{client_id}",
            "session_init": "/session/init",
            "phrase_finalize": "/phrase/finalize",
            "continuous_detect": "/detection/continuous-detect",
            "status": "/realtime/ws/status",
            "docs": "/docs",
            "health": "/health"
        },
        "optimization": "Production-grade LSP detection < 50ms with incremental updates"
    }

@app.on_event("startup")
async def startup_event():
    print("🚀 Bridge API v3.0 Starting...")
    print("📱 Ready for Flutter connections on:")
    print("   - Local: http://127.0.0.1:8000")
    print("   - Android Emulator: http://10.0.2.2:8000")
    print("   - WebSocket: ws://127.0.0.1:8000/realtime/ws/detection/{client_id}")
    print("✨ New in v3.0:")
    print("   - Unified session init: POST /session/init")
    print("   - Phrase finalization: POST /phrase/finalize")
    print("   - Incremental state updates: POST /detection/continuous-detect")
    print("   - WebSocket heartbeat monitoring with ping/pong")
    print("   - Performance logging and client authentication")
    print("✅ Bridge API v3.0 is production ready!")

app.include_router(detection.router, tags=["detection"])
app.include_router(text_to_speech.router, tags=["text-to-speech"])
app.include_router(autocorrector.router, prefix="/autocorrector", tags=["autocorrector"])
app.include_router(translation.router, tags=["translation"])
app.include_router(websocket_detection.router, prefix="/realtime", tags=["realtime-websocket"])
app.include_router(realtime_detection.router, prefix="/realtime", tags=["realtime-hardened"])
app.include_router(timer_management.router, prefix="/timers", tags=["timer-management"])
app.include_router(continuous_detection.router, prefix="/detection", tags=["continuous-detection"])

# New v3.0 routers
app.include_router(session.router, prefix="/session", tags=["session-management"])
app.include_router(phrase_finalization.router, prefix="/phrase", tags=["phrase-finalization"])
if NEW_ROUTERS_AVAILABLE:
    app.include_router(word_builder.router, prefix="/word-builder", tags=["word-builder"])
    app.include_router(phrase_completion.router, prefix="/phrase", tags=["phrase-completion"])
    app.include_router(bert_correction.router, prefix="/bert", tags=["bert-correction"])
    app.include_router(enhanced_tts.router, prefix="/tts", tags=["enhanced-tts"])
    print("✅ Todos los routers nuevos cargados correctamente")
else:
    print("⚠️ Ejecutándose en modo básico - algunos endpoints no disponibles")

@app.get("/health")
async def health():
    return {"message": "Bridge API is running! 🌉"}