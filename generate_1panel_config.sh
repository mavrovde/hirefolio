#!/bin/bash
echo "Generating docker-compose.1panel.yml from docker-compose.prod.yml..."

# Copy prod config
cp docker-compose.prod.yml docker-compose.1panel.yml

# Check if yq is installed, otherwise use sed/grep
if command -v yq &> /dev/null; then
    yq eval 'del(.services.*.build)' -i docker-compose.1panel.yml
else
    # Fallback to sed/grep for simple removal of build: lines
    # This assumes "build:" is on its own line or standard format
    # We remove "build: *" lines
    
    # Mac OS sed requires -i ''
    sed -i '' '/build:/d' docker-compose.1panel.yml
    sed -i '' '/context:/d' docker-compose.1panel.yml
    sed -i '' '/dockerfile:/d' docker-compose.1panel.yml
    
    echo "  - Removed build context from backend"
    echo "  - Removed build context from frontend"
    echo "  - Removed build context from proxy"
fi

echo "✅ Generated docker-compose.1panel.yml"
