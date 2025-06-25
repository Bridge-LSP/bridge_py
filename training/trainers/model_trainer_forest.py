import json
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

# === CONFIGURACIÓN DE RUTAS ===
DATASET_PATH = 'dataset_bridge/landmarks_static.json'
MODEL_OUTPUT_PATH = 'models/forest_model_u.pkl'

# === FUNCIÓN: Cargar y preparar el dataset ===
def load_dataset():
    """
    Carga los datos desde el archivo JSON y construye los vectores de características.
    Se incluyen diferencias con landmarks previos si están disponibles.
    """
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
    """
    Entrena un modelo Random Forest con el dataset cargado, evalúa con test split
    y guarda el modelo entrenado.
    """
    X, y = load_dataset()
    print(f"📦 Dataset cargado: {len(X)} muestras, {len(y)} etiquetas")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"🧪 Datos de entrenamiento: {len(X_train)}, Datos de prueba: {len(X_test)}")

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    print("✅ Modelo entrenado correctamente")

    y_pred = model.predict(X_test)
    print("\n📈 Reporte de clasificación:")
    print(classification_report(y_test, y_pred))

    joblib.dump(model, MODEL_OUTPUT_PATH)
    print(f"\n💾 Modelo guardado en: {MODEL_OUTPUT_PATH}")

# === PUNTO DE ENTRADA ===
if __name__ == "__main__":
    train_model()