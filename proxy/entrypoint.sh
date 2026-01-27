#!/bin/sh
set -e

# Define paths
DOMAIN="mavrov.de"
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"
CONF_DIR="/etc/letsencrypt"
SSL_PARAMS="$CONF_DIR/options-ssl-nginx.conf"
SSL_DHPARAMS="$CONF_DIR/ssl-dhparams.pem"

echo "Bootstrapping Nginx SSL..."

# 1. Download recommended TLS parameters if missing
if [ ! -f "$SSL_PARAMS" ] || [ ! -f "$SSL_DHPARAMS" ]; then
    echo "Downloading recommended TLS parameters..."
    mkdir -p "$CONF_DIR"
    # Nginx alpine has wget
    wget -qO "$SSL_PARAMS" https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf
    wget -qO "$SSL_DHPARAMS" https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem
fi

# 2. Generate dummy certificate if missing (to allow Nginx to start)
if [ ! -f "$CERT_DIR/fullchain.pem" ]; then
    echo "Detail: No existing certificate found at $CERT_DIR/fullchain.pem"
    echo "Action: Generating dummy self-signed certificate to satisfy Nginx config..."
    mkdir -p "$CERT_DIR"
    # Using openssl from alpine
    openssl req -x509 -nodes -newkey rsa:4096 -days 1 \
        -keyout "$CERT_DIR/privkey.pem" \
        -out "$CERT_DIR/fullchain.pem" \
        -subj "/CN=localhost"
    echo "Dummy certificate created."
else
    echo "Valid certificate found. Skipping dummy generation."
fi

echo "Starting Nginx..."
exec "$@"
