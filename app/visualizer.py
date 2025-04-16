import cv2
from app.config import HAND_CONNECTIONS, LANDMARK_COLOR, CONNECTION_COLOR

def draw_landmarks(frame, landmarks, width, height):
    for lm in landmarks:
        x = int(lm.x * width)
        y = int(lm.y * height)
        cv2.circle(frame, (x, y), 5, LANDMARK_COLOR, -1)

def draw_connections(frame, landmarks, width, height):
    for start_idx, end_idx in HAND_CONNECTIONS:
        start = landmarks[start_idx]
        end = landmarks[end_idx]
        x1 = int(start.x * width)
        y1 = int(start.y * height)
        x2 = int(end.x * width)
        y2 = int(end.y * height)
        cv2.line(frame, (x1, y1), (x2, y2), CONNECTION_COLOR, 2)

def draw_handedness_label(frame, handedness, index):
    text = f'{handedness} Hand'
    cv2.putText(frame, text, (10, 30 + index * 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, CONNECTION_COLOR, 2)