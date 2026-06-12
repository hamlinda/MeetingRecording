#!/bin/bash
set -e

# Formatting colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0;m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}       Starting Meeting Recorder Setup            ${NC}"
echo -e "${BLUE}==================================================${NC}"

# Check prerequisites
check_cmd() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}Error: $1 is required but not installed.${NC}"
        exit 1
    fi
}

echo -e "${GREEN}[1/5] Verifying System Prerequisites...${NC}"
check_cmd python3
check_cmd node
check_cmd npm

if ! command -v ffmpeg &> /dev/null; then
    echo -e "${YELLOW}Warning: ffmpeg not found in PATH. Audio muxing will not be available.${NC}"
fi

# Manage virtual environment
echo -e "${GREEN}[2/5] Setting up Python Virtual Environment...${NC}"
if [ -d "backend/venv/Scripts" ]; then
    echo -e "${YELLOW}Detected Windows virtual environment. Recreating for Linux...${NC}"
    rm -rf backend/venv
fi

# We use uv if available, as it can bypass ensurepip errors on Linux systems
if command -v uv &> /dev/null; then
    echo "Using 'uv' to create virtual environment..."
    uv venv backend/venv --clear
else
    if [ ! -d "backend/venv" ]; then
        echo "Creating virtual environment in backend/venv using standard python3..."
        python3 -m venv backend/venv
    fi
fi

# Activate venv and install dependencies
echo -e "${GREEN}[3/5] Installing Backend Dependencies...${NC}"
source backend/venv/bin/activate

# Filter out pyaudiowpatch on Linux since it is a Windows-only library
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Detected Linux. Bypassing Windows-only pyaudiowpatch..."
    # Create a temporary requirements file without pyaudiowpatch
    grep -v "pyaudiowpatch" backend/requirements.txt > backend/requirements_linux.txt
    
    if command -v uv &> /dev/null; then
        echo "Using 'uv' to install packages..."
        uv pip install -r backend/requirements_linux.txt
        uv pip install pyaudio || echo -e "${YELLOW}Warning: PyAudio failed to install. Offline microphone recording may not work without host portaudio libraries.${NC}"
    else
        pip install --upgrade pip
        pip install -r backend/requirements_linux.txt
        pip install pyaudio || echo -e "${YELLOW}Warning: PyAudio failed to install. Offline microphone recording may not work without host portaudio libraries.${NC}"
    fi
    rm -f backend/requirements_linux.txt
else
    if command -v uv &> /dev/null; then
        uv pip install -r backend/requirements.txt
    else
        pip install --upgrade pip
        pip install -r backend/requirements.txt
    fi
fi

# Frontend Setup
echo -e "${GREEN}[4/5] Building Frontend Assets...${NC}"
cd frontend
if [ ! -d "node_modules" ] || [ ! -x "node_modules/.bin/vite" ]; then
    echo "Installing/repairing npm dependencies..."
    npm install
fi
echo "Compiling React frontend..."
npm run build
cd ..

# Check Ollama status
echo -e "${GREEN}[5/5] Checking Local AI Services (Ollama)...${NC}"
if curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo -e "${GREEN}Ollama server found running at http://localhost:11434${NC}"
else
    echo -e "${YELLOW}Warning: Ollama server not detected at http://localhost:11434.${NC}"
    echo -e "${YELLOW}Please ensure Ollama is running and has the required models installed (e.g., llama3.1) for summarization and title features.${NC}"
fi

# Run service in background
echo -e "${GREEN}Starting the Web Service...${NC}"

# Stop any previously started instances tracking .backend.pid
if [ -f ".backend.pid" ]; then
    PID=$(cat .backend.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo -e "${YELLOW}Stopping previously started service (PID: $PID)...${NC}"
        kill "$PID" 2>/dev/null || true
        sleep 1
    fi
    rm -f .backend.pid
fi

# Dynamically find a free port starting from 8083
get_free_port() {
    local port=$1
    while ! python3 -c "import socket; s = socket.socket(); s.bind(('0.0.0.0', $port)); s.close()" &>/dev/null; do
        port=$((port+1))
    done
    echo $port
}

PORT=$(get_free_port 8083)
if [ "$PORT" -ne 8083 ]; then
    echo -e "${YELLOW}Port 8083 is in use. Selected free port: $PORT${NC}"
fi

export PRODUCTION=1
export PORT=$PORT
export HOST=0.0.0.0

nohup backend/venv/bin/python -u backend/main.py > out.log 2> err.log &
NEW_PID=$!
echo "$NEW_PID" > .backend.pid

echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}       Web Service Successfully Started!         ${NC}"
echo -e "${GREEN}==================================================${NC}"
echo -e "Access the web app at:   ${BLUE}http://127.0.0.1:$PORT${NC}"
echo -e "View backend logs via:  ${BLUE}tail -f out.log${NC} or ${BLUE}tail -f err.log${NC}"
echo -e "Stop the service via:   ${BLUE}./shutdown.sh${NC} or ${BLUE}kill $NEW_PID${NC}"
echo -e "${GREEN}==================================================${NC}"
