#!/bin/bash

# RAG System Startup Script
# Usage: ./GO.sh [dev|prod] [--init] [--down] [--logs] [--build] [--workers N] [--backup] [--deploy]
# 
# Flags:
#   dev        - Start development environment (default)
#   prod       - Start production environment  
#   --init     - Initialize frontend dependencies
#   --down     - Stop all services
#   --logs     - Show service logs
#   --build    - Force rebuild containers
#   --workers  - Number of API workers (default: 1, recommended: 4 for production)
#   --backup   - Create backup of fiscal notes before deployment
#   --deploy   - Full production deployment with backup and health checks

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

# --- Backup Functions ---
create_fiscal_notes_backup() {
    print_info "📦 Creating backup of fiscal notes..."
    if [ -d "src/fiscal_notes/generation" ]; then
        mkdir -p fiscal_notes_backups
        BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
        BACKUP_FILE="fiscal_notes_backups/fiscal_notes_${BACKUP_DATE}.tar.gz"
        tar -czf "${BACKUP_FILE}" src/fiscal_notes/generation/
        print_success "Backup created: ${BACKUP_FILE}"
        
        # Keep only last 10 backups to save space
        cd fiscal_notes_backups
        ls -t fiscal_notes_*.tar.gz | tail -n +11 | xargs -r rm 2>/dev/null
        print_info "📊 Current backups:"
        ls -lh fiscal_notes_*.tar.gz 2>/dev/null || print_info "No previous backups found"
        cd ..
    else
        print_info "No fiscal notes directory found, skipping backup"
    fi
}

# --- Health Check Functions ---
wait_for_api() {
    local max_attempts=10
    local attempt=1
    
    print_info "🧪 Testing API endpoint..."
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8200/ > /dev/null 2>&1; then
            print_success "API is responding"
            return 0
        fi
        print_info "⏳ Waiting for API... (attempt $attempt/$max_attempts)"
        sleep 10
        attempt=$((attempt + 1))
    done
    
    print_error "API health check failed after $max_attempts attempts"
    return 1
}

# --- Docker Management Functions ---
cleanup_docker_resources() {
    print_info "🧹 Cleaning up Docker resources..."
    
    # Remove unused images
    docker image prune -f || true
    
    # Remove build cache to save space
    docker builder prune -f || true
    
    print_info "📊 Disk space after cleanup:"
    df -h / | tail -1 || true
}

stop_all_containers() {
    print_info "🛑 Stopping all containers and cleaning up ports..."
    
    # Stop all compose projects that might be running
    docker compose -f docker-compose.yml down --remove-orphans 2>/dev/null || true
    docker compose -f docker-compose.dev.yml down --remove-orphans 2>/dev/null || true
    docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
    
    # Kill any processes using our ports
    print_info "🔍 Checking for processes using ports..."
    
    # Check what's using port 8200
    PORT_8200_PID=$(lsof -ti:8200 2>/dev/null || true)
    if [ -n "$PORT_8200_PID" ]; then
        print_warning "Port 8200 is in use by PID: $PORT_8200_PID"
        kill -9 $PORT_8200_PID 2>/dev/null || true
        sleep 2
    fi
    
    # Check what's using port 6379
    PORT_6379_PID=$(lsof -ti:6379 2>/dev/null || true)
    if [ -n "$PORT_6379_PID" ]; then
        print_warning "Port 6379 is in use by PID: $PORT_6379_PID"
        kill -9 $PORT_6379_PID 2>/dev/null || true
        sleep 2
    fi
    
    # Force stop any containers using our ports (alternative method)
    docker ps -q --filter "publish=6379" | xargs -r docker kill 2>/dev/null || true
    docker ps -q --filter "publish=8200" | xargs -r docker kill 2>/dev/null || true
    docker ps -q --filter "publish=3000" | xargs -r docker kill 2>/dev/null || true
    docker ps -q --filter "publish=4444" | xargs -r docker kill 2>/dev/null || true
    
    # Remove any stopped containers
    docker container prune -f || true
    
    # Wait a moment for ports to be released
    sleep 3
    
    print_info "📋 Port status after cleanup:"
    netstat -tlnp | grep -E ":(6379|8200|3000|4444)" || print_info "All target ports are free"
    
    print_info "📋 Remaining running containers:"
    docker ps --format "table {{.Names}}\t{{.Ports}}" || true
}

deploy_production() {
    print_info "🚀 Starting Full Production Deployment"
    print_info "======================================"
    
    # Create backup if requested
    if [ "$BACKUP" = true ]; then
        create_fiscal_notes_backup
    fi
    
    # Stop all containers and clean up ports
    stop_all_containers
    
    # Clean up Docker resources
    cleanup_docker_resources
    
    # Final port check before deployment
    print_info "🔍 Final port availability check..."
    PORTS_IN_USE=$(netstat -tlnp | grep -E ":(6379|8200|3000|4444)" || true)
    if [ -n "$PORTS_IN_USE" ]; then
        print_error "Ports still in use after cleanup:"
        echo "$PORTS_IN_USE"
        print_error "Deployment cannot proceed with ports in use"
        return 1
    fi
    print_success "All required ports are available"
    
    # Build and start production containers
    print_info "🚀 Building and starting production containers..."
    if ! docker compose -f "$COMPOSE_FILE" up -d --build; then
        print_error "Failed to start containers"
        return 1
    fi
    
    # Wait for services to be ready
    print_info "⏳ Waiting for services to start..."
    sleep 30
    
    # Check container health
    print_info "🔍 Checking container health..."
    docker compose -f "$COMPOSE_FILE" ps
    
    # Test API endpoint
    if ! wait_for_api; then
        print_error "📋 Container logs:"
        docker compose -f "$COMPOSE_FILE" logs --tail=50
        return 1
    fi
    
    print_success "✅ Production deployment completed successfully!"
    return 0
}

show_usage() {
    echo "Usage: $0 [dev|prod] [--init] [--down] [--logs] [--build] [--workers N] [--backup] [--deploy]"
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
    echo "  --workers N  Number of API workers (default: 1 for dev, 4 for prod)"
    echo "  --backup     Create backup of fiscal notes before deployment"
    echo "  --deploy     Full production deployment with backup and health checks"
    echo "  --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Start development environment (1 worker)"
    echo "  $0 dev --init         # Initialize and start development"
    echo "  $0 dev --workers 4    # Start development with 4 API workers"
    echo "  $0 prod --deploy      # Full production deployment with backup"
    echo "  $0 prod --workers 8   # Start production with 8 API workers"
    echo "  $0 --down             # Stop all services"
    echo "  $0 dev --logs         # Show development logs"
    echo ""
    echo "Worker Recommendations:"
    echo "  • Development: 1 worker (easier debugging)"
    echo "  • Dev Testing: 2-4 workers (test multi-worker behavior)"
    echo "  • Production: 4-8 workers (optimal performance)"
    echo "  • High Load: 8+ workers (high-traffic scenarios)"
}

# --- Parse Arguments ---
ENVIRONMENT="dev"  # Default to development
INIT=false
DOWN=false
LOGS=false
BUILD=false
WORKERS=""
BACKUP=false
DEPLOY=false

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
        --down)
            DOWN=true
            ;;
        --logs)
            LOGS=true
            ;;
        --build)
            BUILD=true
            ;;
        --backup)
            BACKUP=true
            ;;
        --deploy)
            DEPLOY=true
            BACKUP=true  # Deploy always includes backup
            BUILD=true   # Deploy always rebuilds
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

# --- Handle --backup flag ---
if [ "$BACKUP" = true ] && [ "$DEPLOY" = false ]; then
    create_fiscal_notes_backup
    exit 0
fi

# --- Handle --deploy flag ---
if [ "$DEPLOY" = true ]; then
    if [ "$ENVIRONMENT" != "prod" ]; then
        print_error "--deploy flag can only be used with production environment"
        print_info "Use: ./GO.sh prod --deploy"
        exit 1
    fi
    
    if deploy_production; then
        print_success "🎉 Production deployment completed successfully!"
        # Show final status and exit
        print_info "📊 Final container status:"
        docker compose -f "$COMPOSE_FILE" ps
        exit 0
    else
        print_error "Production deployment failed"
        exit 1
    fi
fi

# --- Standard Docker Compose Commands ---
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
    print_info "  ./GO.sh dev --workers 4     # Restart with 4 workers"
    print_info "  ./GO.sh --backup            # Create fiscal notes backup"
else
    echo ""
    print_success "🌐 Production Environment Ready!"
    print_info "Application: http://localhost (via Nginx)"
    print_info "API: http://localhost:8200"
    print_info "Frontend: http://localhost:3000"
    if [ -n "$WORKERS" ]; then
        print_info "API Workers: $WORKERS processes"
        print_info "Redis: Enabled for multi-worker coordination"
    fi
    echo ""
    print_info "Useful commands:"
    print_info "  ./GO.sh prod --logs          # View logs"
    print_info "  ./GO.sh prod --deploy        # Full deployment with backup"
    print_info "  ./GO.sh --backup             # Create fiscal notes backup"
    print_info "  ./GO.sh --down               # Stop services"
fi
