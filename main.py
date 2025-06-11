import cv2
import mediapipe as mp
from app.hand_tracker import create_hand_landmarker
from app.visualizer import draw_landmarks, draw_connections, draw_handedness_label
from app.config import CAMERA_WIDTH, CAMERA_HEIGHT
from app.utils import save_landmark_to_json
import joblib
import numpy as np
import time

MODEL_PATH = 'models/forest_model_u.pkl'
svm_model = joblib.load(MODEL_PATH)

current_word = ""
last_prediction = None
last_time = 0
COOLDOWN_TIME = 1.5 
letra_actual = ""
palabras_completadas = []
buttons = {} 

def get_dynamic_buttons(frame_height):
    bottom_y1 = frame_height - 60
    bottom_y2 = frame_height - 20
    return {
        "aceptar_letra": (10, bottom_y1, 220, bottom_y2),
        "aceptar_palabra": (240, bottom_y1, 450, bottom_y2),
        "nueva_palabra": (470, bottom_y1, 680, bottom_y2)
    }


def extract_features(landmarks):
    features = []
    for lm in landmarks:
        features.extend([lm.x, lm.y, lm.z])
    return np.array(features).reshape(1, -1)

def draw_buttons(frame):
    global buttons
    frame_height = frame.shape[0]
    buttons = get_dynamic_buttons(frame_height)
    for key, (x1, y1, x2, y2) in buttons.items():
        cv2.rectangle(frame, (x1, y1), (x2, y2), (200, 200, 200), -1)
        label = {
            "aceptar_letra": "Aceptar Letra",
            "aceptar_palabra": "Aceptar Palabra",
            "nueva_palabra": "Nueva Palabra"
        }[key]
        cv2.putText(frame, label, (x1 + 10, y2 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)


def handle_click(event, x, y, flags, param):
    global current_word, letra_actual, palabras_completadas
    if event == cv2.EVENT_LBUTTONDOWN:
        for key, (x1, y1, x2, y2) in buttons.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                if key == "aceptar_letra" and letra_actual:
                    current_word += letra_actual
                elif key == "aceptar_palabra" and current_word:
                    palabras_completadas.append(current_word)
                elif key == "nueva_palabra":
                    current_word = ""
                    letra_actual = ""

def main():
    global current_word, last_prediction, last_time, letra_actual

    hand_landmarker = create_hand_landmarker(running_mode="VIDEO")
    cap = cv2.VideoCapture(0)
    cap.set(3, CAMERA_WIDTH)
    cap.set(4, CAMERA_HEIGHT)

    cv2.namedWindow("Hand Tracking Live")
    cv2.setMouseCallback("Hand Tracking Live", handle_click)

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

                world_landmarks = results.hand_world_landmarks[idx]
                features = extract_features(world_landmarks)
                prediction = svm_model.predict(features)[0]

                now = time.time()
                if prediction != last_prediction and (now - last_time) > COOLDOWN_TIME:
                    letra_actual = prediction.upper()
                    last_prediction = prediction
                    last_time = now

                frame_height = frame.shape[0]
                text_y = frame_height - 80 
                text = f"Letra: {letra_actual}"
                (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
                cv2.rectangle(frame, (10, text_y - text_height - 10), (10 + text_width + 10, text_y + 10), (255, 255, 255), -1)

                cv2.putText(frame, text, (15, text_y),     
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (90, 90, 90), 2)

        cv2.putText(frame, f"Palabra: {current_word}", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 100, 255), 2)

        y_offset = 80
        for i, palabra in enumerate(palabras_completadas[-3:]):
            cv2.putText(frame, f"{i+1}. {palabra}", (10, y_offset + i * 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 50, 50), 2)

        draw_buttons(frame)
        cv2.imshow("Hand Tracking Live", frame)

        key = cv2.waitKey(5) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("r"):
            current_word = ""
            letra_actual = ""

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
