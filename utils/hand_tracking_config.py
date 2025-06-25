# === RUTA DEL MODELO ===
MODEL_PATH = 'models/hand_landmarker.task'

# === CONFIGURACIÓN DE CÁMARA ===
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

# === COLORES PARA DIBUJO DE LANDMARKS Y CONEXIONES ===
LANDMARK_COLOR = (0, 0, 255)        # Rojo para puntos
CONNECTION_COLOR = (255, 0, 0)      # Azul para líneas

# === CONEXIONES DE MANO (21 LANDMARKS) ===
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),           # Pulgar
    (0, 5), (5, 6), (6, 7), (7, 8),           # Índice
    (5, 9), (9, 10), (10, 11), (11, 12),      # Medio
    (9, 13), (13, 14), (14, 15), (15, 16),    # Anular
    (13, 17), (17, 18), (18, 19), (19, 20),   # Meñique
    (0, 17)                                   # Conexión base-puño
]