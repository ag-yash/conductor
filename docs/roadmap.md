# V1 implementation roadmap

Each milestone ends in a runnable, reviewable state and adds only behavior needed by the V1 success criteria.

## M1 — Executable control-plane shell ✅

- FastAPI application factory and typed settings.
- Versioned health and readiness endpoints.
- Structured logging and request correlation.
- Unit tests and CI quality gates.

Demo: start the control plane and inspect build/readiness information.

## M2 — Durable job core ✅

- Job and attempt domain objects with guarded transitions.
- SQLite migrations, repository ports, and implementations.
- Idempotent submission, inspection, listing, and queued cancellation.

Demo: submit duplicate-safe jobs and restart without losing them.

## M3 — Worker leases and deterministic execution 🚧

- Worker registration, `worker_instance_id`, heartbeats, drain behavior, and polling.
- Deterministic control-plane execution path: lease → start → complete.
- Current-process checks reject stale messages after a worker restarts.

Demo: register a worker, lease a job, run it through a predictable success path, and show that an old process cannot report work after a restart.

## M4 — Explainable resource-aware scheduling 🚧

- Eligibility constraints based on task support, worker state, and free execution slots.
- Deterministic least-loaded choice with worker-ID tie-breaking and immutable decision records.
- A job endpoint that shows why each worker was accepted or rejected.

Demo: fill one worker, submit another job, and show that Conductor chooses the available worker with an inspectable explanation.

## M5 — Heterogeneous AI runtimes and model lifecycle

- Ollama-compatible text adapter and one ONNX Runtime workload.
- Model definition and residency lifecycle.
- Idle eviction and memory-pressure policy.
- Benchmark command and recorded latency/resource summaries.

Demo: run two AI task kinds through one API and show warm-model preference and unload behavior.

## M6 — Operator experience

- CLI for submit, inspect, list, cancel, and benchmark flows.
- Dashboard for jobs, workers, queue, models, resources, and scheduling rationale.
- Live updates using a minimal justified transport.

Demo: operate and explain the system without reading terminal logs.

## M7 — Release hardening

- Prometheus-compatible metrics, failure-injection scenarios, and integration tests.
- Docker setup, native Apple Silicon setup, CI, security review, and contributor documentation.
- Reproducible demo script, screenshots/video, performance baseline, and `v1.0.0` release notes.

Demo: clone-to-demo walkthrough on a clean machine.

## Scope gate

A feature not required by [`vision.md`](vision.md) waits until after `v1.0.0`. In particular, no V1 milestone introduces multi-host scheduling, workflow DAGs, authentication, Kubernetes, Kafka, or predictive model selection.
