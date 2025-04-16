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

