#!/bin/bash
# restore_potential_volume.sh - Inspect an orphan volume to see if it contains the lost data

VOLUME_ID=$1
DB_CONTAINER="mavrovde-db-1"

if [ -z "$VOLUME_ID" ]; then
    echo "Usage: ./restore_potential_volume.sh <VOLUME_ID>"
    echo "Example: ./restore_potential_volume.sh 69db621bd..."
    exit 1
fi

echo "🔍 Inspecting volume: $VOLUME_ID"

# 1. Stop the current DB container
echo "Stopping database container..."
docker stop $DB_CONTAINER

# 2. Start a temporary container with the target volume mounted
echo "Starting inspection container..."
# We mount the target volume to /var/lib/postgresql/data
# We use the same image as the db service
echo "Checking for 'posts' table count..."

# Run a temporary postgres to check data
# Note: This might take a few seconds to start up within the container
docker run --rm \
    -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=mavrov \
    -v $VOLUME_ID:/var/lib/postgresql/data \
    pgvector/pgvector:pg16 \
    /bin/bash -c "
        docker-entrypoint.sh postgres & 
        sleep 10; 
        psql -U postgres -d mavrov -c 'SELECT count(*) FROM posts;' || echo 'Could not query posts table';
    "

echo "---------------------------------------------------"
echo "If you saw a count > 0, this is likely your lost data."
echo "To restore it:"
echo "1. Update docker-compose.prod.yml to use this volume as 'external'"
echo "   OR"
echo "2. Dump the data from this volume and restore it to 'postgres_data'"
echo "---------------------------------------------------"

# Restart original DB
echo "Restarting original database..."
docker start $DB_CONTAINER
