@echo off
REM Build script for Downunder Product Engine Windows Executable
REM Creates: dist/Downunder Product Engine.exe
REM Usage: build_executable.bat

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo  Downunder Product Engine - Executable Builder
echo ============================================================
echo.

REM Get the directory where this script is located
cd /d "%~dp0"

REM Step 1: Check Python availability
echo [1/4] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.x and add it to your system PATH
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo ✓ Found: %PYTHON_VERSION%
echo.

REM Step 2: Install PyInstaller if not present
echo [2/4] Checking PyInstaller...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller -q
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%i in ('python -m pip show pyinstaller ^| find "Version:"') do set PYINSTALLER_VERSION=%%i
echo ✓ PyInstaller ready (%PYINSTALLER_VERSION%)
echo.

REM Step 3: Convert logo PNG to ICO if not already done
echo [3/4] Preparing application icon...
if not exist "assets\logo.ico" (
    echo Converting logo.png to logo.ico...
    python convert_logo_to_ico.py
    if errorlevel 1 (
        echo WARNING: Logo conversion failed. Continuing without custom icon.
    )
) else (
    echo ✓ Icon file already exists
)
echo.

REM Step 4: Build executable with PyInstaller
echo [4/4] Building executable...
echo This may take 1-2 minutes...
echo.

REM Remove old build artifacts
if exist "build" rmdir /s /q "build" >nul 2>&1
if exist "dist" rmdir /s /q "dist" >nul 2>&1

REM Run PyInstaller (using python -m to avoid PATH issues)
python -m PyInstaller dpe_desktop.spec --distpath dist --workpath build --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed
    echo Check the output above for details
    pause
    exit /b 1
)

REM Verify the executable was created
if not exist "dist\Downunder Product Engine.exe" (
    echo.
    echo ERROR: Executable not found in dist\ directory
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  BUILD SUCCESSFUL
echo ============================================================
echo.
echo Executable created: dist\Downunder Product Engine.exe
echo.
echo NEXT STEPS:
echo   1. Copy the entire 'dist' folder to your deployment location
echo   2. Keep the 'output' folder alongside the executable
echo   3. The application will find config, assets, and database
echo.
echo TO LAUNCH:
echo   - Double-click: dist\Downunder Product Engine.exe
echo   - Shortcut: Create a shortcut to the .exe
echo.
echo TO DISTRIBUTE:
echo   - Zip the 'dist' folder for users
echo   - Include the 'output' folder if needed
echo.
pause
