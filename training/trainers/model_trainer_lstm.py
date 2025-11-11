import os
import json
import numpy as np
import tensorflow as tf
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

SEQUENCE_DIR = 'dataset_bridge/landmarks_dynamic'
MODEL_PATH = 'models/lstm_model.h5'
SEQUENCE_LENGTH = 30
FEATURES_PER_FRAME = 63

def load_sequences():

    X, y = [], []
    label_map = {}
    label_count = 0

    for root, _, files in os.walk(SEQUENCE_DIR):
        label = os.path.basename(root)
        if label == os.path.basename(SEQUENCE_DIR):
            continue

        if label not in label_map:
            label_map[label] = label_count
            label_count += 1

        for fname in files:
            if fname.endswith('.json'):
                path = os.path.join(root, fname)
                with open(path, encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                        if 'sequence' not in data or not data['sequence']:
                            continue
                        X.append(data['sequence'])
                        y.append(label_map[label])
                    except json.JSONDecodeError:
                        print(f"⚠️ Archivo JSON inválido: {path}")
                        continue

    return np.array(X), np.array(y), label_map

def train_lstm():

    X, y, label_map = load_sequences()

    if len(X) == 0 or len(y) == 0:
        print("❌ No se encontraron secuencias válidas para entrenamiento.")
        return

    y_cat = tf.keras.utils.to_categorical(y)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_cat, test_size=0.2, random_state=42
    )

    model = tf.keras.Sequential([
        tf.keras.layers.Masking(mask_value=0.0, input_shape=(SEQUENCE_LENGTH, FEATURES_PER_FRAME)),
        tf.keras.layers.LSTM(64, return_sequences=True),
        tf.keras.layers.LSTM(32),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(y_cat.shape[1], activation='softmax')
    ])

    model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
    model.fit(X_train, y_train, epochs=30, batch_size=8, validation_data=(X_test, y_test))

    model.save(MODEL_PATH)
    print(f"\n✅ Modelo LSTM guardado en: {MODEL_PATH}")
    print(f"🗂️ Label map: {label_map}")

    y_pred = model.predict(X_test)
    y_pred_labels = np.argmax(y_pred, axis=1)
    y_true_labels = np.argmax(y_test, axis=1)

    print("\n📈 Reporte de clasificación:")
    print(classification_report(y_true_labels, y_pred_labels))

if __name__ == "__main__":
    train_lstm()