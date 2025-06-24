from pydantic import BaseModel
from typing import List, Optional

class HandDetectionResponse(BaseModel):
    prediction: str
    handedness: str
    confidence: float

class TTSRequest(BaseModel):
    texto: str
    idioma: str = "es"

class HealthResponse(BaseModel):
    status: str
    version: str