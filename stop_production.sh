#!/bin/bash

# Production stop script for RAG System API
# Safely stops all uvicorn workers and cleans up

set -e  # Exit on any error

# Configuration
PORT="8200"
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

print_info "Stopping RAG System API Server..."

# Find all processes using the port
PIDS_ON_PORT=$(lsof -t -i:$PORT 2>/dev/null || true)

if [ ! -z "$PIDS_ON_PORT" ]; then
    print_info "Found processes using port $PORT: $PIDS_ON_PORT"
    
    # Try graceful shutdown first
    for pid in $PIDS_ON_PORT; do
        if ps -p $pid > /dev/null 2>&1; then
            print_info "Gracefully stopping process $pid..."
            kill -TERM $pid 2>/dev/null || true
        fi
    done
    
    # Wait for graceful shutdown
    print_info "Waiting for graceful shutdown..."
    sleep 5
    
    # Force kill any remaining processes
    REMAINING_PIDS=$(lsof -t -i:$PORT 2>/dev/null || true)
    if [ ! -z "$REMAINING_PIDS" ]; then
        print_warning "Force killing remaining processes: $REMAINING_PIDS"
        for pid in $REMAINING_PIDS; do
            if ps -p $pid > /dev/null 2>&1; then
                kill -9 $pid 2>/dev/null || true
            fi
        done
        sleep 2
    fi
    
    print_success "All processes on port $PORT have been stopped"
else
    print_info "No processes found using port $PORT"
fi

# Clean up PID file
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p $OLD_PID > /dev/null 2>&1; then
        print_info "Stopping process from PID file (PID: $OLD_PID)..."
        kill -TERM $OLD_PID 2>/dev/null || true
        sleep 2
        if ps -p $OLD_PID > /dev/null 2>&1; then
            print_warning "Force killing PID file process..."
            kill -9 $OLD_PID 2>/dev/null || true
        fi
    fi
    rm -f "$PID_FILE"
    print_success "PID file cleaned up"
fi

# Final verification
if lsof -i:$PORT > /dev/null 2>&1; then
    print_error "Port $PORT is still in use after cleanup"
    print_error "Manual check required: lsof -i:$PORT"
    exit 1
else
    print_success "RAG System API Server stopped successfully"
    print_success "Port $PORT is now available"
fi
