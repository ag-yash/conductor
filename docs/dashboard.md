# Dashboard

## What it is

The dashboard is a browser view of Conductor's current control-plane state. It
is deliberately **read-only**. An operator can see whether the API is ready,
inspect recent jobs, registered workers, and trusted model definitions, then
select a job or worker to investigate the evidence behind it.

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

## Investigating a job

Click a job in **Recent jobs**. The detail panel shows its durable result or
error, followed by its saved scheduling decision.

For example, when a worker asks for the next job, Conductor takes a snapshot of
eligible workers and saves why each candidate was accepted or rejected. That
record is a **scheduling rationale**. It lets you answer a useful operations
question after the fact:

> Why was this job placed on `demo-worker` instead of another worker?

The dashboard reads it from:

```text
GET /api/v1/jobs/{job_id}/scheduling-decisions
```

The browser does not recompute the selection rule. Recomputing it later would
be misleading because workers may have heartbeated or changed capacity since
the decision happened. The saved record is the truthful historical answer.

## Investigating a worker

Click a worker in **Workers**. The detail panel makes two related but different
ideas visible:

1. **Model residency** — which models this exact process has loaded or last
   reported as loaded.
2. **Benchmark history** — measurements recorded while that exact process ran
   a model after warm-up.

Both requests include the worker's `instance_id`. This matters because a worker
name such as `demo-worker` can survive a restart, while the actual process does
not. A restart creates a new instance ID, and data from the older process must
not be treated as data from the new one.

```text
GET /api/v1/workers/{worker_id}/residencies
GET /api/v1/workers/{worker_id}/benchmarks
            + Worker-Instance-ID header
```

“Model definition” and “model residency” are intentionally separate. A
definition says Conductor is allowed to use a model. A residency says one
specific worker process has loaded it. The first is configuration; the second
is operational state.

## Exploring a larger queue

The overview shows only recent jobs so it stays small and quick. **Queue
explorer** is for looking through a larger set of durable jobs.

Choose a status such as `queued`, `running`, `succeeded`, or `failed`, then use
**Previous** and **Next** to move through pages of ten jobs. Selecting any job
opens the same evidence panel described above.

The dashboard asks the existing jobs API for only the needed slice:

```text
GET /api/v1/jobs?status=queued&limit=11&offset=20
```

`offset=20` means “skip the first twenty matching jobs.” The dashboard displays
the first ten rows and uses the eleventh as a look-ahead row. If that extra row
exists, **Next** is enabled; if it does not, the current page is the last one.

Why not ask for the total number of jobs? A total-count query can become costly
for a large queue. This look-ahead pattern gives the operator the only answer
needed for navigation—“is there another page?”—while keeping each request
bounded. It is a small example of **pagination**, meaning reading a large list
in stable-sized pieces rather than loading the whole list at once.

## Reading benchmark timing insight

When you select a worker with saved benchmark history, **Recent benchmarks**
also includes a small timing chart. Each bar is one durable benchmark summary;
the bars run from the oldest displayed summary on the left to the newest on the
right.

The chart uses `mean_wall_time_ms`, the average elapsed time across that
benchmark's measured runs. For example, a `20 ms` bar means that the timed runs
in that one benchmark averaged 20 milliseconds after warm-up. A taller bar
means a slower average execution, not a better or worse model.

The summary cards show the fastest, slowest, and latest mean. If the selected
runtime reports extra numeric values, such as an Ollama evaluation count, the
latest values appear below the chart exactly as the adapter reported them.

This view deliberately does **not** claim to show host CPU or RAM consumption.
Conductor does not collect that data yet, and showing a made-up estimate would
be misleading. Host-resource sampling is a later capability.

## What each dashboard card means

| Card | Source | Meaning |
| --- | --- | --- |
| Control plane | `GET /health/ready` | Whether the API and SQLite startup checks are ready to receive work. |
| Registered workers | `GET /workers` | Current worker identities and their current process instances. |
| Active jobs | `GET /jobs` | Number of recent jobs with `assigned` or `running` status. This is a useful small-window signal, not a global queue count. |
| Trusted models | `GET /models` | Definitions the control plane knows about; it does not prove a model is loaded in RAM. |
| Job detail | `GET /jobs/{job_id}/scheduling-decisions` | The historical candidate evaluation saved when Conductor placed or deferred a job. |
| Worker detail | `GET /workers/{worker_id}/residencies` and `/benchmarks` | Loaded-model snapshots and warm-runtime measurements for the current worker process. |
| Benchmark timing insight | Existing benchmark history in the worker detail | A visual comparison of saved mean wall-clock timings; it is not a CPU/RAM chart. |
| Queue explorer | `GET /jobs?status=...&limit=11&offset=...` | A filterable, paginated view of durable jobs. |

That last distinction is important: model **definition** means configured;
model **residency** means loaded by one particular worker process. See
[`models-and-runtimes.md`](models-and-runtimes.md) for the detailed explanation.

## Current limitations

- The page fetches state on load and when **Refresh** is pressed; it does not
  yet use polling or WebSockets.
- It displays the most recent eight jobs in the overview, while Queue explorer
  has status filters and forward/backward pagination.
- It has no write actions. Continue using the CLI or OpenAPI page for job and
  worker operations.
- Vite proxies `/api` only for local development. Production serving and CORS
  policy belong to a later deployment milestone.

These limits are intentional. The dashboard now proves that a UI can show
truthful current state **and** durable evidence from the authoritative API.
Later slices can add charts and live updates without changing that boundary.
