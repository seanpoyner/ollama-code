#!/bin/bash
# Script to run ollama-code in Docker Desktop

echo "🐳 Setting up Ollama Code for Docker Desktop..."
echo "============================================"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Build the image
echo "📦 Building Docker image..."
docker build -f Dockerfile.desktop -t ollama-code:desktop .

if [ $? -ne 0 ]; then
    echo "❌ Failed to build Docker image"
    exit 1
fi

# Create workspace directory if it doesn't exist
mkdir -p workspace

# Stop any existing container
echo "🛑 Stopping any existing container..."
docker stop ollama-code-desktop 2>/dev/null
docker rm ollama-code-desktop 2>/dev/null

# Run the container
echo "🚀 Starting container..."
docker run -d \
  --name ollama-code-desktop \
  -p 11434:11434 \
  -v "$(pwd)/workspace:/home/ollama/workspace" \
  -e PYTHONUNBUFFERED=1 \
  ollama-code:desktop

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Container started successfully!"
    echo ""
    echo "To use ollama-code:"
    echo "  1. Open Docker Desktop"
    echo "  2. Go to Containers"
    echo "  3. Click on 'ollama-code-desktop'"
    echo "  4. Click the 'Terminal' tab"
    echo "  5. Run these commands:"
    echo ""
    echo "     ollama serve &"
    echo "     ollama pull llama3.2:3b"
    echo "     cd /workspace"
    echo "     ollama-code"
    echo ""
    echo "Or use docker exec:"
    echo "  docker exec -it ollama-code-desktop bash"
    echo ""
else
    echo "❌ Failed to start container"
    exit 1
fi