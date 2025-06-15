@echo off
REM Installation script for ollama-code on Windows

echo ====================================
echo  Ollama Code Windows Installer
echo ====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

echo Installing required dependencies...
echo.

REM Install all dependencies including ChromaDB
echo Installing ollama...
pip install ollama
echo Installing rich...
pip install rich
echo Installing requests...
pip install requests
echo Installing pyyaml...
pip install pyyaml
echo Installing chromadb (this may take a moment)...
pip install chromadb

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies
    echo.
    echo If you see an "externally-managed-environment" error, try:
    echo   1. Create a virtual environment: python -m venv venv
    echo   2. Activate it: venv\Scripts\activate
    echo   3. Run this script again
    echo.
    echo Or install with: pip install --user ollama rich requests pyyaml chromadb
    pause
    exit /b 1
)

echo.
echo ====================================
echo  Installation Complete!
echo ====================================
echo.
echo To run ollama-code:
echo   python ollama-code.py
echo.
echo Make sure Ollama is running:
echo   ollama serve
echo.
echo For vector search, pull the embedding model:
echo   ollama pull nomic-embed-text
echo.
pause