#!/bin/bash

# Production setup script for RAG System
# Sets up the environment for production deployment

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

print_info "Setting up RAG System for production deployment..."

# Check if we're in the right directory
if [ ! -f "src/api.py" ]; then
    print_error "Please run this script from the RAG-system root directory"
    exit 1
fi

# Create necessary directories
print_info "Creating directories..."
mkdir -p logs
mkdir -p src/fiscal_notes/generation/data
mkdir -p src/documents/storage_documents
mkdir -p src/documents/extracted_text
mkdir -p src/documents/chunked_text

# Install system dependencies (if needed)
print_info "Checking system dependencies..."

# Check for Redis
if ! command -v redis-server &> /dev/null; then
    print_warning "Redis not found. Installing..."
    sudo apt-get update
    sudo apt-get install -y redis-server
    sudo systemctl enable redis-server
    sudo systemctl start redis-server
    print_success "Redis installed and started"
else
    print_success "Redis is available"
    if ! pgrep -x "redis-server" > /dev/null; then
        print_info "Starting Redis..."
        sudo systemctl start redis-server
    fi
fi

# Check for Chrome (needed for web scraping)
if ! command -v google-chrome &> /dev/null; then
    print_warning "Google Chrome not found. This is needed for document scraping."
    print_info "Chrome is available but may need additional setup for headless operation"
fi

# Setup Python environment
print_info "Setting up Python environment..."
cd src

if [ ! -d "myenv" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv myenv
fi

print_info "Activating virtual environment and installing dependencies..."
source myenv/bin/activate

# Upgrade pip first
pip install --upgrade pip

# Install production dependencies
pip install -r requirements.txt

# Install additional production packages
print_info "Installing additional production packages..."
pip install gunicorn uvloop httptools

print_success "Python dependencies installed"

# Setup environment variables
print_info "Setting up environment variables..."
if [ ! -f ".env" ]; then
    print_warning ".env file not found. Creating template..."
    cat > .env << 'EOF'
# API Keys
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Database
CHROMA_DB_PATH=chroma_db/data

# Server
HOST=0.0.0.0
PORT=8200
WORKERS=4
LOG_LEVEL=info

# Security (set to False in production)
DEBUG=False
EOF
    print_warning "Please edit .env file with your actual API keys"
else
    print_success ".env file exists"
fi

# Setup logging
print_info "Configuring logging..."
cd ..  # Back to root directory

# Make scripts executable
chmod +x start_production.sh
chmod +x start_gunicorn.sh

print_success "Production setup completed!"
print_info ""
print_info "🚀 To start the server:"
print_info "   Option 1 (Recommended): ./start_production.sh"
print_info "   Option 2 (Alternative):  ./start_gunicorn.sh"
print_info ""
print_info "📋 To setup systemd service:"
print_info "   sudo cp rag-api.service /etc/systemd/system/"
print_info "   sudo systemctl daemon-reload"
print_info "   sudo systemctl enable rag-api"
print_info "   sudo systemctl start rag-api"
print_info ""
print_info "📊 To monitor:"
print_info "   tail -f logs/uvicorn.log"
print_info "   systemctl status rag-api"
print_info ""
print_warning "⚠️  Remember to:"
print_warning "   1. Edit src/.env with your actual API keys"
print_warning "   2. Configure firewall for port 8200"
print_warning "   3. Setup reverse proxy (nginx) if needed"
