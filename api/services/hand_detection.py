import cv2
import numpy as np
import mediapipe as mp
from typing import List, Dict

def extract_features(landmarks) -> np.ndarray:
    """Extrae características de los landmarks de la mano."""
    features = []
    for lm in landmarks:
        features.extend([lm.x, lm.y, lm.z])
    return np.array(features).reshape(1, -1)

async def process_image_detection(
    file_contents: bytes, 
    hand_landmarker, 
    model
) -> List[Dict]:

    np_arr = np.frombuffer(file_contents, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
    results = hand_landmarker.detect(mp_image)

    response_data = []

    if results.hand_landmarks:
        for idx, landmarks in enumerate(results.hand_world_landmarks):
            handedness = results.handedness[idx][0].category_name.lower()
            features = extract_features(landmarks)
            prediction = model.predict(features)[0]

            response_data.append({
                "prediction": prediction,
                "handedness": handedness,
                "confidence": float(max(model.predict_proba(features)[0]))
            })

    return response_data