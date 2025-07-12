import os
import cv2
import json
import mediapipe as mp
from tqdm import tqdm
from engine_bridge.hand_tracker import create_hand_landmarker

# === RUTAS Y PARÁMETROS ===
INPUT_FOLDER = 'training/dataset_multimedia/dataset_static'
OUTPUT_JSON = 'dataset_bridge/landmarks_static.json'

# === GENERACIÓN DEL DATASET A PARTIR DE IMÁGENES Y VIDEOS ===
def generate_dataset_from_folder(label_filter=None):
    """Procesa imágenes y videos de INPUT_FOLDER para generar landmarks y guardarlos en un JSON."""
    hand_landmarker_image = create_hand_landmarker(running_mode="IMAGE")
    hand_landmarker_video = create_hand_landmarker(running_mode="VIDEO")
    dataset = []

    for label_folder in os.listdir(INPUT_FOLDER):
        if label_filter and label_folder != label_filter:
            continue
        label_path = os.path.join(INPUT_FOLDER, label_folder)
        if not os.path.isdir(label_path):
            continue

        for filename in tqdm(os.listdir(label_path), desc=f'Procesando {label_folder}'):
            filepath = os.path.join(label_path, filename)
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                process_image(filepath, label_folder, hand_landmarker_image, dataset)
            elif filename.lower().endswith('.mp4'):
                process_video(filepath, label_folder, hand_landmarker_video, dataset)

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2)
    print(f"\n✅ Dataset generado en {OUTPUT_JSON} con {len(dataset)} muestras.")

# === PROCESAMIENTO DE IMÁGENES ESTÁTICAS ===
def process_image(filepath, label_folder, hand_landmarker, dataset):
    image = cv2.imread(filepath)
    if image is None:
        print(f"⚠️ Error al leer {filepath}")
        return

    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
    results = hand_landmarker.detect(mp_image)

    if results.hand_world_landmarks:
        for idx, landmarks in enumerate(results.hand_world_landmarks):
            handedness = results.handedness[idx][0].category_name
            dataset.append({
                "label": label_folder,
                "handtype": handedness.lower(),
                "landmarks": [
                    {"id": i, "x": lm.x, "y": lm.y, "z": lm.z} for i, lm in enumerate(landmarks)
                ]
            })

# === PROCESAMIENTO DE FRAMES DE VIDEO ===
def process_video(filepath, label_folder, hand_landmarker, dataset):
    cap = cv2.VideoCapture(filepath)
    prev_landmarks = None
    last_timestamp_ms = 0 
    frame_count = 0 

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        timestamp_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
        print(f"[DEBUG] Frame {frame_count}: Original timestamp_ms = {timestamp_ms}")

        if timestamp_ms <= last_timestamp_ms:
            timestamp_ms = last_timestamp_ms + 1
            print(f"[DEBUG] Frame {frame_count}: Adjusted timestamp_ms = {timestamp_ms}")

        if timestamp_ms % 200 == 0:
            print(f"[DEBUG] Frame {frame_count}: Processing frame with timestamp_ms = {timestamp_ms}")
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            results = hand_landmarker.detect_for_video(mp_image, timestamp_ms=timestamp_ms)

            if results.hand_world_landmarks:
                for idx, landmarks in enumerate(results.hand_world_landmarks):
                    handedness = results.handedness[idx][0].category_name
                    current_landmarks = [
                        {"id": i, "x": lm.x, "y": lm.y, "z": lm.z} for i, lm in enumerate(landmarks)
                    ]

                    sample = {
                        "label": label_folder,
                        "handtype": handedness.lower(),
                        "landmarks": current_landmarks
                    }
                    if prev_landmarks:
                        sample["prev_landmarks"] = prev_landmarks

                    dataset.append(sample)

                prev_landmarks = current_landmarks

        last_timestamp_ms = timestamp_ms
        frame_count += 1 

    cap.release()
    print(f"[DEBUG] Video {filepath} procesado con éxito.")

if __name__ == "__main__":
    # Deja None para procesar todas las letras, o pon 'a', 'b', etc.
    generate_dataset_from_folder(label_filter=None)