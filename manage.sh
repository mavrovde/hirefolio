#!/bin/bash

# manage.sh - Helper script for managing the application containers
# Supports both Docker and Podman

set -e

# Detect container engine and compose tool
if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_CMD="podman-compose"
    ENGINE="podman"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
    ENGINE="docker"
elif docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    ENGINE="docker"
else
    echo "Error: Neither podman-compose nor docker-compose found."
    exit 1
fi

echo "Using $COMPOSE_CMD with $ENGINE engine."

function start() {
    echo "Starting services..."
    $COMPOSE_CMD up -d
    echo "Services started. Frontend: http://localhost:4200, Backend: http://localhost:8000"
}

function stop() {
    echo "Stopping services..."
    $COMPOSE_CMD down
    echo "Services stopped."
}

function restart() {
    echo "Restarting services..."
    stop
    start
}

function build() {
    echo "Building services..."
    $COMPOSE_CMD build
}

function rebuild() {
    echo "Bumping version..."
    ./bump_version.sh
    
    echo "Rebuilding and restarting services..."
    stop
    $COMPOSE_CMD up -d --build
    echo "Services rebuilt and started."
    
    echo ""
    echo "Deployment Status:"
    echo "------------------"
    if [ "$ENGINE" == "podman" ]; then
        podman ps
        echo ""
        podman images | grep mavrovde
    else
        docker ps
        echo ""
        docker images | grep mavrovde
    fi
}

function logs() {
    $COMPOSE_CMD logs -f
}

function help() {
    echo "Usage: ./manage.sh [command]"
    echo "Commands:"
    echo "  start    - Start services"
    echo "  stop     - Stop services"
    echo "  restart  - Restart services (stop + start)"
    echo "  build    - Build images"
    echo "  rebuild  - Rebuild and restart (stop + build + start)"
    echo "  logs     - Follow logs"
}

# Main execution
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    build)
        build
        ;;
    rebuild)
        rebuild
        ;;
    logs)
        logs
        ;;
    *)
        help
        exit 1
        ;;
esac
