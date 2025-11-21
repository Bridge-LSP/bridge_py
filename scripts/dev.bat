@echo off
REM Script avanzado de desarrollo Bridge LSP
REM Activa entorno + muestra información útil + shortcuts

title Bridge LSP - Desarrollo

if not exist "myenv\Scripts\activate.bat" (
    echo ❌ Error: Ejecuta desde la raíz del proyecto
    pause & exit /b 1
)

cls
echo ═══════════════════════════════════════════════════════════════
echo 🌉 BRIDGE LSP - ENTORNO DE DESARROLLO
echo ═══════════════════════════════════════════════════════════════
echo.

REM Activar entorno
call myenv\Scripts\activate.bat

echo 📊 INFORMACIÓN DEL PROYECTO:
echo    📁 Directorio: %CD%
python --version 2>nul && echo    🐍 Python: Disponible || echo    ❌ Python: No encontrado
echo    🌐 Puerto API: 8000
echo.

echo 🚀 COMANDOS RÁPIDOS:
echo    [1] Iniciar servidor API    : start_api.bat
echo    [2] Servidor con reload     : python -m uvicorn api.api_main:app --reload --host 0.0.0.0 --port 8000  
echo    [3] Descargar modelos BERT  : python download_bert_models.py
echo    [4] Ver IP para móvil       : ipconfig ^| findstr IPv4
echo    [5] Ver estructura          : tree /F /A
echo.

echo 💡 TIPS DE DESARROLLO:
echo    • Usa Ctrl+C para detener el servidor
echo    • Documentación API: http://localhost:8000/docs
echo    • Logs en tiempo real con --reload
echo    • 'deactivate' para salir del entorno
echo.
echo ═══════════════════════════════════════════════════════════════