import json
import numpy as np
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix

# === CONFIGURACIÓN DE RUTAS ===
DATASET_PATH = 'dataset_bridge/landmarks_static.json'
MODEL_OUTPUT_PATH = 'models/forest_model_u.pkl'

# === FUNCIÓN: Cargar y preparar el dataset ===
def load_dataset():
    with open(DATASET_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    X, y = [], []

    for sample in data:
        landmarks = sample["landmarks"]
        features = []

        for lm in landmarks:
            features.extend([lm["x"], lm["y"], lm["z"]])

        if "prev_landmarks" in sample:
            prev_landmarks = sample["prev_landmarks"]
            for i, lm in enumerate(landmarks):
                features.extend([
                    lm["x"] - prev_landmarks[i]["x"],
                    lm["y"] - prev_landmarks[i]["y"],
                    lm["z"] - prev_landmarks[i]["z"]
                ])

        X.append(features)
        y.append(sample["label"])

    return np.array(X), np.array(y)

# === FUNCIÓN PRINCIPAL DE ENTRENAMIENTO ===
def train_model():
    X, y = load_dataset()
    print(f"📦 Dataset cargado: {len(X)} muestras, {len(y)} etiquetas")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"🧪 Datos de entrenamiento: {len(X_train)}, Datos de prueba: {len(X_test)}")

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    print("✅ Modelo entrenado correctamente")

    y_pred = model.predict(X_test)

    # === Reporte de clasificación
    print("\n📈 Reporte de clasificación:")
    print(classification_report(y_test, y_pred))

    # === Matriz de Confusión
    print("\n📊 Matriz de Confusión:")
    labels = sorted(list(set(y)))
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    plt.figure(figsize=(18, 14))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=labels, yticklabels=labels)
    plt.title("📊 Matriz de Confusión - Bridge V2 (Random Forest)")
    plt.xlabel("Predicción")
    plt.ylabel("Valor Real")
    plt.tight_layout()
    plt.show()

    # === Guardar el modelo
    joblib.dump(model, MODEL_OUTPUT_PATH)
    print(f"\n💾 Modelo guardado en: {MODEL_OUTPUT_PATH}")

# === PUNTO DE ENTRADA ===
if __name__ == "__main__":
    train_model()
