import cv2
from utils.hand_tracking_config import HAND_CONNECTIONS, LANDMARK_COLOR, CONNECTION_COLOR

# === DIBUJO DE LANDMARKS DE MANO ===
def draw_landmarks(frame, landmarks, width, height):
    """Dibuja los puntos clave (landmarks) de una mano."""
    for lm in landmarks:
        x = int(lm.x * width)
        y = int(lm.y * height)
        cv2.circle(frame, (x, y), 5, LANDMARK_COLOR, -1)

# === DIBUJO DE CONEXIONES ENTRE LANDMARKS ===
def draw_connections(frame, landmarks, width, height):
    """Dibuja las conexiones entre los puntos clave de la mano."""
    for start_idx, end_idx in HAND_CONNECTIONS:
        start = landmarks[start_idx]
        end = landmarks[end_idx]
        x1 = int(start.x * width)
        y1 = int(start.y * height)
        x2 = int(end.x * width)
        y2 = int(end.y * height)
        cv2.line(frame, (x1, y1), (x2, y2), CONNECTION_COLOR, 2)

# === ETIQUETA DE DOMINANCIA DE MANO ===
def draw_handedness_label(frame, handedness, index):
    """Muestra si es mano izquierda o derecha en pantalla."""
    text = f'{handedness} Hand'
    cv2.putText(frame, text, (10, 30 + index * 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, CONNECTION_COLOR, 2)