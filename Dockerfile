# Dockerfile for testing ollama-code
FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Python and development tools
    python3.11 \
    python3.11-venv \
    python3-pip \
    python3-dev \
    build-essential \
    # Git for version control
    git \
    # Curl and wget for downloading
    curl \
    wget \
    # Node.js for MCP servers
    nodejs \
    npm \
    # Editor for testing file operations
    nano \
    vim \
    # Process management
    supervisor \
    # Utilities
    tree \
    htop \
    jq \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Create a non-root user for running ollama-code
RUN useradd -m -s /bin/bash ollama && \
    echo "ollama:ollama" | chpasswd && \
    usermod -aG sudo ollama

# Create necessary directories
RUN mkdir -p /home/ollama/.ollama/logs && \
    mkdir -p /home/ollama/.ollama/ollama-code && \
    mkdir -p /home/ollama/workspace && \
    chown -R ollama:ollama /home/ollama

# Switch to ollama user
USER ollama
WORKDIR /home/ollama

# Copy ollama-code repository
COPY --chown=ollama:ollama . /home/ollama/ollama-code/

# Create Python virtual environment
RUN python3 -m venv /home/ollama/ollama-code/venv

# Install ollama-code with all features
RUN cd /home/ollama/ollama-code && \
    . venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -e ".[all]"

# Create a startup script
RUN echo '#!/bin/bash\n\
echo "🐳 Ollama Code Docker Environment"\n\
echo "================================="\n\
echo ""\n\
echo "Available commands:"\n\
echo "  ollama-code    - Run Ollama Code CLI"\n\
echo "  ollama serve   - Start Ollama server (in another terminal)"\n\
echo "  cd /workspace  - Go to workspace directory"\n\
echo ""\n\
echo "To use MCP servers:"\n\
echo "  export GITHUB_PERSONAL_ACCESS_TOKEN=your_token"\n\
echo ""\n\
echo "Note: You need to start Ollama server first:"\n\
echo "  ollama serve &"\n\
echo "  ollama pull qwen2.5-coder:7b"\n\
echo ""\n\
' > /home/ollama/start.sh && chmod +x /home/ollama/start.sh

# Create ollama installation script
RUN echo '#!/bin/bash\n\
if [ ! -f /usr/local/bin/ollama ]; then\n\
    echo "📦 Installing Ollama..."\n\
    curl -fsSL https://ollama.com/install.sh | sh\n\
    echo "✅ Ollama installed!"\n\
else\n\
    echo "✅ Ollama already installed"\n\
fi\n\
' > /home/ollama/install-ollama.sh && chmod +x /home/ollama/install-ollama.sh

# Set up PATH
ENV PATH="/home/ollama/ollama-code/venv/bin:$PATH"

# Default working directory
WORKDIR /home/ollama/workspace

# Entry point
ENTRYPOINT ["/bin/bash", "-c", "/home/ollama/install-ollama.sh && /home/ollama/start.sh && exec /bin/bash"]