@echo off
REM Script de activación rápida del entorno virtual Bridge LSP
REM Uso: scripts\env.bat (desde la raíz del proyecto)

title Bridge LSP - Entorno Activado

REM Verificar si estamos en la raíz del proyecto
if not exist "myenv\Scripts\activate.bat" (
    echo ❌ Error: Ejecuta este script desde la raíz del proyecto bridge_py
    echo 📁 Ubicación actual: %CD%
    echo 📁 Ubicación esperada: ...\bridge_py\
    pause
    exit /b 1
)

REM Mostrar información del proyecto
echo 🌉 Bridge LSP - Activando entorno virtual
echo 📁 Directorio: %CD%
echo.

REM Activar entorno virtual
call myenv\Scripts\activate.bat

REM Confirmar activación
echo ✅ Entorno virtual activado
echo 🐍 Python: 
python --version
echo.
echo 🚀 Comandos disponibles:
echo   start_api.bat           - Iniciar servidor API
echo   python -m uvicorn api.api_main:app --host 0.0.0.0 --port 8000
echo   python download_bert_models.py
echo.
echo 💡 Tip: Usa 'deactivate' para salir del entorno virtual
echo.