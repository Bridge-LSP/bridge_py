@echo off
REM Quick Test Script for WebSocket Detection Pipeline Diagnostics
REM This script helps run the diagnostic system quickly

echo ========================================================================
echo BRIDGE - WebSocket Detection Pipeline Diagnostic System
echo ========================================================================
echo.

REM Check if virtual environment exists
if not exist "myenv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found at myenv\
    echo Please run this script from the bridge_py root directory
    pause
    exit /b 1
)

echo Select test mode:
echo.
echo [1] Start Backend Server (Terminal 1)
echo [2] Start Visual WebSocket Client (Terminal 2)
echo [3] Start Backend + Client (both in new windows)
echo [4] View debug_ws_frame.jpg
echo [5] View logs side-by-side
echo.
set /p choice="Enter choice (1-5): "

if "%choice%"=="1" goto backend
if "%choice%"=="2" goto client
if "%choice%"=="3" goto both
if "%choice%"=="4" goto debug_frame
if "%choice%"=="5" goto logs

echo Invalid choice
pause
exit /b 1

:backend
echo.
echo ========================================================================
echo Starting Backend Server...
echo ========================================================================
echo Watch for these diagnostic messages:
echo   - [DEBUG][WS] Saved frame to debug_ws_frame.jpg
echo   - [DEBUG][MP] MediaPipe detected X hand(s)  ^<-- KEY INDICATOR
echo   - [DEBUG][RF] Prediction: X
echo.
echo Press CTRL+C to stop
echo ========================================================================
echo.
call myenv\Scripts\activate.bat
python -m uvicorn api.api_main:app --reload --host 0.0.0.0 --port 8000
goto end

:client
echo.
echo ========================================================================
echo Starting Visual WebSocket Client...
echo ========================================================================
echo Watch for these messages:
echo   - Session initialized: ^<session_id^>
echo   - WebSocket connected
echo   - Camera opened successfully
echo   - detection.letter: 'X' ^<-- KEY INDICATOR
echo.
echo Press Q in OpenCV window or CTRL+C to stop
echo ========================================================================
echo.
call myenv\Scripts\activate.bat
python main_ws_visual.py
goto end

:both
echo.
echo ========================================================================
echo Starting Backend and Client in separate windows...
echo ========================================================================
echo.
echo Backend window will open first, wait 3 seconds for startup
echo Then client window will open
echo.
echo IMPORTANT: Keep both windows visible to see diagnostics!
echo ========================================================================
echo.
start "BRIDGE Backend" cmd /k "call myenv\Scripts\activate.bat && python -m uvicorn api.api_main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak
start "BRIDGE Client" cmd /k "call myenv\Scripts\activate.bat && python main_ws_visual.py"
echo.
echo Both windows launched. Check:
echo   - Backend window for [DEBUG][MP] messages
echo   - Client window for detection.letter messages
echo   - OpenCV window for visual feedback
echo.
pause
goto end

:debug_frame
echo.
echo ========================================================================
echo Opening debug_ws_frame.jpg...
echo ========================================================================
if not exist "debug_ws_frame.jpg" (
    echo ERROR: debug_ws_frame.jpg not found
    echo.
    echo This file is created when the backend processes a frame.
    echo Please run the backend + client first to generate it.
    echo.
    pause
    exit /b 1
)
start debug_ws_frame.jpg
echo.
echo Compare this frame with what you see in:
echo   - main.py camera window
echo   - main_ws_visual.py camera window
echo.
echo Check:
echo   [X] Hand visible and clear?
echo   [X] Hand orientation correct (not upside down)?
echo   [X] Hand mirrored appropriately (mirror mode)?
echo   [X] Image quality good (not too dark/blurry)?
echo.
pause
goto end

:logs
echo.
echo ========================================================================
echo Viewing Recent Diagnostic Logs
echo ========================================================================
echo.
echo Opening documentation...
start IMPLEMENTATION_SUMMARY.md
start DIAGNOSTIC_ANALYSIS.md
echo.
echo Documentation opened in your default markdown viewer.
echo.
echo Key files:
echo   - IMPLEMENTATION_SUMMARY.md: Complete implementation details
echo   - DIAGNOSTIC_ANALYSIS.md: Root cause analysis and solutions
echo.
pause
goto end

:end
echo.
echo ========================================================================
echo Test script completed
echo ========================================================================
