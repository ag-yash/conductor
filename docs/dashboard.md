# Dashboard foundation

## What it is

The dashboard is a browser view of Conductor's current control-plane state. It
is deliberately **read-only** in this first slice. An operator can see whether
the API is ready and inspect recent jobs, registered workers, and trusted model
definitions.

The dashboard is not a second scheduler. It asks the existing API for data:

```text
Browser dashboard
       |
       | GET /api/v1/...
       v
FastAPI routes → services → SQLite
```

This is called a **thin client**. The UI handles presentation; Conductor's
backend owns correctness rules and durable state.

## Run the complete view

Start the backend in the repository root:

```bash
source .venv/bin/activate
conductor-api
```

Then, in a second terminal:

```bash
cd /Users/yash/Documents/Conductor/dashboard
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

If you have not registered data yet, the dashboard will honestly show empty
states. Use the fixture flow in [`cli.md`](cli.md) to create a model, worker,
and job; press **Refresh** to load the new state.

## Why a new workers endpoint was needed

Before this slice, workers could register, heartbeat, lease work, and inspect
their own residency. There was no API that let an operator list all workers.

The dashboard needs that visibility, so Conductor now provides:

```text
GET /api/v1/workers
```

The route calls `WorkerService.list_workers()`, which reads the existing worker
repository. It does not query the database from a React component or from an
API route directly.

The repository orders workers by ID. Databases do not promise a useful default
row order; stable ordering avoids a dashboard list randomly shuffling even when
no worker actually changed.

## What each dashboard card means

| Card | Source | Meaning |
| --- | --- | --- |
| Control plane | `GET /health/ready` | Whether the API and SQLite startup checks are ready to receive work. |
| Registered workers | `GET /workers` | Current worker identities and their current process instances. |
| Active jobs | `GET /jobs` | Number of recent jobs with `assigned` or `running` status. This is a useful small-window signal, not a global queue count. |
| Trusted models | `GET /models` | Definitions the control plane knows about; it does not prove a model is loaded in RAM. |

That last distinction is important: model **definition** means configured;
model **residency** means loaded by one particular worker process. See
[`models-and-runtimes.md`](models-and-runtimes.md) for the detailed explanation.

## Current limitations

- The page fetches state on load and when **Refresh** is pressed; it does not
  yet use polling or WebSockets.
- It displays the most recent eight jobs, not a paginated job explorer.
- It has no write actions. Continue using the CLI or OpenAPI page for job and
  worker operations.
- Vite proxies `/api` only for local development. Production serving and CORS
  policy belong to a later deployment milestone.

These limits are intentional. First we prove that the UI shows truthful data
from the authoritative API. Later slices can add charts, detail pages, and live
updates without changing that boundary.
