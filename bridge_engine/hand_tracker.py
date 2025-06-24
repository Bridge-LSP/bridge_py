import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from utils.hand_tracking_config import MODEL_PATH

def create_hand_landmarker(running_mode="IMAGE"):
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    try:
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=getattr(vision.RunningMode, running_mode),
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        return vision.HandLandmarker.create_from_options(options)
    except Exception as e:
        print(f"[WARNING] Failed to initialize with running_mode={running_mode}. Error: {e}")
        print("[INFO] Switching to running_mode='VIDEO'")
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        return vision.HandLandmarker.create_from_options(options)