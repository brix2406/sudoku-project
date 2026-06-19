# Sudokudo

A full-stack Sudoku solver that accepts either a photo of a puzzle or a manually entered board,
solves it, and returns the completed grid. Supports arbitrary k×n board sizes, not just standard 9×9.

## Architecture

```
Browser → Frontend (React/Vite :5173)
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
| http://localhost:5173 | Frontend |
| http://localhost:5001 | REST API |

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

This creates the PersistentVolumeClaim, Deployments, and Services for all seven components.

### 4. Wait for pods to become ready

```bash
kubectl wait --for=condition=ready pod --all --timeout=180s
```

The OCR worker takes the longest to start due to model loading. If the timeout elapses, re-run the
command or check logs with `kubectl logs deployment/ocr`.

### 5. Access the application

Port-forward the frontend and (optionally) the API:

```bash
# Frontend
kubectl port-forward service/frontend 5173:5173 &

# API (optional — the frontend talks to it via the Vite proxy)
kubectl port-forward service/api 5001:5000 &
```

Open http://localhost:5173.

### Teardown

```bash
kubectl delete -f k3s-manifests/
k3d cluster delete sudokudo
```

## API Reference

Base URL: `http://localhost:5001` (Docker Compose) or `http://localhost:5001` after port-forwarding.

### `POST /solve-image`

Solve a puzzle from a photograph. Upload the image as `multipart/form-data` with the field `file`.

```bash
curl -X POST http://localhost:5001/solve-image \
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
curl -X POST http://localhost:5001/manual_solve \
  -H "Content-Type: application/json" \
  -d '{"value": "Sudoku{(3,3)(5,3,.,.,7,.,.,.,.,6,.,.,1,9,5,.,.,.,.,9,8,.,.,.,.,6,.,.,.,.,6,.,.,.,3,4,.,.,.,8,.,3,.,.,1,7,.,.,.,.,2,.,.,.,.,6,.,.,.,.,2,8,.,.,.,4,.,.,.,.,1,9,.,.,.,5,.,.,.,.,8,.,.,.,7,9)}"}'
```

Response (200 OK): same shape as `/solve-image`.

### `GET /status`

Health check. Returns NATS connectivity and round-trip latency.

```bash
curl http://localhost:5001/status
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
