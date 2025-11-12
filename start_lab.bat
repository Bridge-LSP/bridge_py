@echo off
title Bridge LSP Laboratory
echo 🚀 Iniciando Bridge LSP Laboratory
echo.
echo Activando entorno virtual...
call myenv\Scripts\activate.bat
echo.
echo Ejecutando laboratorio...
python main.py
echo.
echo 🔚 Laboratorio terminado
pause