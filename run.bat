@echo off
title Antigravity Subtitle Embedder
echo ======================================================
echo   Antigravity Subtitle Embedder is starting...
echo ======================================================
echo.

:: Change directory to where the BAT file is located
cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your system PATH.
    echo Please install Python and try again.
    pause
    exit /b
)

:: Check if Flask is installed, install it if missing
python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Flask is not installed. Installing Flask automatically...
    pip install flask
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install Flask automatically. Please install it manually: pip install flask
        pause
        exit /b
    )
)

:: Start Flask application
python app.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application crashed or failed to start.
    echo Please check if Flask is installed: pip install flask
    pause
)
