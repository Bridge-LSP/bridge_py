import os
import json
import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Masking
from tensorflow.keras.utils import to_categorical
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# === CONFIGURACIÓN GLOBAL ===
SEQUENCE_DIR = 'dataset_bridge/landmarks_dynamic'
MODEL_PATH = 'models/lstm_model.h5'
SEQUENCE_LENGTH = 30
FEATURES_PER_FRAME = 63

# === FUNCIÓN: Cargar secuencias y etiquetas ===
def load_sequences():
    """
    Carga los archivos .json con secuencias de landmarks.
    Asigna un índice numérico a cada etiqueta de clase.
    """
    X, y = [], []
    label_map = {}
    label_count = 0

    for fname in os.listdir(SEQUENCE_DIR):
        if fname.endswith('.json'):
            with open(os.path.join(SEQUENCE_DIR, fname)) as f:
                data = json.load(f)
                X.append(data['sequence'])
                label = data['label']
                if label not in label_map:
                    label_map[label] = label_count
                    label_count += 1
                y.append(label_map[label])

    return np.array(X), np.array(y), label_map

# === FUNCIÓN: Entrenar el modelo LSTM ===
def train_lstm():
    """
    Entrena un modelo LSTM con las secuencias cargadas.
    Evalúa el modelo y guarda los resultados.
    """
    X, y, label_map = load_sequences()
    y_cat = to_categorical(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_cat, test_size=0.2, random_state=42
    )

    model = Sequential([
        Masking(mask_value=0.0, input_shape=(SEQUENCE_LENGTH, FEATURES_PER_FRAME)),
        LSTM(64, return_sequences=True),
        LSTM(32),
        Dense(64, activation='relu'),
        Dense(y_cat.shape[1], activation='softmax')
    ])

    model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
    model.fit(X_train, y_train, epochs=30, batch_size=8, validation_data=(X_test, y_test))

    model.save(MODEL_PATH)
    print(f"\n✅ Modelo LSTM guardado en: {MODEL_PATH}")
    print(f"🗂️ Label map: {label_map}")

    # === EVALUACIÓN ===
    y_pred = model.predict(X_test)
    y_pred_labels = np.argmax(y_pred, axis=1)
    y_true_labels = np.argmax(y_test, axis=1)

    print("\n📈 Reporte de clasificación:")
    print(classification_report(y_true_labels, y_pred_labels))

# === PUNTO DE ENTRADA ===
if __name__ == "__main__":
    train_lstm()