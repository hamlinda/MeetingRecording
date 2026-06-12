#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0;m'

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}       Stopping Meeting Recorder Service          ${NC}"
echo -e "${BLUE}==================================================${NC}"

STOPPED=false

if [ -f ".backend.pid" ]; then
    PID=$(cat .backend.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping background service (PID: $PID)..."
        kill "$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null || true
        STOPPED=true
        sleep 1
    fi
    rm -f .backend.pid
fi

# Fallback: kill anything running backend/main.py
BACKEND_PIDS=$(pgrep -f "backend/main.py" || true)
for p in $BACKEND_PIDS; do
    echo "Stopping background python process $p..."
    kill "$p" 2>/dev/null || kill -9 "$p" 2>/dev/null || true
    STOPPED=true
done

if [ "$STOPPED" = true ]; then
    echo -e "${GREEN}Service successfully stopped.${NC}"
else
    echo -e "${YELLOW}No running Meeting Recorder service detected.${NC}"
fi
echo -e "${BLUE}==================================================${NC}"
