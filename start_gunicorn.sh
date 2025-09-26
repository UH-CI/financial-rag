#!/bin/bash

# Alternative production startup using Gunicorn with Uvicorn workers
# This provides better process management and zero-downtime reloads

set -e

# Configuration
HOST="0.0.0.0"
PORT="8200"
WORKERS="4"
LOG_LEVEL="info"
LOG_DIR="/home/exouser/RAG-system/logs"
PID_FILE="/home/exouser/RAG-system/gunicorn.pid"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# Create logs directory
mkdir -p "$LOG_DIR"

# Change to source directory
cd /home/exouser/RAG-system/src

# Activate virtual environment
if [ -f "myenv/bin/activate" ]; then
    print_info "Activating virtual environment..."
    source myenv/bin/activate
else
    print_error "Virtual environment not found"
    exit 1
fi

# Install gunicorn if not present
if ! command -v gunicorn &> /dev/null; then
    print_info "Installing gunicorn..."
    pip install gunicorn
fi

# Stop existing processes
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p $OLD_PID > /dev/null 2>&1; then
        print_info "Stopping existing gunicorn process..."
        kill $OLD_PID
        sleep 2
    fi
    rm -f "$PID_FILE"
fi

print_info "Starting Gunicorn with $WORKERS Uvicorn workers..."

# Start Gunicorn with Uvicorn workers
gunicorn api:app \
    --bind "$HOST:$PORT" \
    --workers "$WORKERS" \
    --worker-class uvicorn.workers.UvicornWorker \
    --log-level "$LOG_LEVEL" \
    --access-logfile "$LOG_DIR/access.log" \
    --error-logfile "$LOG_DIR/error.log" \
    --pid "$PID_FILE" \
    --daemon \
    --timeout 120 \
    --keepalive 5 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --preload \
    --worker-tmp-dir /dev/shm

if [ -f "$PID_FILE" ]; then
    print_success "Gunicorn started with PID: $(cat $PID_FILE)"
    print_success "API Server: http://$HOST:$PORT"
    print_info "To reload: kill -HUP \$(cat $PID_FILE)"
    print_info "To stop: kill \$(cat $PID_FILE)"
else
    print_error "Failed to start Gunicorn"
    exit 1
fi

