from fastapi import FastAPI
import time
import logging
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from api.routers import (
    detection, text_to_speech, autocorrector, translation,
    websocket_detection, realtime_detection, timer_management, continuous_detection,
    session, phrase_finalization, realtime_websocket, session_unified
)

CONFIDENCE_THRESHOLD = 0.70
FRAME_MIN_INTERVAL_MS = 200
MAX_INFLIGHT_FRAMES = 1
PHRASE_IDLE_SECONDS = 5
WS_MAX_MESSAGE_BYTES = 10_485_760
PING_INTERVAL_SECONDS = 25

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

try:
    from api.routers import word_builder, phrase_completion, bert_correction, enhanced_tts
    NEW_ROUTERS_AVAILABLE = True
except ImportError:
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
        "url": "https://bridge-lsp.vercel.app/",
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
            "sessionengine_realtime",
            "unified_session_management",
            "phrase_finalization",
            "autocorrection",
            "translation",
            "conversational_lsp",
            "performance_logging",
            "shared_ml_models",
            "automatic_cleanup",
            "word_builder" if NEW_ROUTERS_AVAILABLE else "basic_mode",
            "phrase_completion" if NEW_ROUTERS_AVAILABLE else "basic_mode",
            "bert_correction" if NEW_ROUTERS_AVAILABLE else "basic_mode",
            "enhanced_tts" if NEW_ROUTERS_AVAILABLE else "basic_tts"
        ],
        "endpoints": {
            "websocket_new": "/realtime/ws/detection/{session_id}",
            "session_init": "/session/init",
            "session_preferences": "/session/preferences", 
            "session_finalize": "/session/finalize",
            "session_reset": "/session/reset",
            "session_status": "/session/status/{session_id}",
            "websocket_status": "/realtime/ws/status",
            "websocket_legacy": "/realtime/ws/detection/{client_id}",
            "docs": "/docs",
            "health": "/health"
        },
        "optimization": "Production-grade LSP detection < 50ms with incremental updates"
    }

@app.on_event("startup")
async def startup_event():
    try:
        print("🚀 [STARTUP] Starting BERT model loading in background...")
        from engine_bridge.bert_model_loader import start_background_loading
        start_background_loading()
        print("✅ [STARTUP] BERT background loading initiated")
        
        print("🚀 [STARTUP] Initializing session manager...")
        from engine_bridge.session_manager import initialize_session_manager
        session_manager = initialize_session_manager()
        print(f"✅ [STARTUP] Session manager initialized")
        
        print("🚀 [STARTUP] Starting periodic cleanup task...")
        asyncio.create_task(periodic_cleanup())
        print("✅ [STARTUP] FastAPI startup complete (<200ms)")
        print("ℹ️  [STARTUP] BERT models loading in background - check /bert/status")
    except Exception as e:
        print(f"❌ [STARTUP] Error during startup: {e}")
        import traceback
        traceback.print_exc()
        raise


async def periodic_cleanup():
    """Background task to clean up inactive sessions every 10 minutes."""
    import asyncio
    from engine_bridge.session_manager import get_session_manager
    
    while True:
        try:
            await asyncio.sleep(600)
            session_manager = get_session_manager()
            cleaned_count = session_manager.cleanup_inactive_sessions()
            pass
        except Exception:
            pass


@app.on_event("shutdown")
async def shutdown_event():
    try:
        from engine_bridge.session_manager import get_session_manager
        session_manager = get_session_manager()
        session_manager.stop_all_sessions()
    except Exception:
        pass

app.include_router(detection.router, tags=["detection"])
app.include_router(text_to_speech.router, tags=["text-to-speech"])
app.include_router(autocorrector.router, prefix="/autocorrector", tags=["autocorrector"])
app.include_router(translation.router, tags=["translation"])

app.include_router(realtime_websocket.router, prefix="/realtime", tags=["realtime-sessionengine"])
app.include_router(session_unified.router, prefix="/session", tags=["session-unified"])

app.include_router(websocket_detection.router, prefix="/realtime", tags=["realtime-websocket-legacy"])
app.include_router(realtime_detection.router, prefix="/realtime", tags=["realtime-hardened-legacy"])
app.include_router(timer_management.router, prefix="/timers", tags=["timer-management-legacy"])
app.include_router(continuous_detection.router, prefix="/detection", tags=["continuous-detection-legacy"])
app.include_router(session.router, prefix="/session", tags=["session-management-legacy"])
app.include_router(phrase_finalization.router, prefix="/phrase", tags=["phrase-finalization-legacy"])
if NEW_ROUTERS_AVAILABLE:
    app.include_router(word_builder.router, prefix="/word-builder", tags=["word-builder"])
    app.include_router(phrase_completion.router, prefix="/phrase", tags=["phrase-completion"])
    app.include_router(bert_correction.router, prefix="/bert", tags=["bert-correction"])
    app.include_router(enhanced_tts.router, prefix="/tts", tags=["enhanced-tts"])

@app.get("/health")
async def health():
    return {"message": "Bridge API is running! 🌉"}


@app.get("/bert/status", tags=["bert-health"])
async def bert_status():
    """
    Get BERT model loading status.
    
    Frontend can poll this endpoint to check if models are ready.
    WebSocket clients should wait until loaded=true before connecting.
    
    Returns:
        loaded: bool - True if models are ready to use
        loading: bool - True if currently loading
        mode: str - Current loading mode (loading, cache-only, network-fallback, failed)
        model_name: str - HuggingFace model identifier
        cache_path: str - Local cache directory path
        network_fallback_used: bool - True if network was used (cache miss)
        error: str | None - Error message if loading failed
    """
    from engine_bridge.bert_model_loader import get_model_info
    return get_model_info()