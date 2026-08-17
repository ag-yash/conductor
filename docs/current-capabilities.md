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
Worker invokes the fixture or Ollama adapter
        ↓
Conductor stores the result and model-residency snapshot
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
and a model you have already pulled.

## Capability matrix

| Area | Implemented now | Still planned |
| --- | --- | --- |
| Control plane | FastAPI application factory, health/readiness, typed settings, structured request IDs | Background scheduling loop and richer operational views |
| Jobs | SQLite-backed submission, idempotency, listing, queued cancellation, result/error persistence | Running-job cancellation, retries, lease-expiry recovery |
| Workers | Register, list, heartbeat, drain, polling, process-instance protection, fixed execution-slot scheduling | Separate long-running worker executable and automatic failure detection |
| Scheduling | Deterministic task/capacity eligibility, least-loaded selection, persisted explanations | CPU, memory, resident-model, priority, and queue-depth scoring |
| Runtimes | Fixture adapter, Ollama text adapter, on-demand loading, warm reuse, safe idle eviction | ONNX adapter, memory-pressure policy, periodic eviction loop |
| Models | Durable definitions and residency snapshots per worker process | Model revision updates and configuration administration |
| Benchmarks | Warmup + repeated execution, wall-clock timing, runtime metrics, SQLite history API and CLI commands | Dashboard charts, percentile distributions, resource sampling |
| User experience | OpenAPI page at `/docs`, thin terminal CLI, and local read-only dashboard with job/worker details and queue explorer | Dashboard write actions and live updates |
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
| How does a runtime stay replaceable? | `runtime/base.py` → `runtime/fixture.py` or `runtime/ollama.py` |
| How is a model kept warm? | `runtime/manager.py` |
| How is a benchmark stored? | `services/workers.py` → `domain/benchmark.py` → `storage/repositories.py` |
| How do tests prove the HTTP flow? | `tests/test_workers_api.py` |
| How does the dashboard avoid becoming a second control plane? | `dashboard/src/api.ts` → `api/workers.py` → `services/workers.py` |
| Where does the dashboard get historical scheduling evidence? | `dashboard/src/App.tsx` → `api/jobs.py` → `services/workers.py` |

## Current limitations worth remembering

- The control plane and worker-facing execution API currently run in the same
  FastAPI process for a simple local demonstration.
- Runtime invocation holds a service transaction open; that is acceptable for
  the current local scope but will need redesign before long-running production
  inference.
- Benchmark wall-clock time measures end-to-end adapter invocation. It is not a
  model-quality score and does not directly measure CPU, RAM, GPU, or accuracy.
- A persisted residency is an operator snapshot. It cannot recreate model memory
  after a worker process restarts.
