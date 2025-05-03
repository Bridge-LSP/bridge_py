import cv2
import mediapipe as mp
from app.hand_tracker import create_hand_landmarker
from app.visualizer import draw_landmarks, draw_connections, draw_handedness_label
from app.config import CAMERA_WIDTH, CAMERA_HEIGHT
from app.utils import save_landmark_to_json
import joblib
import numpy as np

MODEL_PATH = 'models/svm_model_u.pkl'
svm_model = joblib.load(MODEL_PATH)

def extract_features(landmarks):
    features = []
    for lm in landmarks:
        features.extend([lm.x, lm.y, lm.z])
    return np.array(features).reshape(1, -1)

def main():
    hand_landmarker = create_hand_landmarker(running_mode="VIDEO")  # Cambiar a VIDEO
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
                prediction = svm_model.predict(features)[0]

                text = f'{prediction.upper()} ({handedness})'
                cv2.putText(frame, text, (10, 60 + idx * 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow("Hand Tracking Live", frame)
        if cv2.waitKey(5) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()