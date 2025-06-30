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

## ▶️ Define la versión Python 3.10.11 (dentro del entorno virtual, usualmente siempre despues de activar entorno)

```bash
py -3.10 -m venv myenv 
```


## 📦 Instalar dependencias

```bash
pip install -r requirements.txt
```

## 💾 Guardar dependencias (al actualizar o agregar paquetes)

```bash
pip freeze > requirements.txt
```

<br><br><br>


## 🚀 Ejecutar backend local con FastAPI

Este proyecto expone un backend que permite recibir imágenes y procesarlas con MediaPipe para retornar los landmarks de las manos detectadas.

### 📌 Comando para correr el backend local:

```bash
uvicorn api.api_main:app --reload
```

Esto abrirá el servidor en:

```text
http://127.0.0.1:8000
```

Y la interfaz de prueba automática de la API (Swagger UI) estará disponible en:

```text
http://127.0.0.1:8000/docs
```

<br><br><br>


## 🚀 Playground de Optimización en Bridge


### 📌 Generar Dataset Éstatico (Imagenes) y Dinámico (Videos)
```bash
python -m training.generate_datasets.generate_static_dataset
python -m training.generate_datasets.generate_dynamic_dataset

```

### 📌 Generar Modelo Forest/LSTM con nuestro Dataset Bridge Estático/Dinámico
```bash
python -m training.trainers.model_trainer_forest
python -m training.trainers.model_trainer_lstm
```