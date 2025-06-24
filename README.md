# Proyecto Bridge en Python🐍

Este proyecto utiliza un entorno virtual para evitar conflictos de dependencias entre paquetes.

## 🧪 Crear entorno virtual

```bash
python -m venv myenv
```

## ▶️ Activar entorno

```bash
myenv\Scripts\activate
```

## 📦 Instalar dependencias

```bash
pip install -r requirements.txt
```

## 💾 Guardar dependencias (al actualizar o agregar paquetes)

```bash
pip freeze > requirements.txt
```

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



### 📌 Generar Dataset Éstatico
```bash
python -m generate_datasets.generate_static_dataset
```

### 📌 Generar Dataset Dinámico
```bash
python -m generate_datasets.generate_dynamic_dataset
```



### 📌 Generar Modelo Forest y LSTM con el Dataset
- python -m trainers.model_trainer_forest
- python -m trainers.model_trainer_lstm