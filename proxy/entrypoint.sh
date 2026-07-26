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

# --- Generate the admin allowlist from env (closed by default, never "allow all") --
# Loopback is always allowed by the server block itself; this list adds trusted CIDRs.
ALLOWLIST=/etc/nginx/admin_allowlist.conf
{
    echo "# Generated at container start from ADMIN_ALLOWED_CIDRS (do not edit)."
    if [ -n "${ADMIN_ALLOWED_CIDRS:-}" ]; then
        # Accept a space- or comma-separated list of CIDRs/IPs.
        for cidr in $(echo "$ADMIN_ALLOWED_CIDRS" | tr ',' ' '); do
            echo "allow $cidr;"
        done
    fi
    echo "deny all;"
} > "$ALLOWLIST"
echo "Admin allowlist: ${ADMIN_ALLOWED_CIDRS:-<closed: loopback only>}"

echo "Starting Nginx in HTTP/HTTPS mode..."
exec "$@"
