#!/bin/bash

# House Finance Deployment Script
# Usage: ./deploy.sh [option] [run_api.py flags]

set -e

echo "🏛️  House Finance Deployment Script"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to detect docker compose command
get_docker_compose_cmd() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    elif docker compose version &> /dev/null; then
        echo "docker compose"
    else
        echo "none"
    fi
}

# Extract deployment mode and API flags
DEPLOY_MODE="${1:-help}"
shift || true  # Remove first argument (deploy mode)
API_FLAGS="$@"  # Capture remaining arguments as API flags

case "$DEPLOY_MODE" in
    "local")
        echo -e "${BLUE}🚀 Starting local development...${NC}"
        echo "Installing dependencies..."
        pip install -r src/requirements.txt
        echo "Starting API server on port 8000..."
        cd src
        python run_api.py $API_FLAGS &
        API_PID=$!
        sleep 3
        echo "Starting test interface on port 8081..."
        cd tests && python test_server.py --port 8081 &
        TEST_PID=$!
        cd ../..
        echo -e "${GREEN}✅ Services started!${NC}"
        echo "🔗 API: http://localhost:8000"
        echo "🔗 Test Interface: http://localhost:8081/budget_test_interface.html"
        if [ -n "$API_FLAGS" ]; then
            echo "🚀 API started with flags: $API_FLAGS"
        fi
        echo "Press Ctrl+C to stop both services"
        trap "kill $API_PID $TEST_PID 2>/dev/null || true" EXIT
        wait
        ;;
    
    "docker")
        echo -e "${BLUE}🐳 Building and running with Docker...${NC}"
        
        # Check for Google API key
        if [ -z "$GOOGLE_API_KEY" ]; then
            echo -e "${YELLOW}⚠️  WARNING: GOOGLE_API_KEY not set!${NC}"
            echo "The intelligent-query endpoint requires a Google API key."
            echo "Set it with: export GOOGLE_API_KEY='your_key_here'"
            echo "Other endpoints will still work."
        fi
        
        DOCKER_COMPOSE_CMD=$(get_docker_compose_cmd)
        if [ "$DOCKER_COMPOSE_CMD" = "none" ]; then
            echo -e "${RED}❌ Docker Compose not found!${NC}"
            echo "Trying alternative single-container deployment..."
            
            # Stop existing containers
            docker stop house-finance-api house-finance-test 2>/dev/null || true
            docker rm house-finance-api house-finance-test 2>/dev/null || true
            
            echo "Building image..."
            docker build -t house-finance:latest ./src
            
            echo "Starting API server..."
            docker run -d --name house-finance-api -p 8000:8000 \
                -e GOOGLE_API_KEY="${GOOGLE_API_KEY:-}" \
                -v "$(pwd)/src/chroma_db/data:/app/chroma_db/data" \
                -v "$(pwd)/src/.env:/app/.env:ro" \
                house-finance:latest python run_api.py $API_FLAGS
            
            sleep 5
            
            echo "Starting test interface..."
            docker run -d --name house-finance-test -p 8081:8080 \
                -e GOOGLE_API_KEY="${GOOGLE_API_KEY:-}" \
                -v "$(pwd)/src/chroma_db/data:/app/chroma_db/data" \
                house-finance:latest python tests/test_server.py --port 8080
            
            echo -e "${GREEN}✅ Docker containers started!${NC}"
        else
            # Create a temporary docker-compose override for API flags
            if [ -n "$API_FLAGS" ]; then
                echo "🚀 Starting with API flags: $API_FLAGS"
                cat > docker-compose.override.yml << EOF
version: '3.8'
services:
  api:
    command: python run_api.py $API_FLAGS
EOF
            else
                # Remove any existing override
                rm -f docker-compose.override.yml
            fi
            
            $DOCKER_COMPOSE_CMD up --build -d
            echo -e "${GREEN}✅ Docker services started!${NC}"
            
            # Clean up override file
            rm -f docker-compose.override.yml
        fi
        echo "🔗 API: http://localhost:8000"
        echo "🔗 Test Interface: http://localhost:8081/budget_test_interface.html"
        if [ -n "$API_FLAGS" ]; then
            echo "🚀 API started with flags: $API_FLAGS"
        fi
        echo "Run './deploy.sh logs' to see logs"
        echo "Run './deploy.sh stop' to stop"
        ;;
    
    "build")
        echo -e "${BLUE}🔨 Building Docker image...${NC}"
        docker build -t house-finance:latest ./src
        echo -e "${GREEN}✅ Docker image built successfully!${NC}"
        echo "Run './deploy.sh docker' to start services"
        ;;
    
    "push")
        echo -e "${BLUE}📤 Pushing to Docker Hub...${NC}"
        read -p "Enter your Docker Hub username: " DOCKER_USER
        docker tag house-finance:latest $DOCKER_USER/house-finance:latest
        docker push $DOCKER_USER/house-finance:latest
        echo -e "${GREEN}✅ Image pushed to Docker Hub!${NC}"
        echo "On your server, run:"
        echo "  docker run -d -p 8000:8000 -p 8081:8081 $DOCKER_USER/house-finance:latest python tests/test_server.py --port 8081"
        ;;
    
    "server")
        echo -e "${BLUE}🖥️  Server deployment commands:${NC}"
        echo ""
        echo "⚠️  IMPORTANT: Set GOOGLE_API_KEY environment variable first!"
        echo "  export GOOGLE_API_KEY='your_api_key_here'"
        echo ""
        echo "Option 1 - Direct GitHub clone with ingestion:"
        echo "  git clone https://github.com/yourusername/house-finance.git"
        echo "  cd house-finance"
        echo "  pip install -r src/requirements.txt"
        echo "  export GOOGLE_API_KEY='your_api_key_here'"
        echo "  ./deploy.sh local --ingest --ingest-type worksheets"
        echo ""
        echo "Option 2 - Docker with ingestion:"
        echo "  ./deploy.sh docker --ingest --ingest-type worksheets"
        echo ""
        echo "Option 3 - Append mode (add to existing data):"
        echo "  ./deploy.sh docker --ingest --append"
        echo ""
        echo "Available --ingest flags:"
        echo "  --ingest                     # Ingest and start server"
        echo "  --ingest-only                # Only ingest, don't start server"
        echo "  --ingest-type worksheets     # Use budget worksheets"
        echo "  --ingest-type standard       # Use standard documents"
        echo "  --append or --no-reset       # Don't reset collections"
        echo ""
        ;;
    
    "logs")
        echo -e "${BLUE}📋 Showing container logs...${NC}"
        DOCKER_COMPOSE_CMD=$(get_docker_compose_cmd)
        if [ "$DOCKER_COMPOSE_CMD" != "none" ]; then
            $DOCKER_COMPOSE_CMD logs -f
        else
            echo "API Server logs:"
            docker logs house-finance-api
            echo ""
            echo "Test Interface logs:"
            docker logs house-finance-test
        fi
        ;;
    
    "status")
        echo -e "${BLUE}📊 Checking service status...${NC}"
        DOCKER_COMPOSE_CMD=$(get_docker_compose_cmd)
        if [ "$DOCKER_COMPOSE_CMD" != "none" ]; then
            echo "Docker Compose services:"
            $DOCKER_COMPOSE_CMD ps 2>/dev/null || echo "Docker Compose not running"
        else
            echo "Docker containers:"
            docker ps | grep house-finance || echo "No house-finance containers running"
        fi
        echo ""
        echo "Local processes:"
        pgrep -f "python.*run_api.py" && echo "✅ API server running" || echo "❌ API server not running"
        pgrep -f "python.*test_server.py" && echo "✅ Test server running" || echo "❌ Test server not running"
        echo ""
        echo "Port usage:"
        lsof -i :8000 2>/dev/null && echo "Port 8000 in use" || echo "Port 8000 free"
        lsof -i :8081 2>/dev/null && echo "Port 8081 in use" || echo "Port 8081 free"
        ;;
    
    "stop")
        echo -e "${YELLOW}🛑 Stopping services...${NC}"
        DOCKER_COMPOSE_CMD=$(get_docker_compose_cmd)
        if [ "$DOCKER_COMPOSE_CMD" != "none" ]; then
            $DOCKER_COMPOSE_CMD down 2>/dev/null || echo "Docker Compose not running"
        else
            docker stop house-finance-api house-finance-test 2>/dev/null || echo "No containers to stop"
            docker rm house-finance-api house-finance-test 2>/dev/null || echo "No containers to remove"
        fi
        pkill -f "python.*run_api.py" 2>/dev/null || echo "No API server to stop"
        pkill -f "python.*test_server.py" 2>/dev/null || echo "No test server to stop"
        echo -e "${GREEN}✅ Services stopped${NC}"
        ;;
    
    "help"|*)
        echo -e "${YELLOW}Available commands:${NC}"
        echo "  local [API_FLAGS]   - Run locally with Python (pass API flags)"
        echo "  docker [API_FLAGS]  - Run with Docker (pass API flags)"
        echo "  build               - Build Docker image"
        echo "  push                - Push to Docker Hub"
        echo "  server              - Show server deployment commands"
        echo "  status              - Check service status"
        echo "  logs                - Show container logs"
        echo "  stop                - Stop services"
        echo ""
        echo -e "${YELLOW}API Flags (can be passed after command):${NC}"
        echo "  --ingest                     # Reset collections and ingest documents"
        echo "  --ingest-only                # Only ingest, don't start server"
        echo "  --ingest-type worksheets     # Ingest budget worksheets"
        echo "  --ingest-type standard       # Ingest standard documents (default)"
        echo "  --append or --no-reset       # Don't reset collections before ingestion"
        echo "  --ingest-file path/file.json # Custom file to ingest"
        echo ""
        echo -e "${YELLOW}Examples:${NC}"
        echo "  ./deploy.sh docker --ingest --ingest-type worksheets"
        echo "  ./deploy.sh local --ingest --append"
        echo "  ./deploy.sh docker --ingest-only --ingest-type standard"
        ;;
esac 