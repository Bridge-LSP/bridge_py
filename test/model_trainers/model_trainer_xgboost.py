import json
import numpy as np
import joblib
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

DATASET_PATH = 'data/landmarks_dataset.json'
MODEL_OUTPUT_PATH = 'models/xgb_model.pkl'

def load_dataset():
    with open(DATASET_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    X = []
    y = []

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

def train_model():
    X, y = load_dataset()
    print(f"Dataset cargado: {len(X)} muestras, {len(y)} etiquetas")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"Datos de entrenamiento: {len(X_train)}, Datos de prueba: {len(X_test)}")

    model = xgb.XGBClassifier(use_label_encoder=False, eval_metric='mlogloss', random_state=42)
    model.fit(X_train, y_train)
    print("Modelo XGBoost entrenado correctamente")

    y_pred = model.predict(X_test)
    print("\n📈 Reporte de clasificación:")
    print(classification_report(y_test, y_pred))

    joblib.dump(model, MODEL_OUTPUT_PATH)
    print(f"\n✅ Modelo guardado en {MODEL_OUTPUT_PATH}")

if __name__ == "__main__":
    train_model()