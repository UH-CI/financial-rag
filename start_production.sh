#!/bin/bash

# Production startup script for RAG System API
# Optimized for 4-worker deployment with proper process management

set -e  # Exit on any error

# Configuration
HOST="0.0.0.0"
PORT="8200"
WORKERS="4"
LOG_LEVEL="info"
LOG_DIR="/home/exouser/RAG-system/logs"
PID_FILE="/home/exouser/RAG-system/uvicorn.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Create logs directory
mkdir -p "$LOG_DIR"

# Change to source directory
cd /home/exouser/RAG-system/src

# Activate virtual environment
if [ -f "myenv/bin/activate" ]; then
    print_info "Activating virtual environment..."
    source myenv/bin/activate
    print_success "Virtual environment activated"
else
    print_error "Virtual environment not found at myenv/bin/activate"
    exit 1
fi

# Check if Redis is running (required for multi-worker fiscal note jobs)
if ! pgrep -x "redis-server" > /dev/null; then
    print_warning "Redis server not detected. Multi-worker fiscal note job tracking may not work properly."
    print_info "To start Redis: sudo systemctl start redis-server"
fi

# Stop existing uvicorn processes
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p $OLD_PID > /dev/null 2>&1; then
        print_info "Stopping existing uvicorn process (PID: $OLD_PID)..."
        kill $OLD_PID
        sleep 2
        if ps -p $OLD_PID > /dev/null 2>&1; then
            print_warning "Process still running, force killing..."
            kill -9 $OLD_PID
        fi
    fi
    rm -f "$PID_FILE"
fi

# Start uvicorn with multiple workers
print_info "Starting uvicorn with $WORKERS workers..."
print_info "Host: $HOST, Port: $PORT"
print_info "Log Level: $LOG_LEVEL"
print_info "Access logs: $LOG_DIR/access.log"
print_info "Error logs: $LOG_DIR/error.log"

# Production uvicorn command with optimized settings
nohup uvicorn api:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level "$LOG_LEVEL" \
    --access-log \
    --loop uvloop \
    --http httptools \
    --ws websockets \
    --lifespan on \
    --timeout-keep-alive 30 \
    --timeout-graceful-shutdown 30 \
    --backlog 2048 \
    > "$LOG_DIR/uvicorn.log" 2>&1 &

# Save PID
echo $! > "$PID_FILE"

# Wait a moment for startup
sleep 3

# Check if the process is running
if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
    print_success "Uvicorn started successfully with PID: $(cat $PID_FILE)"
    print_success "API Server running at: http://$HOST:$PORT"
    print_success "API Documentation: http://localhost:$PORT/docs"
    print_success "WebSocket endpoint: ws://localhost:$PORT/ws"
    print_info "Logs are being written to: $LOG_DIR/"
    print_info "To stop the server: kill \$(cat $PID_FILE)"
    print_info "To view logs: tail -f $LOG_DIR/uvicorn.log"
else
    print_error "Failed to start uvicorn"
    print_error "Check logs: cat $LOG_DIR/uvicorn.log"
    exit 1
fi
