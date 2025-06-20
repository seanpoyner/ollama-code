@echo off
REM Script to run ollama-code in Docker Desktop on Windows

echo Setting up Ollama Code for Docker Desktop...
echo ============================================
echo.

REM Check if Docker is running
docker info > nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

REM Build the image
echo Building Docker image...
docker build -f Dockerfile.desktop -t ollama-code:desktop .

if errorlevel 1 (
    echo ERROR: Failed to build Docker image
    pause
    exit /b 1
)

REM Create workspace directory if it doesn't exist
if not exist workspace mkdir workspace

REM Stop any existing container
echo Stopping any existing container...
docker stop ollama-code-desktop 2>nul
docker rm ollama-code-desktop 2>nul

REM Run the container
echo Starting container...
docker run -d ^
  --name ollama-code-desktop ^
  -p 11434:11434 ^
  -v "%cd%\workspace:/home/ollama/workspace" ^
  -e PYTHONUNBUFFERED=1 ^
  ollama-code:desktop

if errorlevel 1 (
    echo ERROR: Failed to start container
    pause
    exit /b 1
)

echo.
echo Container started successfully!
echo.
echo To use ollama-code:
echo   1. Open Docker Desktop
echo   2. Go to Containers
echo   3. Click on 'ollama-code-desktop'
echo   4. Click the 'Terminal' tab
echo   5. Run these commands:
echo.
echo      ollama serve ^&
echo      ollama pull llama3.2:3b
echo      cd /workspace
echo      ollama-code
echo.
echo Or use docker exec:
echo   docker exec -it ollama-code-desktop bash
echo.
pause