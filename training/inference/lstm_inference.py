import cv2
import mediapipe as mp
import numpy as np
from tensorflow.keras.models import load_model
from collections import deque

SEQUENCE_LENGTH = 30
FEATURES_PER_FRAME = 63
MODEL_PATH = 'models/lstm_model.h5'
LABEL_MAP = {0: 'j', 1: 'll', 2: 'rr', 3: 'z', 4: 'ny'}

mp_hands = mp.solutions.hands

def extract_landmarks_from_frame(frame):
    with mp_hands.Hands(static_image_mode=False, max_num_hands=1) as hands:
        results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if results.multi_hand_landmarks:
            lm = results.multi_hand_landmarks[0]
            frame_features = []
            for point in lm.landmark:
                frame_features.extend([point.x, point.y, point.z])
            return frame_features
    return None

if __name__ == "__main__":
    model = load_model(MODEL_PATH)
    cap = cv2.VideoCapture(0)
    buffer_seq = deque(maxlen=SEQUENCE_LENGTH)

    with mp_hands.Hands(static_image_mode=False, max_num_hands=1) as hands:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.multi_hand_landmarks:
                lm = results.multi_hand_landmarks[0]
                frame_features = []
                for point in lm.landmark:
                    frame_features.extend([point.x, point.y, point.z])
                buffer_seq.append(frame_features)
            else:
                buffer_seq.append([0.0]*FEATURES_PER_FRAME)

            if len(buffer_seq) == SEQUENCE_LENGTH:
                seq = np.array(buffer_seq)
                pred = model.predict(np.expand_dims(seq, axis=0), verbose=0)
                pred_label = np.argmax(pred)
                label_text = LABEL_MAP.get(pred_label, "Desconocido")
                prob = float(pred[0][pred_label])
                if prob > 0.8:
                    cv2.putText(frame, f"Prediccion: {label_text} ({prob:.2f})", (10, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

            cv2.imshow("LSTM Camera Inference", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break

    cap.release()
    cv2.destroyAllWindows()