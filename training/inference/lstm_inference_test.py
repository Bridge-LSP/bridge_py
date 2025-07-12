import cv2
import mediapipe as mp
import numpy as np
from tensorflow.keras.models import load_model

# === CONFIGURACIÓN Y RUTAS ===
SEQUENCE_LENGTH = 30
FEATURES_PER_FRAME = 63
MODEL_PATH = 'models/lstm_model.h5'
VIDEO_PATH = 'training/dataset_multimedia/dataset_dynamic/j/J LSP1.mp4'

mp_hands = mp.solutions.hands

# === EXTRACCIÓN DE SECUENCIA DE LANDMARKS DESDE VIDEO ===
def extract_landmark_sequence(video_path, sequence_length=SEQUENCE_LENGTH):
    """
    Procesa un video y extrae una secuencia de landmarks normalizada de longitud fija.
    """
    cap = cv2.VideoCapture(video_path)
    sequence = []

    with mp_hands.Hands(static_image_mode=False, max_num_hands=1) as hands:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            if results.multi_hand_landmarks:
                lm = results.multi_hand_landmarks[0]
                frame_features = []
                for point in lm.landmark:
                    frame_features.extend([point.x, point.y, point.z])
                sequence.append(frame_features)

            if len(sequence) == sequence_length:
                break

    cap.release()

    while len(sequence) < sequence_length:
        sequence.append([0.0] * FEATURES_PER_FRAME)

    return np.array(sequence)

# === PREDICCIÓN USANDO MODELO LSTM ===
if __name__ == "__main__":
    # Cargar modelo
    model = load_model(MODEL_PATH)

    # Obtener secuencia de landmarks desde video
    seq = extract_landmark_sequence(VIDEO_PATH)

    # Realizar predicción
    pred = model.predict(np.expand_dims(seq, axis=0))
    pred_label = np.argmax(pred)

    # Mostrar resultados
    print("Predicción (índice):", pred_label)
    print("Probabilidades:", pred)