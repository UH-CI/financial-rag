#!/bin/bash

# House Finance Deployment Script
# Usage: ./deploy.sh [option]

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

case "${1:-help}" in
    "local")
        echo -e "${BLUE}🚀 Starting local development...${NC}"
        echo "Installing dependencies..."
        pip install -r src/requirements.txt
        echo "Starting API server on port 8000..."
        python src/run_api.py &
        API_PID=$!
        sleep 3
        echo "Starting test interface on port 8081..."
        cd src/tests && python test_server.py --port 8081 &
        TEST_PID=$!
        cd ../..
        echo -e "${GREEN}✅ Services started!${NC}"
        echo "🔗 API: http://localhost:8000"
        echo "🔗 Test Interface: http://localhost:8081/budget_test_interface.html"
        echo "Press Ctrl+C to stop both services"
        trap "kill $API_PID $TEST_PID 2>/dev/null || true" EXIT
        wait
        ;;
    
    "docker")
        echo -e "${BLUE}🐳 Building and running with Docker...${NC}"
        DOCKER_COMPOSE_CMD=$(get_docker_compose_cmd)
        if [ "$DOCKER_COMPOSE_CMD" = "none" ]; then
            echo -e "${RED}❌ Docker Compose not found!${NC}"
            echo "Trying alternative single-container deployment..."
            echo "Building image..."
            docker build -t house-finance:latest ./src
            echo "Starting API server..."
            docker run -d --name house-finance-api -p 8000:8000 \
                -v "$(pwd)/src/.env:/app/.env:ro" \
                house-finance:latest python run_api.py &
            sleep 3
            echo "Starting test interface..."
            docker run -d --name house-finance-test -p 8081:8081 \
                -v "$(pwd)/src/.env:/app/.env:ro" \
                house-finance:latest python tests/test_server.py --port 8081
            echo -e "${GREEN}✅ Docker containers started!${NC}"
        else
            $DOCKER_COMPOSE_CMD up --build -d
            echo -e "${GREEN}✅ Docker services started!${NC}"
        fi
        echo "🔗 API: http://localhost:8000"
        echo "🔗 Test Interface: http://localhost:8081/budget_test_interface.html"
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
        echo "Option 1 - Direct GitHub clone:"
        echo "  git clone https://github.com/yourusername/house-finance.git"
        echo "  cd house-finance"
        echo "  pip install -r src/requirements.txt"
        echo "  python src/run_api.py &"
        echo "  cd src/tests && python test_server.py --port 8081"
        echo ""
        echo "Option 2 - Docker from Docker Hub:"
        echo "  docker run -d -p 8000:8000 -p 8081:8081 yourusername/house-finance:latest"
        echo ""
        echo "Option 3 - Docker Compose (if available):"
        echo "  git clone https://github.com/yourusername/house-finance.git"
        echo "  cd house-finance"
        echo "  ./deploy.sh docker"
        echo ""
        echo "Option 4 - Simple Docker containers:"
        echo "  docker run -d --name api -p 8000:8000 yourusername/house-finance:latest"
        echo "  docker run -d --name test -p 8081:8081 yourusername/house-finance:latest python tests/test_server.py --port 8081"
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
        echo "  local   - Run locally with Python"
        echo "  docker  - Run with Docker (auto-detects compose vs containers)"
        echo "  build   - Build Docker image"
        echo "  push    - Push to Docker Hub"
        echo "  server  - Show server deployment commands"
        echo "  status  - Check service status"
        echo "  logs    - Show container logs"
        echo "  stop    - Stop all services"
        echo "  help    - Show this help"
        echo ""
        echo -e "${BLUE}Quick start:${NC}"
        echo "  ./deploy.sh local   # For development"
        echo "  ./deploy.sh docker  # For production"
        echo ""
        echo -e "${YELLOW}Updated ports (no conflicts):${NC}"
        echo "  API: http://localhost:8000"
        echo "  Test Interface: http://localhost:8081"
        echo ""
        echo -e "${GREEN}✅ Completely avoids port 8080 conflicts with Watchtower${NC}"
        ;;
esac 