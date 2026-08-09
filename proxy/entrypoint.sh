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

# --- Generate real_ip trust + admin allowlist from env (closed by default) ----
# Restores the real client IP behind the Docker gateway / front proxy, then
# filters the admin console on trusted operator CIDRs. See generate-admin-config.sh.
echo "Generating admin access config (trusted='${TRUSTED_PROXY_CIDRS:-172.16.0.0/12}', admin_cidrs='${ADMIN_ALLOWED_CIDRS:-<closed: loopback only>}')..."
/generate-admin-config.sh /etc/nginx

# --- Fail-safe: never let a bad allowlist/real_ip snippet crash nginx or silently
# lock the owner out. Validate ONLY our two generated snippets, in isolation, with a
# throwaway minimal config — deliberately NOT the full config, whose upstream names
# (backend/frontend/...) resolve only inside the compose network and would otherwise
# make this misfire on a DNS race. If a snippet is invalid, revert to KNOWN-GOOD safe
# defaults (trust the Docker bridge, admin closed to loopback only) so the real
# `exec nginx` below still starts on valid config. This block never aborts the
# container itself (both checks are guarded), so it can't take the public site down.
validate_admin_snippets() {
    cat > /tmp/admin_validate.conf <<'EOF'
events {}
http {
    include /etc/nginx/real_ip.conf;
    server {
        listen 8099;
        server_name _;
        include /etc/nginx/admin_allowlist.conf;
        location / { return 200; }
    }
}
EOF
    nginx -t -c /tmp/admin_validate.conf 2>/tmp/admin_validate.log
}

if ! validate_admin_snippets; then
    echo "ERROR: generated admin/real_ip snippets failed validation — reverting to safe closed defaults:" >&2
    cat /tmp/admin_validate.log >&2
    printf '%s\n' \
        "# FALLBACK (generated snippet was invalid): trust Docker bridge, read X-Forwarded-For." \
        "set_real_ip_from 172.16.0.0/12;" \
        "real_ip_header X-Forwarded-For;" \
        "real_ip_recursive on;" > /etc/nginx/real_ip.conf
    printf '%s\n' \
        "# FALLBACK (generated snippet was invalid): admin CLOSED (loopback only)." \
        "deny all;" > /etc/nginx/admin_allowlist.conf
    if ! validate_admin_snippets; then
        echo "ERROR: fallback snippets still invalid (unexpected) — continuing; nginx will surface any error" >&2
        cat /tmp/admin_validate.log >&2
    fi
fi

echo "Starting Nginx in HTTP/HTTPS mode..."
exec "$@"
