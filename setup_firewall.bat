@echo off
echo 🔥 Configurando Firewall para Bridge API
echo.
echo Creando regla de firewall para puerto 8000...
netsh advfirewall firewall add rule name="Bridge-API-8000" dir=in action=allow protocol=TCP localport=8000
echo.
if %errorlevel%==0 (
    echo ✅ Regla de firewall creada exitosamente
    echo 📱 El puerto 8000 ahora está accesible desde otros dispositivos
) else (
    echo ❌ Error: Este script necesita ejecutarse como Administrador
    echo 👤 Clic derecho → "Ejecutar como administrador"
)
echo.
pause