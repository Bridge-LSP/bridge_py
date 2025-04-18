import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from app.config import MODEL_PATH

def create_hand_landmarker():
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE, #este para integrar a flutter, ya que recibe fotogramas a procesar
        # running_mode=vision.RunningMode.VIDEO, <-- Este para las pruebas en python directas
        num_hands=2,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5
    )
    return vision.HandLandmarker.create_from_options(options)