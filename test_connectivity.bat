@echo off
title Bridge API - Test de Conectividad
echo 🧪 Probando conectividad del Bridge API
echo.

echo 📍 Obteniendo IP local...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4"') do (
    set "ip=%%a"
    call :trim ip
    if not "!ip!"=="" (
        echo 🏠 IP Local: !ip!
        echo 📱 URL para celular: http://!ip!:8000
        echo 📚 Docs para celular: http://!ip!:8000/docs
        echo.
    )
)

echo 🔍 Verificando si el puerto 8000 está abierto...
netstat -an | findstr :8000 > nul
if %errorlevel%==0 (
    echo ✅ Puerto 8000 está en uso (servidor probablemente corriendo)
) else (
    echo ❌ Puerto 8000 no está en uso (inicia el servidor primero)
)

echo.
echo 🔥 Verificando regla de firewall...
netsh advfirewall firewall show rule name="Bridge-API-8000" > nul 2>&1
if %errorlevel%==0 (
    echo ✅ Regla de firewall existe
) else (
    echo ❌ Regla de firewall no existe
    echo 👤 Ejecuta setup_firewall.bat como administrador
)

echo.
echo 📝 PASOS PARA CONECTAR DESDE CELULAR:
echo 1. Ejecuta: start_api.bat
echo 2. Asegúrate de que firewall permita conexiones
echo 3. Desde tu celular, accede a: http://!ip!:8000/docs
echo.
pause
goto :eof

:trim
setlocal enabledelayedexpansion
set "str=!%1!"
for /f "tokens=* delims= " %%a in ("!str!") do set "str=%%a"
for /l %%a in (1,1,100) do if "!str:~-1!"==" " set "str=!str:~0,-1!"
endlocal & set "%1=%str%"
goto :eof