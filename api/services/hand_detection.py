import cv2
import numpy as np
import mediapipe as mp
import time
from typing import List, Dict

def extract_features(landmarks) -> np.ndarray:
    features = []
    for lm in landmarks:
        features.extend([lm.x, lm.y, lm.z])
    return np.array(features).reshape(1, -1)

class PhraseTimer:
    def __init__(self, timeout_seconds=10):
        self.timeout_seconds = timeout_seconds
        self.last_detection_time = time.time()
        self.active = False

    def update(self, detected: bool):
        if detected:
            self.last_detection_time = time.time()
            self.active = True

    def check_timeout(self):
        if self.active and (time.time() - self.last_detection_time > self.timeout_seconds):
            self.active = False
            return True
        return False

async def process_image_detection(
    file_contents: bytes,
    hand_landmarker,
    model,
    phrase_timer: PhraseTimer = None
) -> List[Dict]:

    np_arr = np.frombuffer(file_contents, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
    results = hand_landmarker.detect(mp_image)

    response_data = []

    detected = False
    if results.hand_landmarks:
        detected = True
        for idx, landmarks in enumerate(results.hand_world_landmarks):
            handedness = results.handedness[idx][0].category_name.lower()
            features = extract_features(landmarks)
            prediction = model.predict(features)[0]

            response_data.append({
                "prediction": prediction,
                "handedness": handedness,
                "confidence": float(max(model.predict_proba(features)[0]))
            })

    if phrase_timer is not None:
        phrase_timer.update(detected)
        phrase_timer.check_timeout()

    return response_data