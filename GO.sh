#!/bin/bash

# RAG System Startup Script
# Usage: ./GO.sh [dev|prod] [--init] [--down] [--logs] [--build] [--workers N]
# 
# Flags:
#   dev        - Start development environment (default)
#   prod       - Start production environment  
#   --init     - Initialize frontend dependencies
#   --down     - Stop all services
#   --logs     - Show service logs
#   --build    - Force rebuild containers
#   --workers  - Number of API workers (default: 1, recommended: 10 for production)

# --- Configuration ---
FRONTEND_DIR="frontend"
DEV_COMPOSE_FILE="docker-compose.dev.yml"
PROD_COMPOSE_FILE="docker-compose.prod.yml"

# --- Colors for output ---
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# --- Helper Functions ---
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}" >&2
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

show_usage() {
    echo "Usage: $0 [dev|prod] [--init] [--down] [--logs] [--build] [--workers N]"
    echo ""
    echo "Environment:"
    echo "  dev     Start development environment (default)"
    echo "  prod    Start production environment"
    echo ""
    echo "Options:"
    echo "  --init       Initialize frontend dependencies"
    echo "  --down       Stop all services"
    echo "  --logs       Show service logs"
    echo "  --build      Force rebuild containers"
    echo "  --workers N  Number of API workers (default: 1)"
    echo "  --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Start development environment (1 worker)"
    echo "  $0 dev --init         # Initialize and start development"
    echo "  $0 dev --workers 10   # Start development with 10 API workers"
    echo "  $0 prod --workers 10  # Start production with 10 API workers"
    echo "  $0 --down             # Stop all services"
    echo "  $0 dev --logs         # Show development logs"
    echo ""
    echo "Worker Recommendations:"
    echo "  • Development: 1-3 workers (easier debugging)"
    echo "  • Production: 10 workers (matches 12 Chrome sessions)"
    echo "  • Testing: 10 workers (test full parallel capacity)"
}

# --- Parse Arguments ---
ENVIRONMENT="dev"  # Default to development
INIT=false
DOWN=false
LOGS=false
BUILD=false
WORKERS=""

# Parse arguments with support for --workers N
i=1
while [ $i -le $# ]; do
    arg="${!i}"
    case $arg in
        dev|development)
            ENVIRONMENT="dev"
            ;;
        prod|production)
            ENVIRONMENT="prod"
            ;;
        --init)
            INIT=true
            ;;
        --down)
            DOWN=true
            ;;
        --logs)
            LOGS=true
            ;;
        --build)
            BUILD=true
            ;;
        --workers)
            # Get next argument as worker count
            i=$((i + 1))
            if [ $i -le $# ]; then
                WORKERS="${!i}"
                if ! [[ "$WORKERS" =~ ^[0-9]+$ ]] || [ "$WORKERS" -lt 1 ]; then
                    print_error "Invalid worker count: $WORKERS (must be a positive integer)"
                    exit 1
                fi
            else
                print_error "--workers requires a number"
                show_usage
                exit 1
            fi
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown argument: $arg"
            show_usage
            exit 1
            ;;
    esac
    i=$((i + 1))
done

# Set compose file based on environment
if [ "$ENVIRONMENT" = "prod" ]; then
    COMPOSE_FILE="$PROD_COMPOSE_FILE"
    print_info "Using PRODUCTION environment"
else
    COMPOSE_FILE="$DEV_COMPOSE_FILE"
    print_info "Using DEVELOPMENT environment"
fi

# Set workers environment variable if specified
if [ -n "$WORKERS" ]; then
    export WORKERS="$WORKERS"
    print_info "Setting API workers: $WORKERS"
    
    # Provide recommendations based on worker count
    if [ "$WORKERS" -eq 1 ]; then
        print_info "Single worker mode - good for development and debugging"
    elif [ "$WORKERS" -le 3 ]; then
        print_info "Low worker count - good for development testing"
    elif [ "$WORKERS" -le 10 ]; then
        print_info "High worker count - good for production load"
    else
        print_warning "Very high worker count ($WORKERS) - may exceed Chrome session capacity (12)"
    fi
else
    print_info "Using default worker count (1)"
fi

# --- Handle --down flag ---
if [ "$DOWN" = true ]; then
    print_info "Stopping all services..."
    docker compose -f "$DEV_COMPOSE_FILE" down 2>/dev/null
    docker compose -f "$PROD_COMPOSE_FILE" down 2>/dev/null
    print_success "All services stopped."
    exit 0
fi

# --- Handle --logs flag ---
if [ "$LOGS" = true ]; then
    print_info "Showing logs for $ENVIRONMENT environment..."
    docker compose -f "$COMPOSE_FILE" logs -f
    exit 0
fi

# --- Frontend Initialization ---
if [ "$INIT" = true ]; then
    print_info "Initializing frontend dependencies..."
    
    if [ ! -d "$FRONTEND_DIR" ]; then
        print_error "Frontend directory '$FRONTEND_DIR' not found!"
        exit 1
    fi

    cd "$FRONTEND_DIR" || exit
    
    print_info "Installing npm dependencies..."
    if ! npm install; then
        print_error "npm install failed."
        exit 1
    fi
    
    cd .. || exit
    print_success "Frontend initialization complete."
fi

# --- Docker Compose Commands ---
DOCKER_CMD="docker compose -f $COMPOSE_FILE"

if [ "$BUILD" = true ]; then
    DOCKER_CMD="$DOCKER_CMD up -d --build"
    print_info "Building and starting services..."
else
    DOCKER_CMD="$DOCKER_CMD up -d"
    print_info "Starting services..."
fi

# --- Start Services ---
print_info "Starting $ENVIRONMENT environment..."

if ! eval "$DOCKER_CMD"; then
    print_error "Failed to start services."
    exit 1
fi

print_success "Services started successfully!"

# --- Show Service Status ---
print_info "Service Status:"
docker compose -f "$COMPOSE_FILE" ps

# --- Environment-specific messages ---
if [ "$ENVIRONMENT" = "dev" ]; then
    echo ""
    print_success "🚀 Development Environment Ready!"
    print_info "Frontend: http://localhost:3000"
    print_info "API: http://localhost:8200"
    print_info "API Docs: http://localhost:8200/docs"
    if [ -n "$WORKERS" ]; then
        print_info "API Workers: $WORKERS processes"
        print_info "Redis: Enabled for multi-worker coordination"
        print_info "Chrome Sessions: 12 available (Selenium Grid)"
    fi
    print_warning "Note: Frontend runs in Docker for development"
    echo ""
    print_info "Useful commands:"
    print_info "  ./GO.sh --logs              # View logs"
    print_info "  ./GO.sh --down              # Stop services"
    print_info "  ./GO.sh --build             # Rebuild containers"
    print_info "  ./GO.sh dev --workers 10    # Restart with 10 workers"
else
    echo ""
    print_success "🌐 Production Environment Ready!"
    print_info "Application: http://localhost (via Nginx)"
    print_info "API: http://localhost:8200"
    print_info "Frontend: http://localhost:3000"
    echo ""
    print_info "Useful commands:"
    print_info "  ./GO.sh prod --logs  # View logs"
    print_info "  ./GO.sh --down       # Stop services"
fi
