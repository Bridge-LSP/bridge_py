import os
import cv2
import mediapipe as mp
import numpy as np
import json

RAW_VIDEO_DIR = 'data/raw_videos'
SEQUENCE_DIR = 'data/dynamic_sequences'
SEQUENCE_LENGTH = 30 

mp_hands = mp.solutions.hands

def extract_landmark_sequence(video_path, sequence_length=SEQUENCE_LENGTH):
    cap = cv2.VideoCapture(video_path)
    sequence = []
    with mp_hands.Hands(static_image_mode=False, max_num_hands=1) as hands:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
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
        sequence.append([0.0]*63) 
    return sequence

def process_all_videos():
    os.makedirs(SEQUENCE_DIR, exist_ok=True)
    for root, dirs, files in os.walk(RAW_VIDEO_DIR):
        for fname in files:
            if fname.endswith('.mp4'):
                label = os.path.basename(root).lower() 
                video_path = os.path.join(root, fname)
                sequence = extract_landmark_sequence(video_path)
                out_path = os.path.join(SEQUENCE_DIR, f"{label}_{fname}.json")
                with open(out_path, 'w') as f:
                    json.dump({'label': label, 'sequence': sequence}, f)
                print(f"Procesado {fname} → {out_path}")

if __name__ == "__main__":
    process_all_videos()