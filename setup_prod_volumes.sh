#!/bin/bash
       # setup_prod_volumes.sh - Ensure external volumes exist for production

       echo "🛡️  Checking Production Volumes..."

       create_volume_if_missing() {
           local VOLUME_NAME=$1
           if docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1; then
               echo "✅ Volume '$VOLUME_NAME' already exists."
           else
               echo "🆕 Creating volume '$VOLUME_NAME'..."
               docker volume create "$VOLUME_NAME"
           fi
       }

       create_volume_if_missing "postgres_data"
       create_volume_if_missing "ollama_data"
       create_volume_if_missing "open-webui_data"

       echo "✨ All production volumes are ready."
