@echo off
title Bridge LSP API Server
echo 🌉 Iniciando Bridge LSP API Server
echo.
echo Activando entorno virtual...
call myenv\Scripts\activate.bat
echo.
echo 🌐 Obteniendo IP local...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4"') do (
    set "ip=%%a"
    set "ip=!ip: =!"
    if not "!ip!"=="" echo 📱 Acceso desde celular: http://!ip!:8000
)
echo.
echo 🚀 Iniciando servidor API en todas las interfaces (0.0.0.0:8000)
echo 🏠 Acceso local: http://localhost:8000
echo 📚 Documentación: http://localhost:8000/docs
echo 🛑 Para detener el servidor presiona Ctrl+C
echo.
python -m uvicorn api.api_main:app --reload --host 0.0.0.0 --port 8000