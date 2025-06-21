#!/bin/bash
# Entrypoint script for Docker Desktop

# Ensure log directory exists
mkdir -p /home/ollama/.ollama/logs

# Show startup message
/home/ollama/startup.sh

# Start Ollama in the background with proper environment
echo "Starting Ollama server..."
OLLAMA_HOST=0.0.0.0:11434 ollama serve > /home/ollama/.ollama/logs/ollama.log 2>&1 &
OLLAMA_PID=$!

# Wait for Ollama to fully start
echo "Waiting for Ollama to start..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "✅ Ollama server started successfully (PID: $OLLAMA_PID)"
        echo ""
        echo "You can now run: ollama pull llama3.2:3b"
        echo "Then: cd /workspace && ollama-code"
        break
    fi
    sleep 1
done

if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "❌ Failed to start Ollama server"
    echo "Check logs: cat /home/ollama/.ollama/logs/ollama.log"
    tail -n 20 /home/ollama/.ollama/logs/ollama.log
fi
echo ""

# Keep container running
tail -f /dev/null