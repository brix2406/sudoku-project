# nginx Reverse Proxy + GoAccess Traffic Dashboard

This directory contains the Dockerfile, entrypoint, and nginx config for the
reverse proxy and GoAccess dashboard. Deployed as a single container with three
processes.

## Components

| Process | Port | Purpose |
|---|---|---|
| nginx | 80, 443 (internet) | HTTPS reverse proxy → `frontend:5173` |
| goaccess | 7891 (127.0.0.1) | WebSocket server for live traffic updates |
| busybox httpd | 7890 (127.0.0.1) | Serves GoAccess HTML dashboard |

GoAccess parses nginx's combined access log in real time. The dashboard is
a standalone entity — no nginx proxying in its path.

## SSL

A self-signed certificate is auto-generated on first container start (see
`entrypoint.sh`). No manual steps required.

For production, mount a Let's Encrypt certificate at `/etc/nginx/ssl/`.

## Access

### Application

| Environment | URL |
|---|---|
| Docker Compose | https://localhost |
| Kubernetes | https://localhost:443 (`kubectl port-forward service/nginx 443:443 &`) |

### GoAccess Dashboard

Both ports must be reachable — port 7890 serves the HTML, port 7891 handles
live WebSocket updates. The HTML JavaScript auto-connects to port 7891.

**Docker Compose** (localhost):

Open http://localhost:7890.

**Docker Compose** (remote, via SSH):

```bash
ssh -L 7890:127.0.0.1:7890 -L 7891:127.0.0.1:7891 user@your-server
# Then open http://localhost:7890
```

**Kubernetes**:

```bash
kubectl port-forward deployment/nginx 7890:7890 7891:7891 &
# Then open http://localhost:7890
```

## DNS & Hosting

| Type | Name | Value | Purpose |
|---|---|---|---|
| A | sudokudo.example.com | `<server-public-ip>` | Main application (HTTPS) |

**Firewall**: open ports 80 and 443. Do NOT open 7890 or 7891.
