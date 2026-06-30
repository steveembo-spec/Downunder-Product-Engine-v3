@echo off
REM Launch Downunder Product Engine Desktop Application
REM This script sets the working directory and launches the Python desktop app

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.x and ensure it is added to your system PATH.
    echo.
    pause
    exit /b 1
)

REM Check if the desktop app exists
if not exist "desktop\app.py" (
    echo.
    echo ERROR: desktop\app.py not found.
    echo Make sure you are running this from the project root directory.
    echo.
    pause
    exit /b 1
)

REM Launch the application
python desktop/app.py

REM Only show window if there was an error (errorlevel != 0)
if errorlevel 1 (
    echo.
    echo ERROR: The application encountered an error and has exited.
    echo.
    pause
)

exit /b %ERRORLEVEL%
