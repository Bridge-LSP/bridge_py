from fastapi import FastAPI
from api.routers import detection, text_to_speech, autocorrector, translation

app = FastAPI(
    title="Bridge Landmark Detection API",
    description=(
        "API that processes images to detect hand landmarks using MediaPipe. "
        "Includes autocorrection capabilities for sign language recognition."
    ),
    version="1.0.0",
    contact={
        "name": "LUMIX Team",
        "url": "https://bridge.com.pe",
    }
)

@app.get("/", tags=["root"])
async def root():
    return {"message": "Bridge API is running! 🌉"}

app.include_router(detection.router, tags=["detection"])
app.include_router(text_to_speech.router, tags=["text-to-speech"])
app.include_router(autocorrector.router, prefix="/autocorrector", tags=["autocorrector"])
app.include_router(translation.router, tags=["translation"])