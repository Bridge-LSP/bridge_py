from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import cv2
import numpy as np
import mediapipe as mp
from app.hand_tracker import create_hand_landmarker
from app.config import CAMERA_WIDTH, CAMERA_HEIGHT

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

hand_landmarker = create_hand_landmarker()

@app.post(
    "/detect",
    summary="Detect hand landmarks",
    description=(
        "Receives an image in multipart/form-data format, detects the hands present, "
        "and returns the 3D coordinates of the landmarks along with the hand classification (left or right)."
    ),
    response_description="A JSON with the detected landmarks and hand classification.",
)
async def detect_hand(file: UploadFile = File(...)):  
    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
    results = hand_landmarker.detect(mp_image)

    response_data = []

    if results.hand_landmarks:
        for idx, landmarks in enumerate(results.hand_world_landmarks):
            handedness = results.handedness[idx][0].category_name
            landmark_coords = [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in landmarks]

            response_data.append({
                "handedness": handedness,
                "landmarks": landmark_coords,
                "label": "open_hand"
            })

    return JSONResponse(content=response_data)