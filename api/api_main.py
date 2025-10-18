from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import detection, text_to_speech, autocorrector, translation, websocket_detection

app = FastAPI(
    title="Bridge Landmark Detection API - ULTRA RÁPIDO",
    description=(
        "API optimizada para detección de señas LSP en tiempo real. "
        "Incluye WebSocket ultra-rápido para comunicación conversacional "
        "con aplicaciones móviles y autocorrección inteligente."
    ),
    version="2.0.0",
    contact={
        "name": "LUMIX Team",
        "url": "https://bridge.com.pe",
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Processing-Time", "X-Response-Time"]
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
        "message": "🚀 Bridge API ULTRA-RÁPIDA funcionando!",
        "version": "2.0.0",
        "features": [
            "websocket_realtime", 
            "autocorrection", 
            "translation", 
            "conversational_lsp"
        ],
        "endpoints": {
            "websocket": "/realtime/ws/detection/{client_id}",
            "status": "/realtime/ws/status",
            "docs": "/docs"
        },
        "optimization": "Diseñada para LSP conversacional < 50ms"
    }

app.include_router(detection.router, tags=["detection"])
app.include_router(text_to_speech.router, tags=["text-to-speech"])
app.include_router(autocorrector.router, prefix="/autocorrector", tags=["autocorrector"])
app.include_router(translation.router, tags=["translation"])
app.include_router(websocket_detection.router, prefix="/realtime", tags=["realtime-websocket"])

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {
            "hand_detection": "active",
            "websocket": "active",
            "autocorrector": "active",
            "translation": "active"
        }
    }

import time