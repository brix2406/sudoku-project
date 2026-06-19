# Sudokudo

A full-stack Sudoku solver that accepts either a photo of a puzzle or a manually entered board,
solves it, and returns the completed grid. Supports arbitrary k×n board sizes, not just standard 9×9.

## Architecture

```
Browser → nginx (HTTPS :443)
        → REST API (Flask :5000)
          → NATS message broker (:4222)
            ├── Service Layer (Rust)   — orchestrates, reads/writes SQLite
            │     ├── Sudoku Worker (Rust)  — backtracking solver
            │     └── OCR Worker (Python)   — CNN digit extractor
            └── Marmot sidecar             — SQLite replication
```

**Services**

| Service | Language | Purpose |
|---|---|---|
| `frontend` | React / Vite | Upload image or enter board; display solution |
| `api` | Python / Flask | REST gateway; validates and forwards to NATS |
| `service_layer_rust` | Rust / Tokio | NATS subscriber; DB reads/writes; delegates solving and OCR |
| `sudoku_nats_worker` | Rust | Backtracking solver worker |
| `ocr` | Python / PyTorch | CNN that reads digit cells from a photo |
| `nats` | NATS (JetStream) | Message broker |
| `marmot` | Marmot | SQLite replication sidecar (co-located with `service_layer_rust`) |
| `nginx` | Nginx / GoAccess | HTTPS reverse proxy; auto self-signed cert; real-time traffic dashboard |

## Prerequisites

**Docker Compose** (local development)
- Docker Engine ≥ 20 with the Compose plugin (`docker compose version` must succeed)

**Kubernetes** (k3d)
- [k3d](https://k3d.io) ≥ 5
- kubectl
- Docker Engine (k3d uses it for the cluster nodes)
- A GitHub Personal Access Token (PAT) with `read:packages` scope, or the GHCR packages set to public

## Running with Docker Compose

Builds all images locally and starts every service:

```bash
docker compose up
```

| URL | Service |
|---|---|
| https://localhost | Application (accept self-signed cert warning on first visit) |
| http://localhost:7890 | GoAccess traffic dashboard (localhost only; on remote servers use SSH tunnel) |
Stop and remove containers:

```bash
docker compose down
```

Remove the persistent database volume as well:

```bash
docker compose down -v
```

## Running with k3d / kubectl

Images are pulled from GitHub Container Registry (`ghcr.io/brix2406/sudoku-project:<service>`).
The cluster must be able to reach `ghcr.io` at startup.

### 1. Create the cluster

```bash
k3d cluster create sudokudo
```

### 2. Create the GHCR image-pull secret

The manifests reference a secret named `ghcr-secret` in the default namespace.

```bash
kubectl create secret docker-registry ghcr-secret
  --docker-server=ghcr.io
  --docker-username=sudoku-project-access
  --docker-password=<github-pat-with-read-packages>
```

A PAT with the `read:packages` scope is sufficient. If the packages are set to public on GHCR,
this step can be skipped (the `imagePullSecrets` stanza is kept in the manifests for safety).

### 3. Apply all manifests

```bash
kubectl apply -f k3s-manifests/
```

This creates the PersistentVolumeClaims, Deployments, and Services for all components.

### 4. Wait for pods to become ready

```bash
kubectl wait --for=condition=ready pod --all --timeout=180s
```

The OCR worker takes the longest to start due to model loading. If the timeout elapses, re-run the
command or check logs with `kubectl logs deployment/ocr`.

### 5. Access the application

Port-forward the nginx reverse proxy:

```bash
# Application (HTTPS)
kubectl port-forward service/nginx 443:443 &

# GoAccess dashboard (localhost only — HTML on 7890, live WebSocket on 7891)
kubectl port-forward deployment/nginx 7890:7890 7891:7891 &
```

Open https://localhost:443 (accept self-signed cert warning on first visit).

### Teardown

```bash
kubectl delete -f k3s-manifests/
k3d cluster delete sudokudo
```

## API Reference

Base URL: `https://localhost` (Docker Compose) or `https://localhost:443` after port-forwarding.
Add `-k` to curl commands to skip certificate verification when using a self-signed certificate.

### `POST /solve-image`

Solve a puzzle from a photograph. Upload the image as `multipart/form-data` with the field `file`.

```bash
curl -k -X POST https://localhost/solve-image \
  -F "file=@puzzle.png"
```

Response (200 OK):

```json
{
  "original_board": [["1",".","."], ...],
  "solved_board":   [["1","2","3"], ...]
}
```

### `POST /manual_solve`

Solve a manually entered board. Send JSON with a `value` field containing a board string of the
form `Sudoku{(k,n)(cell,cell,...)}` where k and n define the block size and cells are either a
number or `.` for empty.

Example for a standard 9×9 (k=3, n=3):

```bash
curl -k -X POST https://localhost/manual_solve \
  -H "Content-Type: application/json" \
  -d '{"value": "Sudoku{(3,3)(5,3,.,.,7,.,.,.,.,6,.,.,1,9,5,.,.,.,.,9,8,.,.,.,.,6,.,.,.,.,6,.,.,.,3,4,.,.,.,8,.,3,.,.,1,7,.,.,.,.,2,.,.,.,.,6,.,.,.,.,2,8,.,.,.,4,.,.,.,.,1,9,.,.,.,5,.,.,.,.,8,.,.,.,7,9)}"}'
```

Response (200 OK): same shape as `/solve-image`.

### `GET /status`

Health check. Returns NATS connectivity and round-trip latency.

```bash
curl -k https://localhost/status
```

Response:

```json
{
  "serviceStatus": "healthy",
  "workerStatus": "connected",
  "latencyMs": 3,
  "queueDepth": 0
}
```


## Debug Artifacts

When OCR fails to extract a grid, or the solver rejects a puzzle as contradictory,
the system saves debug artifacts to a shared `/debug` volume for inspection.

### Directory layout

```
./debug/
├── grid_not_found/     # Images where no grid corners were found
├── ocr_overlays/       # Original photos with perspective-corrected OCR predictions overlaid
└── contradictions/     # Puzzles rejected as impossible
```

Files are named `<unix_timestamp>_<sha256_prefix>.png` (or `.json` / `_overlay.png`),
making them easy to correlate across directories.

### Docker Compose

A bind mount maps `./debug/` from the host into both the `ocr` and `service_layer_rust`
containers at `/debug`. No extra setup needed — create the directory and artifacts
will appear automatically:

```bash
mkdir -p debug
docker compose up
```

### k3s

Artifacts are written to `/var/sudoku-debug/grid_not_found/`, `/var/sudoku-debug/ocr_overlays/`,
and `/var/sudoku-debug/contradictions/` respectively.
To retrieve artifacts from the cluster:

```bash
# Copy from a pod to local machine
kubectl cp ocr-pod-name:/debug/grid_not_found ./debug/grid_not_found
kubectl cp service-layer-rust-pod-name:/debug/contradictions ./debug/contradictions
```

### Interpreting artifacts

| Directory | Contents | When saved |
|---|---|---|
| `grid_not_found/` | Original uploaded image (PNG) | OCR could not isolate grid corners |
| `ocr_overlays/` | Original photo with green perspective-corrected cell boundaries and red digit predictions + confidence scores | OCR successfully extracted a grid |
| `contradictions/` | Three files per puzzle: original image (`.png`), extracted board (`.json`), and OCR prediction overlay (`.png` overlay copied from `ocr_overlays/`) | Solver found conflicting givens or no solution exists |
## Project Layout

```
.
├── frontend/                  React/Vite UI
├── api_python/                Flask REST API + NATS client
├── service_layer_rust/        Rust NATS service (orchestrator + SQLite)
├── sudoku_solver_rust/
│   ├── sudoku_engine/         Core backtracking solver library
│   └── sudoku_nats_worker/    NATS worker wrapping the engine
├── ocr/                       CNN digit recogniser (PyTorch)
├── nginx/                     nginx config + GoAccess dashboard reference
├── marmot_build/              Marmot SQLite replication config + Dockerfile
├── database_connection/       Shared SQLite connection crate
├── k3s-manifests/             Kubernetes manifests (generated with kompose)
├── .github/workflows/         CI — builds and pushes all Docker images to GHCR
├── docker-compose.yml         Local development stack
└── nats.conf                  NATS server configuration
```

## Tech Stack

- **Solver**: constraint propagation + backtracking with MRV heuristic (Rust)
- **OCR**: custom CNN trained on MNIST, fine-tuned for printed digits (PyTorch)
- **Messaging**: NATS JetStream (pub/sub request-reply pattern)
- **Database**: SQLite with Marmot replication
- **API**: Flask + flask-restful, rate-limited to 10 requests/minute per endpoint
- **Frontend**: React 18, Vite, served via `npm run dev`

## DNS & Hosting

To expose the application on the public internet, create this DNS record:

| Type | Name | Value | Purpose |
|---|---|---|---|
| A | sudokudo.example.com | `<server-public-ip>` | Main application (HTTPS) |

Replace `example.com` with your domain and `<server-public-ip>` with your server's public IPv4 address.

**Only port 443 (HTTPS) and port 80 (HTTP redirect) are internet-facing.** The GoAccess dashboard is never exposed — access it via SSH tunnel:

```bash
ssh -L 7890:127.0.0.1:7890 -L 7891:127.0.0.1:7891 user@your-server
```

Then open http://localhost:7890. Live updates use WebSocket on port 7891 automatically.

**Local development**: add to `/etc/hosts`:

```
127.0.0.1 sudokudo.local
```

Then access at `https://sudokudo.local` (accept the self-signed cert warning).

**SSL**: a self-signed certificate is auto-generated on first start. For production, replace with a
Let's Encrypt certificate (see `nginx/README.md`).

**Firewall**: open ports 80 (HTTP) and 443 (HTTPS). Do NOT open port 7890.
