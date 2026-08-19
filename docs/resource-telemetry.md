# Worker resource telemetry

## Plain meaning

A worker cannot safely run AI work just because it has a free execution slot.
It also needs enough real memory on the laptop.

Resource telemetry is the worker reporting a small measurement such as:

```text
Host CPU:                  31.5%
Host memory available:     5.0 GiB
This worker process RAM:   300 MiB
This worker process CPU:   12.0%
```

Conductor stores each report as an immutable **snapshot**. A snapshot is a fact
observed at one moment; it is not a prediction and it is not a model-quality
score.

## What exists now

The current API accepts, stores, lists, and displays snapshots for the current
worker process. When Conductor knows a model's declared memory requirement, the
scheduler uses the latest snapshot as a hard safety check.

```text
Worker reports available host memory
        ↓
Conductor keeps 512 MiB safety reserve
        ↓
Scheduler compares remaining headroom with model expected memory
        ↓
Place job, or save `insufficient_memory_headroom`
```

The reporting call is explicit in this phase. A future standalone worker
executable will collect and submit reports periodically. Until then, the CLI or
OpenAPI page is the honest way to send a measured sample for a demo.

## The measurements

| Field | Meaning | Why it matters |
| --- | --- | --- |
| `host_cpu_percent` | CPU use across the whole laptop, from 0–100% | Operator visibility; future CPU-aware scoring |
| `host_total_memory_bytes` | Total physical host memory | Makes available memory interpretable |
| `host_available_memory_bytes` | Memory the operating system can make available now | The scheduler's current safety input |
| `process_memory_bytes` | RAM used by this worker process | Separates worker cost from the whole laptop |
| `process_cpu_percent` | CPU used by this worker process | Helps explain a locally busy worker |

The host and worker-process numbers are deliberately separate. A high host RAM
number may come from a browser or IDE; it does not prove the worker itself is
large. Conversely, a worker can be small while the laptop has too little free
memory to safely load another model.

## Record a snapshot

Register the worker first, then use the included example as a shape reference:

```bash
conductor workers report-resources \
  --worker-id demo-worker \
  --instance-id process-a \
  --file examples/worker-resource-snapshot.json
```

Only the current process instance may report. If `demo-worker` restarts as
`process-b`, a late report from `process-a` returns `409 Conflict` instead of
polluting the new worker's history.

List the current process's recent reports:

```bash
conductor workers resource-snapshots \
  --worker-id demo-worker \
  --instance-id process-a
```

The API orders them newest first. The dashboard uses the newest item for its
**Latest resource snapshot** card.

## Memory headroom example

Assume these values:

```text
Available host memory: 1,024 MiB
Safety reserve:          512 MiB
Safe headroom:            512 MiB
Requested model:          768 MiB
```

The model does not fit. Conductor keeps the job queued and records
`insufficient_memory_headroom`.

The 512 MiB reserve is intentional. Using every byte that appears free risks
freezing the operating system, starving your IDE, or triggering memory pressure
while a model is loading.

## Important limits

- A report is trusted local-worker input in the current loopback-only product;
  it is not a security boundary.
- The scheduler enforces memory only when it has a latest snapshot. Workers
  without telemetry remain compatible during this rollout.
- CPU is stored and displayed, but it does not yet change placement decisions.
- The dashboard shows the latest snapshot. Historical CPU/RAM charts and a
  periodic measuring worker are the next improvements.

## Code path to trace

1. `api/workers.py` validates a report.
2. `services/workers.py` rejects stale process identities and creates the snapshot.
3. `storage/repositories.py` appends it to SQLite.
4. `scheduler/policy.py` checks memory headroom during placement.
5. `dashboard/src/App.tsx` shows the latest durable snapshot.
6. `tests/test_workers_api.py` proves storage, stale-process protection, and
   memory-based deferral.
