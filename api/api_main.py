from fastapi import FastAPI
from api.routers import detection, text_to_speech

app = FastAPI(
    title="Bridge Landmark Detection API",
    description=(
        "API that processes images to detect hand landmarks using MediaPipe. "
        "Ideal for computer vision applications and gesture analysis."
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
