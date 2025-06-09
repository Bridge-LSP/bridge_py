import cv2
import mediapipe as mp
from app.hand_tracker import create_hand_landmarker
from app.visualizer import draw_landmarks, draw_connections, draw_handedness_label
from app.config import CAMERA_WIDTH, CAMERA_HEIGHT
from app.utils import save_landmark_to_json
import joblib
import numpy as np
from collections import deque
from tensorflow.keras.models import load_model

MODEL_PATH_STATIC = 'models/forest_model_u.pkl'
MODEL_PATH_LSTM = 'models/lstm_model.h5'
SEQUENCE_LENGTH = 30
FEATURES_PER_FRAME = 63

# Mapa de etiquetas del modelo LSTM (ajusta según tu entrenamiento)
LSTM_LABEL_MAP = {0: 'j', 1: 'll', 2: 'rr', 3: 'z', 4: 'ñ'}

svm_model = joblib.load(MODEL_PATH_STATIC)
lstm_model = load_model(MODEL_PATH_LSTM)
buffer_seq = deque(maxlen=SEQUENCE_LENGTH)

def extract_features(landmarks):
    features = []
    for lm in landmarks:
        features.extend([lm.x, lm.y, lm.z])
    return np.array(features).reshape(1, -1)

def main():
    hand_landmarker = create_hand_landmarker(running_mode="VIDEO")
    cap = cv2.VideoCapture(0)
    cap.set(3, CAMERA_WIDTH)
    cap.set(4, CAMERA_HEIGHT)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        timestamp_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
        results = hand_landmarker.detect_for_video(mp_image, timestamp_ms)

        if results.hand_landmarks:
            for idx, landmarks in enumerate(results.hand_landmarks):
                draw_landmarks(frame, landmarks, frame.shape[1], frame.shape[0])
                draw_connections(frame, landmarks, frame.shape[1], frame.shape[0])
                handedness = results.handedness[idx][0].category_name.lower()
                draw_handedness_label(frame, handedness, idx)

                world_landmarks = results.hand_world_landmarks[idx]
                features = extract_features(world_landmarks)
                # Predicción estatica
                static_pred = svm_model.predict(features)[0]

                # Agrega features al buffer para LSTM
                buffer_seq.append(features.flatten().tolist())
                dynamic_pred = None
                prob = 0.0
                # Predicción dinamica solo si el buffer está lleno
                if len(buffer_seq) == SEQUENCE_LENGTH:
                    seq = np.array(buffer_seq).reshape(1, SEQUENCE_LENGTH, FEATURES_PER_FRAME)
                    pred = lstm_model.predict(seq, verbose=0)
                    pred_label = np.argmax(pred)
                    prob = float(pred[0][pred_label])
                    if prob > 0.8:  # Solo si la confianza es alta
                        dynamic_pred = LSTM_LABEL_MAP.get(pred_label, None)

                # Mostrar predicción dinamica si existe, si no la estatica
                if dynamic_pred:
                    text = f'{dynamic_pred.upper()} (dinamica, {prob:.2f})'
                else:
                    text = f'{static_pred.upper()} (estatica)'

                cv2.putText(frame, text, (10, 60 + idx * 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow("Hand Tracking Live", frame)
        if cv2.waitKey(5) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()