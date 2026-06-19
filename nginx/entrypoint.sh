#!/bin/sh
set -e

# Generate self-signed certificate if not present
if [ ! -f /etc/nginx/ssl/nginx.crt ]; then
    echo "[nginx] Generating self-signed SSL certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/nginx.key \
        -out /etc/nginx/ssl/nginx.crt \
        -subj "/CN=localhost" 2>/dev/null
    echo "[nginx] Certificate generated."
fi

# Ensure access log exists before goaccess starts watching it
touch /var/log/nginx/access.log

# Start GoAccess WebSocket server (internal)
echo "[goaccess] Starting WebSocket server on :7891..."
goaccess /var/log/nginx/access.log \
    --log-format=COMBINED \
    --real-time-html \
    --addr=0.0.0.0 \
    --port=7891 \
    --ws-url=ws://localhost:7891/ws \
    -o /var/log/nginx/goaccess/index.html \
    --daemon

# GoAccess dashboard HTML served by nginx on :7890 (separate server block)
echo "[goaccess] Dashboard ready (HTML :7890 via nginx, WS :7891 direct)..."

# Start nginx in foreground
echo "[nginx] Starting..."
exec nginx -g "daemon off;"
