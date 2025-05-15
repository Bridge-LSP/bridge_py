# Proyecto Bridge en Python🐍

Este proyecto utiliza un entorno virtual para evitar conflictos de dependencias entre paquetes.

## 🧪 Crear entorno virtual

```bash
python -m venv myenv
```

## ▶️ Activar entorno

En Windows:

```bash
myenv\Scripts\activate
```

En macOS/Linux:

```bash
source myenv/bin/activate
```

## 📦 Instalar dependencias

```bash
pip install -r requirements.txt
```

## 💾 Guardar dependencias (al actualizar o agregar paquetes)

```bash
pip freeze > requirements.txt
```

## ❌ No olvidar

El entorno virtual (`myenv/`) no se sube al repositorio, ya está incluido en `.gitignore`.
Si corres varias veces el sistema, el JSON 'landmarks_data.json' se irá llenando con más entradas (no sobreescribe).

## 🚀 Ejecutar backend local con FastAPI

Este proyecto expone un backend que permite recibir imágenes y procesarlas con MediaPipe para retornar los landmarks de las manos detectadas.

### 📌 Comando para correr el backend local:

```bash
uvicorn app.api_server:app --reload
```

Esto abrirá el servidor en:

```text
http://127.0.0.1:8000
```

Y la interfaz de prueba automática de la API (Swagger UI) estará disponible en:

```text
http://127.0.0.1:8000/docs
```

### 🧪 Cómo probar:

1. Abre Postman o entra a `/docs`.
2. Usa el endpoint `POST /detect`.
3. Sube una imagen que contenga una o más manos.
4. Recibirás una respuesta JSON como:

```json
[
  {
    "handedness": "Right",
    "landmarks": [
      {"x": 0.1234, "y": -0.0456, "z": 0.0123},
      ...
    ],
    "label": "open_hand"
  }
]
```

### 📁 Dataset generado

Cada vez que se detecta una mano, se guardan sus coordenadas 3D en el archivo:

```bash
data/landmarks_data.json
```

Este archivo crece con cada ejecución y puede usarse como base para entrenar modelos de clasificación de gestos más adelante.

Para generar el dataset:
- python -m app.generate_dataset

Para generar el modelo con el dataset:
- python -m app.model_trainers.model_trainer_svc
- python -m app.model_trainers.model_trainer_forest
- python -m app.model_trainers.model_trainer_knn
