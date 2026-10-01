# What Conductor does today

This page is the source of truth for the **current implementation**. Read it
before treating a design document as something you can run today.

The project deliberately documents two things:

- the current, tested system; and
- the `v1.0.0` design target it is growing toward.

Keeping those separate is important. A design is useful for understanding the
direction, but it is not proof that code already exists.

## Current end-to-end story

Today you can run this complete local flow:

```text
Register a trusted model definition
        ↓
Register a local worker process
        ↓
Submit a durable job
        ↓
Worker leases and starts that job
        ↓
Standalone worker claims and starts that job
        ↓
The worker process loads/runs the local model and reports its result, residency, and CPU/RAM snapshots
        ↓
Inspect residency, benchmark the model, or evict it when idle
```

You can perform this flow through the OpenAPI page at `/docs` or through the
new `conductor` terminal command. [`cli.md`](cli.md) walks through the exact
commands using the fixture runtime, which needs no model download.

The same current state is also visible in the local browser dashboard. It is a
read-only API client, not a separate source of state; see [`dashboard.md`](dashboard.md).

The fixture runtime is the reliable default for tests and demos. Ollama is also
wired into the runtime registry, but it requires a locally running Ollama server
and a model you have already pulled. ONNX is available for `tensor.infer`, but
you must register a trusted local `.onnx` artifact whose input names and tensor
shapes you know.

## Capability matrix

| Area | Implemented now | Still planned |
| --- | --- | --- |
| Control plane | FastAPI application factory, health/readiness, typed settings, structured request IDs | Background scheduling loop and richer operational views |
| Jobs | SQLite-backed submission, idempotency, listing, queued cancellation, result/error persistence, and bounded retry after an expired worker lease | Running-job cancellation |
| Workers | Register, list, heartbeat, drain, polling, process-instance protection, fixed execution slots, durable CPU/RAM snapshots, `conductor-worker` with worker-owned runtime execution, and heartbeat-expiry recovery | More advanced failure diagnosis |
| Scheduling | Deterministic task/capacity eligibility, warm-model preference, least-loaded fallback, persisted explanations, and memory-headroom deferral when telemetry is present | CPU scoring, priority, and queue-depth scoring |
| Runtimes | Fixture adapter, Ollama text adapter, ONNX `tensor.infer` adapter, worker-owned on-demand loading, warm reuse, and idle eviction | Memory-pressure policy |
| Models | Durable definitions and residency snapshots per worker process | Model revision updates and configuration administration |
| Benchmarks | Warmup + repeated execution, wall-clock timing, runtime metrics, SQLite history API and CLI commands, and a dashboard timing chart | Percentile distributions |
| User experience | OpenAPI page at `/docs`, thin terminal CLI, and local read-only dashboard with job/worker details, queue explorer, benchmark timing insight, bounded CPU/RAM history charts, and visible-tab polling every 5 seconds | Dashboard write actions |
| Deployment | Native local development and GitHub Actions checks | Docker walkthrough, release package, Apple Silicon performance guide |

## What “implemented” means here

A capability belongs in the implemented column only when it has all of these:

1. production code in the repository;
2. an API or code path that can exercise it;
3. automated tests covering the main contract;
4. documentation explaining how it behaves.

For example, Conductor has an Ollama adapter because `runtime/ollama.py` can load,
invoke, and unload a configured Ollama model through the same adapter contract as
the fixture runtime. It does **not** mean every laptop automatically has Ollama or
the requested model installed.

## How to read target-design documents

Some pages, especially [`vision.md`](vision.md) and
[`state-machines.md`](state-machines.md), include target V1 behavior. When reading
them, use this question:

> Is this marked as current code, or is it a future rule that guides the next
> milestone?

That distinction is an engineering habit worth practicing. It prevents a system
from claiming features it cannot yet demonstrate, while still preserving the
design decisions that future code must satisfy.

## Useful code paths to trace now

| Question | Start here |
| --- | --- |
| How does a job become durable? | `services/jobs.py` → `storage/repositories.py` |
| Why can an old worker not finish new work? | `services/workers.py` → `domain/worker.py` |
| How does a runtime stay replaceable? | `runtime/base.py` → `runtime/fixture.py`, `runtime/ollama.py`, or `runtime/onnx.py` |
| How is a model kept warm? | `runtime/manager.py` |
| How is a benchmark stored? | `services/workers.py` → `domain/benchmark.py` → `storage/repositories.py` |
| How does memory affect placement? | `domain/resource.py` → `services/workers.py` → `scheduler/policy.py` |
| How do tests prove the HTTP flow? | `tests/test_workers_api.py` |
| How does the dashboard avoid becoming a second control plane? | `dashboard/src/api.ts` → `api/workers.py` → `services/workers.py` |
| Where does the dashboard get historical scheduling evidence? | `dashboard/src/App.tsx` → `api/jobs.py` → `services/workers.py` |

## Current limitations worth remembering

- `conductor-worker` is a separate OS process for registration, polling,
  heartbeats, graceful drain, CPU/RAM reporting, and model runtime execution.
  It reports a result or safe failure back to the FastAPI control plane.
- A worker can be declared unreachable after a missed heartbeat even when its
  OS process is merely slow or disconnected. Late reports are rejected rather
  than trusted; see [`lease-recovery.md`](lease-recovery.md).
- Benchmark wall-clock time measures end-to-end adapter invocation. It is not a
  model-quality score and does not directly measure CPU, RAM, GPU, or accuracy.
- A persisted residency is an operator snapshot. It cannot recreate model memory
  after a worker process restarts.
