#!/bin/sh
set -e

mkdir -p /etc/nginx/ssl
if [ ! -f /etc/nginx/ssl/fullchain.pem ]; then
    echo "Generating dummy SSL certificates..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/privkey.pem \
        -out /etc/nginx/ssl/fullchain.pem \
        -subj "/CN=localhost"
fi

# --- Render the site config from the template (owner-configurable server_name) ----
# Defaults preserve the canonical mavrov.de hostnames; a forker overrides via env.
: "${PUBLIC_SERVER_NAME:=mavrov.de www.mavrov.de}"
: "${ADMIN_SERVER_NAME:=admin.mavrov.de admin.localhost}"
export PUBLIC_SERVER_NAME ADMIN_SERVER_NAME
echo "Rendering nginx config (public='${PUBLIC_SERVER_NAME}', admin='${ADMIN_SERVER_NAME}')..."
# Substitute ONLY our two names so nginx runtime vars ($host, $remote_addr, ...) survive.
envsubst '${PUBLIC_SERVER_NAME} ${ADMIN_SERVER_NAME}' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

echo "Starting Nginx in HTTP/HTTPS mode..."
exec "$@"
