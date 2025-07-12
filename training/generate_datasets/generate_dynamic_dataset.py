import os
import cv2
import mediapipe as mp
import numpy as np
import json

# === RUTAS Y PARÁMETROS DE CONFIGURACIÓN ===
RAW_VIDEO_DIR = 'training/dataset_multimedia/dataset_dynamic'
SEQUENCE_DIR = 'dataset_bridge/landmarks_dynamic'
SEQUENCE_LENGTH = 30 

mp_hands = mp.solutions.hands

# === EXTRACCIÓN DE SECUENCIA DE LANDMARKS DESDE UN VIDEO ===
def extract_landmark_sequence(video_path, sequence_length=SEQUENCE_LENGTH):
    """
    Extrae una secuencia de landmarks 3D (x, y, z) de un video con una sola mano.
    Devuelve una lista con longitud igual a `sequence_length`.
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

    # Rellenar con ceros si hay menos de `sequence_length` frames
    while len(sequence) < sequence_length:
        sequence.append([0.0] * 63)

    return sequence

# === PROCESAMIENTO DE TODOS LOS VIDEOS EN LA CARPETA ===
def process_all_videos():
    """
    Procesa todos los videos MP4 del directorio RAW_VIDEO_DIR,
    genera la secuencia de landmarks y la guarda en formato JSON en SEQUENCE_DIR.
    """
    os.makedirs(SEQUENCE_DIR, exist_ok=True)

    for root, dirs, files in os.walk(RAW_VIDEO_DIR):
        for fname in files:
            if fname.endswith('.mp4'):
                label = os.path.basename(root).lower()
                video_path = os.path.join(root, fname)
                sequence = extract_landmark_sequence(video_path)

                label_dir = os.path.join(SEQUENCE_DIR, label)
                os.makedirs(label_dir, exist_ok=True)

                out_path = os.path.join(label_dir, f"{fname}.json")
                with open(out_path, 'w') as f:
                    json.dump({'label': label, 'sequence': sequence}, f)

                print(f"Procesado {fname} → {out_path}")

if __name__ == "__main__":
    process_all_videos()