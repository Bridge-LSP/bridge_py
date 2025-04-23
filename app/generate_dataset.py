import os
import cv2
import json
import mediapipe as mp
from tqdm import tqdm
from app.hand_tracker import create_hand_landmarker

INPUT_FOLDER = 'data/raw_images'
OUTPUT_JSON = 'data/landmarks_dataset.json'

def generate_dataset_from_folder():
    hand_landmarker = create_hand_landmarker()
    mp_image_class = mp.Image
    dataset = []

    for label_folder in os.listdir(INPUT_FOLDER):
        label_path = os.path.join(INPUT_FOLDER, label_folder)
        if not os.path.isdir(label_path):
            continue  # Ignorar si no es carpeta

        for filename in tqdm(os.listdir(label_path), desc=f'Procesando {label_folder}'):
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue

            filepath = os.path.join(label_path, filename)

            image = cv2.imread(filepath)
            if image is None:
                print(f"⚠️ Error al leer {filepath}")
                continue

            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            mp_image = mp_image_class(image_format=mp.ImageFormat.SRGB, data=rgb_image)
            results = hand_landmarker.detect(mp_image)

            if results.hand_world_landmarks:
                for idx, landmarks in enumerate(results.hand_world_landmarks):
                    handedness = results.handedness[idx][0].category_name

                    dataset.append({
                        "label": label_folder,
                        "handedness": handedness,
                        "landmarks": [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in landmarks]
                    })

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2)
    print(f"\n✅ Dataset generado en {OUTPUT_JSON} con {len(dataset)} muestras.")

if __name__ == "__main__":
    generate_dataset_from_folder()
