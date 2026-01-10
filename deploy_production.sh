#!/bin/bash

# Production deployment script using Docker Compose
# This script can be run manually or called from Jenkins

set -e  # Exit on any error

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

print_info "🚀 Starting Production Deployment with Docker Compose"
print_info "======================================================"

# Check if Docker and Docker Compose are available
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed or not in PATH"
    exit 1
fi

# Check if production compose file exists
if [ ! -f "docker-compose.prod.yml" ]; then
    print_error "docker-compose.prod.yml not found in current directory"
    exit 1
fi

# Create backup of fiscal notes if they exist
print_info "📦 Creating backup of fiscal notes..."
if [ -d "src/fiscal_notes/generation" ]; then
    mkdir -p fiscal_notes_backups
    BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="fiscal_notes_backups/fiscal_notes_${BACKUP_DATE}.tar.gz"
    tar -czf "${BACKUP_FILE}" src/fiscal_notes/generation/
    print_success "Backup created: ${BACKUP_FILE}"
    
    # Keep only last 10 backups
    cd fiscal_notes_backups
    ls -t fiscal_notes_*.tar.gz | tail -n +11 | xargs -r rm
    cd ..
else
    print_info "No fiscal notes directory found, skipping backup"
fi

# Stop existing containers
print_info "🛑 Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down --remove-orphans || true

# Clean up old images to save space
print_info "🧹 Cleaning up old Docker images..."
docker image prune -f || true

# Build and start production containers
print_info "🚀 Building and starting production containers..."
docker-compose -f docker-compose.prod.yml up -d --build

# Wait for services to be ready
print_info "⏳ Waiting for services to start..."
sleep 30

# Check container health
print_info "🔍 Checking container health..."
docker-compose -f docker-compose.prod.yml ps

# Test API endpoint
print_info "🧪 Testing API endpoint..."
API_READY=false
for i in {1..10}; do
    if curl -f http://localhost:8200/ > /dev/null 2>&1; then
        print_success "API is responding"
        API_READY=true
        break
    fi
    print_info "⏳ Waiting for API... (attempt $i/10)"
    sleep 10
done

# Final health check
if [ "$API_READY" = false ]; then
    print_error "API health check failed"
    print_error "📋 Container logs:"
    docker-compose -f docker-compose.prod.yml logs --tail=50
    exit 1
fi

print_success "✅ All services are healthy and running"
print_success "======================================"
print_info "📊 Final container status:"
docker-compose -f docker-compose.prod.yml ps

print_success "🎉 Production deployment completed successfully!"
print_info "API available at: http://localhost:8200"
print_info "Frontend available at: http://localhost:3000"
print_info "To view logs: docker-compose -f docker-compose.prod.yml logs -f"
print_info "To stop: docker-compose -f docker-compose.prod.yml down"
