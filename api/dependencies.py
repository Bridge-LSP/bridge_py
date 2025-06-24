import joblib
from engine_bridge.hand_tracker import create_hand_landmarker

hand_landmarker = create_hand_landmarker()
MODEL_PATH = 'models/forest_model_u.pkl'
forest_model = joblib.load(MODEL_PATH)

def get_hand_landmarker():
    return hand_landmarker

def get_forest_model():
    return forest_model