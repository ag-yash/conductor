# Run Conductor with Docker Compose

Docker Compose gives you a repeatable local Conductor environment. It is useful
when you want to demonstrate the whole system without manually starting three
separate terminals.

## What starts

```text
Browser → dashboard container → API container ← worker container
                              ↓
                       named SQLite volume
```

- **API** owns the control plane and durable SQLite database.
- **Worker** is a separate process that registers, polls, reports resources,
  and runs the deterministic fixture workload.
- **Dashboard** serves the compiled browser UI and forwards `/api` requests to
  the API container.

The worker is deliberately not merged into the API container. A worker owns
model memory and local CPU/RAM measurements, while the API owns durable job
state. Keeping that boundary visible in Docker makes the production design
easier to understand.

## Start the stack

Install and open Docker Desktop first. From the repository root, run:

```bash
docker compose up --build
```

Then open:

- Dashboard: <http://127.0.0.1:5173>
- API documentation: <http://127.0.0.1:8080/docs>

The first build downloads Python, Node, and Nginx base images, so it takes
longer than later runs.

## Run a real fixture job

Leave Compose running. In a second terminal, register the included fixture
model and submit the included job:

```bash
docker compose exec api conductor models register --file examples/fixture-model.json
docker compose exec api conductor jobs submit \
  --file examples/fixture-job.json \
  --idempotency-key compose-demo-1
```

The worker container polls, claims the job, runs the deterministic fixture
adapter, and saves the result. Refresh the dashboard or watch its automatic
refresh update the job status.

Useful observations:

```bash
docker compose logs -f worker
docker compose exec api conductor jobs list
docker compose exec api conductor workers list
```

## Stop and reset

Stop the processes while keeping the SQLite history:

```bash
docker compose down
```

To remove the named volume too, use:

```bash
docker compose down --volumes
```

That second command deletes the Compose-managed database. Use it only when you
intentionally want a clean demo.

## Current boundary

The Compose worker is for the fixture `text.generate` demo. It does not make
Ollama or an ONNX model magically available inside Docker. Local-model runtimes
need deliberate host-model, volume, or accelerator decisions; those belong to a
later deployment refinement. Native setup remains the clearest path for
Apple-Silicon model experiments today.

## Code path to trace

1. [`docker-compose.yml`](../docker-compose.yml) describes the three processes
   and their network/volume relationships.
2. [`docker/api.Dockerfile`](../docker/api.Dockerfile) packages the API and
   worker commands.
3. [`docker/dashboard.Dockerfile`](../docker/dashboard.Dockerfile) builds the
   dashboard bundle.
4. [`docker/dashboard.nginx.conf`](../docker/dashboard.nginx.conf) preserves
   the dashboard's existing same-origin API contract.
