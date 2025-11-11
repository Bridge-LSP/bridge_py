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


### Para ejecutar el servidor WebSocket independiente:
```bash
python realtime_server.py --host 0.0.0.0 --port 8765
```

### Para ejecutar la API completa con WebSocket integrado:
```bash
uvicorn api.api_main:app --host 0.0.0.0 --port 8000 --reload
```

Para probar el cliente móvil de ejemplo:
python examples/mobile_client_example.py

✅ Lo que el Frontend Puede Hacer Ahora:
✅ Detección básica de gestos (ya existía)
✅ WebSocket tiempo real (ya existía)
✅ Autocorrección con sesiones (ya existía)
🆕 Construcción de palabras letra por letra
🆕 Corrección BERT en tiempo real
🆕 Completado automático de frases
🆕 Traducción multiidioma integrada
🆕 TTS mejorado para frases completas
🆕 Configuración de preferencias de usuario
🆕 Sistema de cache y estado persistente
¡El backend ahora tiene TODOS los endpoints que necesita el frontend Flutter para implementar el flujo completo de Bridge! 🚀

# Navegar al directorio
cd C:\GithubRepos\bridge_py

# Activar entorno virtual
.\myenv\Scripts\activate

# Iniciar servidor en todas las interfaces (CLAVE)
python -m uvicorn api.api_main:app --reload --host 0.0.0.0 --port 8000